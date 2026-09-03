//! zkbench-core: shared workload, scheme abstraction, and measurement harness
//! for the SwiftZK-Wallet evaluation.
//!
//! The SAME code path is used for Experiment 1 (x86 native) and Experiment 3
//! (ARM native). Experiment 2 (EVM gas) lives in `../../evm` and is deliberately
//! decoupled: it consumes exported proof bytes, not this harness.

pub mod adapters;
pub mod bench;
pub mod metrics;
pub mod workload;

use serde::Serialize;

/// Recursive schemes aggregate `depth` unit proofs into one; folding schemes
/// fold `depth` steps and then run a decider. `depth` is the single knob swept
/// in Experiment 1: {2, 4, 8, 16, 32, 64}.
pub const DEPTHS: [u32; 6] = [2, 4, 8, 16, 32, 64];

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
pub enum SchemeKind {
    Recursive,
    Folding,
}

impl SchemeKind {
    pub fn as_str(&self) -> &'static str {
        match self {
            SchemeKind::Recursive => "recursive",
            SchemeKind::Folding => "folding",
        }
    }
}

/// A ZK aggregation scheme under test.
///
/// Implementors MUST NOT print, sleep, or otherwise distort timing. `prove`
/// returns the aggregated/decider proof; `verify` is what a lightweight wallet
/// (Exp 3) or an EVM verifier (Exp 2, via exported bytes) would run.
///
/// The prover and verifier are constructed separately so that the ARM host
/// (Exp 3) builds only a compact verification key and never reconstructs
/// circuits or public parameters — otherwise "verification memory" would be
/// dominated by setup, not by verifying.
pub trait Scheme {
    const NAME: &'static str;
    const KIND: SchemeKind;

    type Prover;
    type Verifier;
    type Proof;

    /// Full prover-side setup (circuits / SRS / proving + verifying keys). Run
    /// once on the x86 machine; excluded from the timed measurements.
    fn setup_prover(w: &workload::AggWorkload) -> anyhow::Result<Self::Prover>;

    /// Serialize the compact verification key from the prover-side data. Written
    /// next to the proof as `<scheme>_d<depth>.vk`.
    fn export_vk(p: &Self::Prover) -> anyhow::Result<Vec<u8>>;

    /// Reconstruct a `Verifier` from the exported vk bytes and the workload
    /// descriptor (for public inputs). Must be cheap — no circuit/SRS rebuild.
    fn verifier_from_vk(w: &workload::AggWorkload, vk: &[u8]) -> anyhow::Result<Self::Verifier>;

    /// Produce the aggregated proof for `w.depth`.
    fn prove(p: &Self::Prover, w: &workload::AggWorkload) -> anyhow::Result<Self::Proof>;

    /// Verify the aggregated proof. Returns `Ok(true)` iff valid.
    fn verify(v: &Self::Verifier, proof: &Self::Proof) -> anyhow::Result<bool>;

    /// Canonical, minimal serialization of the proof (bytes counted as
    /// "Proof Size" and exported for Experiment 2). Does NOT include the vk.
    fn proof_bytes(proof: &Self::Proof) -> anyhow::Result<Vec<u8>>;

    /// Deserialize what `proof_bytes` produced (used by the verifier binary and
    /// on the ARM host, which never proves).
    fn proof_from_bytes(v: &Self::Verifier, bytes: &[u8]) -> anyhow::Result<Self::Proof>;
}

/// One row of Experiment 1 proving output.
#[derive(Debug, Clone, Serialize)]
pub struct ProveRecord {
    pub scheme: String,
    pub kind: String,
    pub depth: u32,
    pub run: u32,
    pub proving_time_ms: f64,
    pub peak_mem_bytes: u64,
    pub proof_size_bytes: u64,
    /// Size of the exported verification key the wallet must store. Constant
    /// across runs; repeated on each row for convenience.
    pub vk_size_bytes: u64,
}

/// One row of Experiment 1 / Experiment 3 verification output.
#[derive(Debug, Clone, Serialize)]
pub struct VerifyRecord {
    pub scheme: String,
    pub kind: String,
    pub depth: u32,
    pub run: u32,
    pub verify_time_ms: f64,
    pub peak_mem_bytes: u64,
    pub proof_size_bytes: u64,
    /// "x86" or "arm" — set from a CLI flag so Exp1/Exp3 rows are distinguishable.
    pub host: String,
}
