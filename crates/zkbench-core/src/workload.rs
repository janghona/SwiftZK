//! The identical workload every scheme aggregates, so proving/verification
//! numbers are comparable across Halo2, Plonky2, Nova, and SuperNova.
//!
//! ## Unit step — a MiMC-style permutation (ZK-friendly)
//!
//! One unit step applies `STEP_ROUNDS` rounds of `x <- (x + c_i)^ALPHA` over the
//! backend's *native* prime field, where `c_i` are fixed round constants and
//! `ALPHA = 5`. This is a standard, field-native ZK benchmark: low degree, no
//! bit-decomposition, cheap in PLONK and R1CS alike.
//!
//! ## What is held constant vs. what varies
//!
//! Held constant across all four schemes: the *computational shape* — number of
//! steps (`depth`), rounds per step (`STEP_ROUNDS`), and round degree (`ALPHA`).
//! NOT held constant: the concrete field (each scheme uses its own) and hence
//! the literal output value. Fair comparison is on equal circuit work, not on a
//! shared output. State this in the paper's setup.
//!
//! ## Aggregation
//!
//! Depth `d` chains `d` unit steps: step `i` consumes step `i-1`'s output. The
//! aggregate proof attests to the whole chain `u_0 -> u_1 -> ... -> u_d`.

use serde::{Deserialize, Serialize};

/// Rounds inside ONE unit step. Fixed for the whole study; tune once so a single
/// step is non-trivial but fast, then freeze and record in the paper.
pub const STEP_ROUNDS: usize = 128;

/// Round exponent (S-box). Degree 5 is invertible in all fields used here
/// (gcd(5, p-1) == 1 for Goldilocks, BN254-Fr, Pallas/Vesta-Fr).
pub const ALPHA: u64 = 5;

/// Fixed round constants, generated once from a counter so every backend uses
/// the same sequence (reduced into its own field). Deterministic, no RNG dep.
pub fn round_constant(i: usize) -> u64 {
    // splitmix64 of the round index — used only to fill a constant table.
    let mut z = (i as u64).wrapping_add(0x9E37_79B9_7F4A_7C15);
    z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
    z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
    z ^ (z >> 31)
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize)]
pub struct AggWorkload {
    /// Aggregation depth: number of unit steps folded / recursively composed.
    pub depth: u32,
    /// Deterministic seed for the initial input, so every run and every scheme
    /// starts from the same (index-wise) chain.
    pub seed: u64,
}

impl AggWorkload {
    pub fn new(depth: u32, seed: u64) -> Self {
        Self { depth, seed }
    }
}

// ---------------------------------------------------------------------------
// Reference implementation over a small 61-bit prime. Used ONLY by the `noop`
// self-test scheme and for sanity assertions — NOT by the real adapters, each
// of which implements the round in its native field.
// ---------------------------------------------------------------------------

/// A Mersenne-ish prime < 2^61 so `u128` intermediate products never overflow.
pub const REF_PRIME: u128 = (1u128 << 61) - 1;

fn ref_mul(a: u128, b: u128) -> u128 {
    (a * b) % REF_PRIME
}

fn ref_pow5(x: u128) -> u128 {
    let x2 = ref_mul(x, x);
    let x4 = ref_mul(x2, x2);
    ref_mul(x4, x)
}

/// One MiMC-style unit step over the reference field.
pub fn ref_step(input: u128) -> u128 {
    let mut x = input % REF_PRIME;
    for i in 0..STEP_ROUNDS {
        let c = (round_constant(i) as u128) % REF_PRIME;
        x = ref_pow5((x + c) % REF_PRIME);
    }
    x
}

/// `ref_step` applied `depth` times to `seed`.
pub fn ref_chain_output(w: &AggWorkload) -> u128 {
    let mut x = (w.seed as u128) % REF_PRIME;
    for _ in 0..w.depth {
        x = ref_step(x);
    }
    x
}
