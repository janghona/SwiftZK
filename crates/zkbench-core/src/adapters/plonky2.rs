//! Plonky2 (recursive, PLONK + FRI over Goldilocks) adapter.
//!
//! Aggregation structure: a linear recursion chain. Layer 1 (the *leaf*) proves
//! one MiMC unit step with public inputs `[u0, u1]`. Layer `i` (a *wrap*)
//! verifies layer `i-1`'s proof in-circuit, applies one more MiMC step, and
//! exposes `[u0, u_i]`. The depth-`d` proof attests to the whole chain
//! `u0 -> u1 -> ... -> u_d`.
//!
//! Circuits are built once in `setup` (excluded from timing) and reused across
//! measured runs. Verification needs only the final circuit's common data and
//! verifier data, both carried in `Verifier`.

use crate::workload::{round_constant, AggWorkload, STEP_ROUNDS};
use crate::{Scheme, SchemeKind};
use anyhow::{anyhow, Result};

use plonky2::field::goldilocks_field::GoldilocksField;
use plonky2::field::types::Field;
use plonky2::iop::target::Target;
use plonky2::iop::witness::{PartialWitness, WitnessWrite};
use plonky2::plonk::circuit_builder::CircuitBuilder;
use plonky2::plonk::circuit_data::{
    CircuitConfig, CircuitData, VerifierCircuitData, VerifierCircuitTarget,
};
use plonky2::plonk::config::PoseidonGoldilocksConfig;
use plonky2::plonk::proof::{ProofWithPublicInputs, ProofWithPublicInputsTarget};
use plonky2::util::serialization::DefaultGateSerializer;

const D: usize = 2;
type C = PoseidonGoldilocksConfig;
type F = GoldilocksField;

const GOLDILOCKS_ORDER: u64 = 0xFFFF_FFFF_0000_0001;

pub struct Plonky2Agg;

struct Leaf {
    data: CircuitData<F, C, D>,
    x: Target,
}

struct Wrap {
    data: CircuitData<F, C, D>,
    inner: ProofWithPublicInputsTarget<D>,
    inner_vd: VerifierCircuitTarget,
}

pub struct Prover {
    seed: u64,
    leaf: Leaf,
    wraps: Vec<Wrap>, // wraps[0] == layer 2
}

impl Prover {
    fn final_data(&self) -> &CircuitData<F, C, D> {
        self.wraps.last().map(|w| &w.data).unwrap_or(&self.leaf.data)
    }
}

pub struct Verifier {
    vd: VerifierCircuitData<F, C, D>,
}

pub struct Proof(ProofWithPublicInputs<F, C, D>);

// --- gadgets -------------------------------------------------------------

fn rc_field(i: usize) -> F {
    F::from_canonical_u64(round_constant(i) % GOLDILOCKS_ORDER)
}

/// One MiMC unit step: `STEP_ROUNDS` rounds of `x <- (x + c_i)^5`.
fn mimc_step_circuit(b: &mut CircuitBuilder<F, D>, mut x: Target) -> Target {
    for i in 0..STEP_ROUNDS {
        let c = b.constant(rc_field(i));
        let t = b.add(x, c);
        let t2 = b.mul(t, t);
        let t4 = b.mul(t2, t2);
        x = b.mul(t4, t);
    }
    x
}

fn mimc_step_native(mut x: F) -> F {
    for i in 0..STEP_ROUNDS {
        let t = x + rc_field(i);
        let t2 = t * t;
        x = t2 * t2 * t;
    }
    x
}

// --- circuit construction ---------------------------------------------

fn build_leaf() -> Leaf {
    let mut b = CircuitBuilder::<F, D>::new(CircuitConfig::standard_recursion_config());
    let x = b.add_virtual_target();
    let y = mimc_step_circuit(&mut b, x);
    b.register_public_input(x);
    b.register_public_input(y);
    Leaf { data: b.build::<C>(), x }
}

fn build_wrap(inner: &CircuitData<F, C, D>) -> Wrap {
    let mut b = CircuitBuilder::<F, D>::new(CircuitConfig::standard_recursion_config());
    let inner_t = b.add_virtual_proof_with_pis(&inner.common);
    let inner_vd = b.add_virtual_verifier_data(inner.common.config.fri_config.cap_height);
    b.verify_proof::<C>(&inner_t, &inner_vd, &inner.common);

    let u0 = inner_t.public_inputs[0];
    let u_prev = inner_t.public_inputs[1];
    let u_i = mimc_step_circuit(&mut b, u_prev);
    b.register_public_input(u0);
    b.register_public_input(u_i);

    Wrap { data: b.build::<C>(), inner: inner_t, inner_vd }
}

fn build_all(depth: u32) -> (Leaf, Vec<Wrap>) {
    let leaf = build_leaf();
    let mut wraps: Vec<Wrap> = Vec::new();
    for i in 1..depth {
        let w = if i == 1 {
            build_wrap(&leaf.data)
        } else {
            build_wrap(&wraps[(i - 2) as usize].data)
        };
        wraps.push(w);
    }
    (leaf, wraps)
}

// --- Scheme impl ----------------------------------------------------

impl Scheme for Plonky2Agg {
    const NAME: &'static str = "plonky2";
    const KIND: SchemeKind = SchemeKind::Recursive;

    type Prover = Prover;
    type Verifier = Verifier;
    type Proof = Proof;

    fn setup_prover(w: &AggWorkload) -> Result<Prover> {
        anyhow::ensure!(w.depth >= 1, "depth must be >= 1");
        let (leaf, wraps) = build_all(w.depth);
        Ok(Prover { seed: w.seed, leaf, wraps })
    }

    fn export_vk(p: &Prover) -> Result<Vec<u8>> {
        p.final_data()
            .verifier_data()
            .to_bytes(&DefaultGateSerializer)
            .map_err(|e| anyhow!("plonky2 vk encode: {e:?}"))
    }

    fn verifier_from_vk(_w: &AggWorkload, vk: &[u8]) -> Result<Verifier> {
        let vd = VerifierCircuitData::<F, C, D>::from_bytes(vk.to_vec(), &DefaultGateSerializer)
            .map_err(|e| anyhow!("plonky2 vk decode: {e:?}"))?;
        Ok(Verifier { vd })
    }

    fn prove(p: &Prover, _w: &AggWorkload) -> Result<Proof> {
        let u0 = F::from_canonical_u64(p.seed % GOLDILOCKS_ORDER);

        let mut pw = PartialWitness::new();
        pw.set_target(p.leaf.x, u0)?;
        let mut proof = p.leaf.data.prove(pw)?;
        let mut u_last = mimc_step_native(u0);
        debug_assert_eq!(proof.public_inputs[1], u_last);

        for (idx, wrap) in p.wraps.iter().enumerate() {
            let inner_vo = if idx == 0 {
                &p.leaf.data.verifier_only
            } else {
                &p.wraps[idx - 1].data.verifier_only
            };
            let mut pw = PartialWitness::new();
            pw.set_proof_with_pis_target(&wrap.inner, &proof)?;
            pw.set_verifier_data_target(&wrap.inner_vd, inner_vo)?;
            proof = wrap.data.prove(pw)?;
            u_last = mimc_step_native(u_last);
            debug_assert_eq!(proof.public_inputs[1], u_last);
        }
        Ok(Proof(proof))
    }

    fn verify(v: &Verifier, proof: &Proof) -> Result<bool> {
        Ok(v.vd.verify(proof.0.clone()).is_ok())
    }

    fn proof_bytes(proof: &Proof) -> Result<Vec<u8>> {
        Ok(proof.0.to_bytes())
    }

    fn proof_from_bytes(v: &Verifier, bytes: &[u8]) -> Result<Proof> {
        let p = ProofWithPublicInputs::<F, C, D>::from_bytes(bytes.to_vec(), &v.vd.common)
            .map_err(|e| anyhow!("plonky2 proof decode: {e}"))?;
        Ok(Proof(p))
    }
}
