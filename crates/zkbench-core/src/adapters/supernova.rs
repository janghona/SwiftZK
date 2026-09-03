//! SuperNova (folding, non-uniform IVC) adapter.
//!
//! Integration plan (see docs/adapters.md):
//!   crate: `nova-snark` SuperNova API, or `sonobe`.
//!   - A small set of step circuits (program instructions); for this workload
//!     two variants of the unit step selected round-robin, so the non-uniform
//!     machinery is actually exercised while total work matches Nova.
//!   - Fold `depth` steps, then a compressed-SNARK decider.
//!   - Exp 3 measures the decider / compressed-SNARK verification (same rule as
//!     the Nova adapter).

use crate::workload::AggWorkload;
use crate::{Scheme, SchemeKind};

pub struct SuperNovaAgg;

pub struct Prover;
pub struct Verifier;
pub struct Proof;

const TODO: &str = "SuperNova adapter not implemented — see docs/adapters.md";

impl Scheme for SuperNovaAgg {
    const NAME: &'static str = "supernova";
    const KIND: SchemeKind = SchemeKind::Folding;

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
