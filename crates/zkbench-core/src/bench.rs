//! Generic measurement loops shared by both binaries. Warmup runs are executed
//! and discarded; only the `runs` measured iterations are written to CSV.

use crate::metrics::{peak_mem_bytes, proc_peak_rss_bytes, reset_peak_mem, time_ms};
use crate::workload::AggWorkload;
use crate::{ProveRecord, Scheme, VerifyRecord};
use anyhow::Result;
use std::io::Write;

/// Result of a proving sweep at one depth: the proof bytes and the vk bytes
/// from the final measured run (written to `<scheme>_d<depth>.bin` / `.vk`).
pub struct ProveArtifacts {
    pub proof: Vec<u8>,
    pub vk: Vec<u8>,
}

/// Experiment 1: prove `w.depth` aggregation for scheme `S`, `warmup + runs`
/// times, appending `ProveRecord`s to `wtr`.
pub fn prove_runs<S, W>(
    w: &AggWorkload,
    warmup: u32,
    runs: u32,
    wtr: &mut csv::Writer<W>,
) -> Result<ProveArtifacts>
where
    S: Scheme,
    W: Write,
{
    let prover = S::setup_prover(w)?;
    let vk = S::export_vk(&prover)?;
    let vk_size = vk.len() as u64;
    let verifier = S::verifier_from_vk(w, &vk)?;

    for _ in 0..warmup {
        let p = S::prove(&prover, w)?;
        anyhow::ensure!(S::verify(&verifier, &p)?, "warmup proof failed to verify");
    }

    let mut last_proof = Vec::new();
    for run in 0..runs {
        reset_peak_mem();
        let (proof, ms) = time_ms(|| S::prove(&prover, w));
        let proof = proof?;
        let mem = peak_mem_bytes();
        let bytes = S::proof_bytes(&proof)?;

        wtr.serialize(ProveRecord {
            scheme: S::NAME.to_string(),
            kind: S::KIND.as_str().to_string(),
            depth: w.depth,
            run,
            proving_time_ms: ms,
            peak_mem_bytes: mem,
            proof_size_bytes: bytes.len() as u64,
            vk_size_bytes: vk_size,
        })?;
        last_proof = bytes;
    }
    wtr.flush()?;
    Ok(ProveArtifacts { proof: last_proof, vk })
}

/// Experiment 1 (host="x86") and Experiment 3 (host="arm"): verify a proof
/// loaded from bytes, `warmup + runs` times, appending `VerifyRecord`s.
///
/// The `Verifier` is rebuilt from the compact vk only — cheap, so the recorded
/// peak memory reflects verification, not setup.
pub fn verify_runs<S, W>(
    w: &AggWorkload,
    proof_bytes: &[u8],
    vk_bytes: &[u8],
    host: &str,
    warmup: u32,
    runs: u32,
    wtr: &mut csv::Writer<W>,
) -> Result<()>
where
    S: Scheme,
    W: Write,
{
    let verifier = S::verifier_from_vk(w, vk_bytes)?;
    let proof = S::proof_from_bytes(&verifier, proof_bytes)?;
    anyhow::ensure!(S::verify(&verifier, &proof)?, "proof does not verify — aborting");

    for _ in 0..warmup {
        let _ = S::verify(&verifier, &proof)?;
    }

    for run in 0..runs {
        reset_peak_mem();
        let (ok, ms) = time_ms(|| S::verify(&verifier, &proof));
        anyhow::ensure!(ok?, "verification returned false mid-measurement");
        let mem = proc_peak_rss_bytes().unwrap_or_else(peak_mem_bytes);

        wtr.serialize(VerifyRecord {
            scheme: S::NAME.to_string(),
            kind: S::KIND.as_str().to_string(),
            depth: w.depth,
            run,
            verify_time_ms: ms,
            peak_mem_bytes: mem,
            proof_size_bytes: proof_bytes.len() as u64,
            host: host.to_string(),
        })?;
    }
    wtr.flush()?;
    Ok(())
}
