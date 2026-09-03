//! PIPELINE SELF-TEST ONLY. This is NOT a ZK scheme and its numbers MUST NOT
//! appear in the paper. It exists so the prover/verifier binaries, the CSV
//! schema, the Python analysis, and the scp/ssh plumbing can be exercised
//! end-to-end before any real backend is wired in.
//!
//! It "aggregates" by running the reference `chain_output` and hashing it.

use crate::workload::{ref_chain_output, AggWorkload};
use crate::{Scheme, SchemeKind};

pub struct NoopAgg;

pub struct Prover;
pub struct Verifier;

pub struct Proof {
    pub claimed_output: u128,
    pub tag: u64,
}

fn tag(x: u128) -> u64 {
    // not cryptographic; just a deterministic mix
    let mut z = (x as u64) ^ ((x >> 64) as u64) ^ 0xD1B5_4A32_D192_ED03;
    z = (z ^ (z >> 33)).wrapping_mul(0xFF51_AFD7_ED55_8CCD);
    z = (z ^ (z >> 33)).wrapping_mul(0xC4CE_B9FE_1A85_EC53);
    z ^ (z >> 33)
}

impl Scheme for NoopAgg {
    const NAME: &'static str = "noop";
    const KIND: SchemeKind = SchemeKind::Recursive; // arbitrary; excluded from analysis

    type Prover = Prover;
    type Verifier = Verifier;
    type Proof = Proof;

    fn setup_prover(_w: &AggWorkload) -> anyhow::Result<Prover> {
        Ok(Prover)
    }
    fn export_vk(_p: &Prover) -> anyhow::Result<Vec<u8>> {
        Ok(Vec::new())
    }
    fn verifier_from_vk(_w: &AggWorkload, _vk: &[u8]) -> anyhow::Result<Verifier> {
        Ok(Verifier)
    }
    fn prove(_p: &Prover, w: &AggWorkload) -> anyhow::Result<Proof> {
        let out = ref_chain_output(w);
        Ok(Proof { claimed_output: out, tag: tag(out) })
    }
    fn verify(_v: &Verifier, proof: &Proof) -> anyhow::Result<bool> {
        Ok(tag(proof.claimed_output) == proof.tag)
    }
    fn proof_bytes(proof: &Proof) -> anyhow::Result<Vec<u8>> {
        let mut b = Vec::with_capacity(24);
        b.extend_from_slice(&proof.claimed_output.to_le_bytes());
        b.extend_from_slice(&proof.tag.to_le_bytes());
        Ok(b)
    }
    fn proof_from_bytes(_v: &Verifier, bytes: &[u8]) -> anyhow::Result<Proof> {
        anyhow::ensure!(bytes.len() == 24, "noop proof must be 24 bytes");
        let claimed_output = u128::from_le_bytes(bytes[0..16].try_into().unwrap());
        let tag = u64::from_le_bytes(bytes[16..24].try_into().unwrap());
        Ok(Proof { claimed_output, tag })
    }
}
