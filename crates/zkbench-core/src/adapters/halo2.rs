//! Halo2 (recursive, accumulation-based) adapter.
//!
//! Integration plan (see docs/adapters.md):
//!   crate: `halo2_proofs` (PSE fork) + `halo2curves`, KZG on BN256.
//!   - Unit circuit: `STEP_HASH_ITERS` splitmix64 rounds as a chip.
//!   - Aggregation: verify the previous proof in-circuit (accumulator), depth
//!     compositions deep; the final proof is a single Halo2 proof.
//!   - `proof_bytes`: `transcript` bytes + serialized instances.
//!
//! Until wired in, every method panics with a clear message so NO fake numbers
//! can be produced.

use crate::workload::AggWorkload;
use crate::{Scheme, SchemeKind};

pub struct Halo2Agg;

pub struct Prover;
pub struct Verifier;
pub struct Proof;

const TODO: &str = "Halo2 adapter not implemented — see docs/adapters.md";

impl Scheme for Halo2Agg {
    const NAME: &'static str = "halo2";
    const KIND: SchemeKind = SchemeKind::Recursive;

    type Prover = Prover;
    type Verifier = Verifier;
    type Proof = Proof;

    fn setup_prover(_w: &AggWorkload) -> anyhow::Result<Prover> {
        unimplemented!("{TODO}")
    }
    fn export_vk(_p: &Prover) -> anyhow::Result<Vec<u8>> {
        unimplemented!("{TODO}")
    }
    fn verifier_from_vk(_w: &AggWorkload, _vk: &[u8]) -> anyhow::Result<Verifier> {
        unimplemented!("{TODO}")
    }
    fn prove(_p: &Prover, _w: &AggWorkload) -> anyhow::Result<Proof> {
        unimplemented!("{TODO}")
    }
    fn verify(_v: &Verifier, _proof: &Proof) -> anyhow::Result<bool> {
        unimplemented!("{TODO}")
    }
    fn proof_bytes(_proof: &Proof) -> anyhow::Result<Vec<u8>> {
        unimplemented!("{TODO}")
    }
    fn proof_from_bytes(_v: &Verifier, _bytes: &[u8]) -> anyhow::Result<Proof> {
        unimplemented!("{TODO}")
    }
}
