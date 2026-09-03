# Adapter integration notes

Each adapter implements `zkbench_core::Scheme` for one scheme. Implement one,
enable its feature, benchmark, repeat. **No fabricated numbers** — a stub panics
rather than returning a fake measurement.

Toolchain: `rust-toolchain.toml` pins `nightly-2026-09-02` (Plonky2 needs it).

Shared workload (`workload.rs`): unit step = `STEP_ROUNDS` rounds of the
MiMC-style permutation `x <- (x + c_i)^5` over the backend's **native** prime
field; aggregation depth `d` chains `d` steps. Round constants come from
`workload::round_constant(i)` (reduce into the native field). Hold the
*computational shape* constant (steps, rounds, degree); the concrete field and
literal output differ per backend — that is expected and stated in the paper.

Status: **Plonky2 — implemented** (`adapters/plonky2.rs`, recursion).
**Nova — implemented** (`adapters/nova.rs`, folding). Halo2 and SuperNova are
NOT benchmarked (project decision); their stubs remain for reference and the
paper covers them analytically.

## Recursive

### Halo2 (`--features halo2`)
- Crates: `halo2_proofs` (PSE fork), `halo2curves`; KZG/BN256.
- Unit circuit: splitmix64 chip. Aggregation: in-circuit verification of the
  previous proof (accumulation); compose `d` deep. Final = one Halo2 proof.
- `proof_bytes`: transcript bytes + serialized instances.
- EVM (Exp 2): `halo2-solidity-verifier` Yul verifier.

### Plonky2 (`--features plonky2`) — IMPLEMENTED
- Crate: `plonky2` 1.1 (Polygon Zero); Goldilocks, `PoseidonGoldilocksConfig`.
- Structure: linear recursion chain — leaf proves one MiMC step (`[u0,u1]`);
  wrap `i` verifies wrap `i-1` in-circuit + one MiMC step, exposes `[u0,u_i]`.
- Circuits built once in `setup` (untimed), reused across runs.
- `proof_bytes`: `ProofWithPublicInputs::to_bytes` (uncompressed FRI proof;
  ~127 KB, constant in `d`). Verification ~constant in `d`.
- EVM (Exp 2): no native verifier — documented limitation or Groth16-wrap.

## Folding

### Nova (`--features nova`)
- Crate: `nova-snark` (Microsoft) or `sonobe` (folding-schemes).
- Step circuit `F` = one unit step. Fold `d` steps into the running relaxed-R1CS
  instance/witness, then **decider** = `CompressedSNARK`.
- **Exp 3 / Exp 2 measure the decider (compressed-SNARK) verification**, not the
  per-step folding verifier. State this in the paper.
- `proof_bytes`: serialized `CompressedSNARK` + final instance.
- EVM (Exp 2): `sonobe` `NovaDecider` Solidity export (Groth16), or snarkjs.

### SuperNova (`--features supernova`)
- Crate: `nova-snark` SuperNova API, or `sonobe`.
- Small set of step circuits (2 unit-step variants, round-robin) so the
  non-uniform IVC path is exercised; total work matches Nova. Decider as above.

## Checklist per adapter
1. `setup` builds params/keys (not timed).
2. `prove` returns the aggregated/decider proof for `w.depth`.
3. `verify` is exactly what a wallet / EVM verifier runs.
4. `proof_bytes` / `proof_from_bytes` round-trip; size is minimal & canonical.
5. `cargo run --release -p zkbench-prover --features <s> -- --scheme <s> --depths 2 --runs 2`
   completes and the proof verifies.
