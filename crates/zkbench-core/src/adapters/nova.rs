//! Nova (folding, relaxed R1CS) adapter — nova-snark 0.75.
//!
//! Step circuit `F` = one MiMC unit step (`STEP_ROUNDS` rounds of
//! `x <- (x + c_i)^5`), arity 1. `prove` folds `depth` steps into the running
//! relaxed-R1CS instance, then runs the **decider** (`CompressedSNARK` over
//! Spartan). Per the study, `verify` measures the decider / compressed-SNARK
//! check — exactly what a wallet or EVM verifier runs — not the per-step
//! folding verifier.

use crate::workload::{round_constant, AggWorkload, STEP_ROUNDS};
use crate::{Scheme, SchemeKind};
use anyhow::{anyhow, Result};

use nova_snark::{
    frontend::{num::AllocatedNum, ConstraintSystem, SynthesisError},
    nova::{CompressedSNARK, ProverKey, PublicParams, RecursiveSNARK, VerifierKey},
    provider::{PallasEngine, VestaEngine},
    traits::{circuit::StepCircuit, snark::RelaxedR1CSSNARKTrait, Engine},
};

// Pallas/Vesta 2-cycle with IPA commitments: transparent setup (no trusted
// ceremony), the canonical Nova instantiation.
type E1 = PallasEngine;
type E2 = VestaEngine;
type EE1 = nova_snark::provider::ipa_pc::EvaluationEngine<E1>;
type EE2 = nova_snark::provider::ipa_pc::EvaluationEngine<E2>;
type S1 = nova_snark::spartan::snark::RelaxedR1CSSNARK<E1, EE1>;
type S2 = nova_snark::spartan::snark::RelaxedR1CSSNARK<E2, EE2>;
type Scal = <E1 as Engine>::Scalar;

const BINCODE: bincode::config::Configuration = bincode::config::standard();

pub struct NovaAgg;

#[derive(Clone)]
struct MimcStep;

impl StepCircuit<Scal> for MimcStep {
    fn arity(&self) -> usize {
        1
    }

    fn synthesize<CS: ConstraintSystem<Scal>>(
        &self,
        cs: &mut CS,
        z: &[AllocatedNum<Scal>],
    ) -> Result<Vec<AllocatedNum<Scal>>, SynthesisError> {
        let mut x = z[0].clone();
        for i in 0..STEP_ROUNDS {
            let c = Scal::from(round_constant(i));
            // t = x + c_i
            let t = AllocatedNum::alloc(cs.namespace(|| format!("t_{i}")), || {
                Ok(x.get_value().ok_or(SynthesisError::AssignmentMissing)? + c)
            })?;
            cs.enforce(
                || format!("t_def_{i}"),
                |lc| lc + x.get_variable() + (c, CS::one()),
                |lc| lc + CS::one(),
                |lc| lc + t.get_variable(),
            );
            // x <- t^5
            let t2 = t.square(cs.namespace(|| format!("t2_{i}")))?;
            let t4 = t2.square(cs.namespace(|| format!("t4_{i}")))?;
            x = t4.mul(cs.namespace(|| format!("t5_{i}")), &t)?;
        }
        Ok(vec![x])
    }
}

fn mimc_step_native(mut x: Scal) -> Scal {
    for i in 0..STEP_ROUNDS {
        let t = x + Scal::from(round_constant(i));
        let t2 = t * t;
        x = t2 * t2 * t;
    }
    x
}

pub struct Prover {
    pp: PublicParams<E1, E2, MimcStep>,
    pk: ProverKey<E1, E2, MimcStep, S1, S2>,
    vk: VerifierKey<E1, E2, MimcStep, S1, S2>,
    z0: Vec<Scal>,
}

pub struct Verifier {
    vk: VerifierKey<E1, E2, MimcStep, S1, S2>,
    z0: Vec<Scal>,
}

fn z0_from_seed(seed: u64) -> Vec<Scal> {
    vec![Scal::from(seed)]
}

pub struct Proof {
    snark: CompressedSNARK<E1, E2, MimcStep, S1, S2>,
    steps: usize,
}

impl Scheme for NovaAgg {
    const NAME: &'static str = "nova";
    const KIND: SchemeKind = SchemeKind::Folding;

    type Prover = Prover;
    type Verifier = Verifier;
    type Proof = Proof;

    fn setup_prover(w: &AggWorkload) -> Result<Prover> {
        anyhow::ensure!(w.depth >= 1, "depth must be >= 1");
        let circuit = MimcStep;
        let pp = PublicParams::<E1, E2, MimcStep>::setup(
            &circuit,
            &*S1::ck_floor(),
            &*S2::ck_floor(),
        )
        .map_err(|e| anyhow!("nova PublicParams::setup: {e:?}"))?;
        let (pk, vk) = CompressedSNARK::<_, _, _, S1, S2>::setup(&pp)
            .map_err(|e| anyhow!("nova CompressedSNARK::setup: {e:?}"))?;
        Ok(Prover { pp, pk, vk, z0: z0_from_seed(w.seed) })
    }

    fn export_vk(p: &Prover) -> Result<Vec<u8>> {
        bincode::serde::encode_to_vec(&p.vk, bincode::config::standard())
            .map_err(|e| anyhow!("nova vk encode: {e}"))
    }

    fn verifier_from_vk(w: &AggWorkload, vk: &[u8]) -> Result<Verifier> {
        let (vk, _) = bincode::serde::decode_from_slice(vk, bincode::config::standard())
            .map_err(|e| anyhow!("nova vk decode: {e}"))?;
        Ok(Verifier { vk, z0: z0_from_seed(w.seed) })
    }

    fn prove(p: &Prover, w: &AggWorkload) -> Result<Proof> {
        let circuit = MimcStep;
        let steps = w.depth as usize;
        let mut rs = RecursiveSNARK::<E1, E2, MimcStep>::new(&p.pp, &circuit, &p.z0)
            .map_err(|e| anyhow!("nova RecursiveSNARK::new: {e:?}"))?;
        for _ in 0..steps {
            rs.prove_step(&p.pp, &circuit)
                .map_err(|e| anyhow!("nova prove_step: {e:?}"))?;
        }
        // sanity: recursive proof must verify before compression
        let out = rs
            .verify(&p.pp, steps, &p.z0)
            .map_err(|e| anyhow!("nova RecursiveSNARK::verify: {e:?}"))?;
        debug_assert_eq!(out[0], expected_output(&p.z0, steps));

        let snark = CompressedSNARK::<_, _, _, S1, S2>::prove(&p.pp, &p.pk, &rs)
            .map_err(|e| anyhow!("nova CompressedSNARK::prove: {e:?}"))?;
        Ok(Proof { snark, steps })
    }

    fn verify(v: &Verifier, proof: &Proof) -> Result<bool> {
        Ok(proof.snark.verify(&v.vk, proof.steps, &v.z0).is_ok())
    }

    fn proof_bytes(proof: &Proof) -> Result<Vec<u8>> {
        let mut buf = bincode::serde::encode_to_vec(&proof.snark, BINCODE)
            .map_err(|e| anyhow!("nova proof encode: {e}"))?;
        buf.extend_from_slice(&(proof.steps as u64).to_le_bytes());
        Ok(buf)
    }

    fn proof_from_bytes(_v: &Verifier, bytes: &[u8]) -> Result<Proof> {
        anyhow::ensure!(bytes.len() > 8, "nova proof too short");
        let (body, tail) = bytes.split_at(bytes.len() - 8);
        let steps = u64::from_le_bytes(tail.try_into().unwrap()) as usize;
        let (snark, _) = bincode::serde::decode_from_slice(body, BINCODE)
            .map_err(|e| anyhow!("nova proof decode: {e}"))?;
        Ok(Proof { snark, steps })
    }
}

fn expected_output(z0: &[Scal], steps: usize) -> Scal {
    let mut x = z0[0];
    for _ in 0..steps {
        x = mimc_step_native(x);
    }
    x
}
