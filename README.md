# SwiftZK-Wallet

Reproduction package for *"SwiftZK-Wallet: Lightweight ZK Aggregation for
Blockchain-Connected Mobile Wallets"* (target: ICT Express, ~6 pp).

**Core question.** Which ZK aggregation approach — recursive (Halo2, Plonky2) or
folding (Nova, SuperNova) — is most suitable for lightweight verification in a
blockchain-connected mobile wallet?

## Layout

| Path | Purpose |
|---|---|
| `crates/zkbench-core` | shared workload, `Scheme` trait, measurement harness |
| `crates/zkbench-core/src/adapters` | one adapter per scheme (Halo2/Plonky2/Nova/SuperNova) |
| `crates/zkbench-prover` | **Exp 1** driver: proving-time / memory / proof-size sweep |
| `crates/zkbench-verifier` | verification driver — **Exp 1** (`--host x86`) and **Exp 3** (`--host arm`) |
| `evm/` | **Exp 2**: Foundry gas harness for EVM verification (separate, manual) |
| `analysis/` | Python: CSV → statistics → tables/figures + `dashboard.py` (no ZK in Python) |
| `scripts/` | `run_exp1.sh`; `run_exp3_remote.sh` + `setup_arm.sh` (SSH-to-an-ARM-box alternative to the CI workflow) |
| `.github/workflows/exp3-arm.yml` | **Exp 3** on a GitHub-hosted ARM runner |
| `docs/adapters.md` | how to wire in each ZK backend |
| `paper/` | the manuscript draft |

## Experiments

1. **ZK benchmark** (native Rust, release, one x86 machine). Depths 2,4,8,16,32,64.
   Metrics: proving time, verification time, peak memory, proof size. Repeated
   runs, mean/variance. → `scripts/run_exp1.sh`
2. **Blockchain validation** (Solidity + Foundry/Anvil). Representative proofs
   through an EVM verifier. Metrics: verification gas, tx/execution cost.
   → `evm/README.md`
3. **Mobile validation** (ARM: Oracle Ampere A1 aarch64, 1 vCPU, 2 GB budget).
   Best recursive + best folding only. Metrics: verification latency, memory.
   → `scripts/run_exp3_remote.sh user@ip "<recursive> <folding>"`

## Toolchain

`rust-toolchain.toml` pins **`nightly-2026-09-02`** — Plonky2 (`plonky2_field`)
needs the nightly `specialization` feature, so the whole workspace uses nightly.
`cargo` picks it up automatically; the ARM VM needs the same (`scripts/setup_arm.sh`).

## Status

| Piece | State |
|---|---|
| Harness, CSV schema, analysis, dashboard, EVM/remote plumbing | complete |
| Workload | MiMC-style permutation (`x <- (x+c_i)^5`, `STEP_ROUNDS` rounds), field-native |
| **Plonky2 adapter** (recursion) | **implemented** — linear recursion chain (leaf + `d-1` wraps) |
| **Nova adapter** (folding) | **implemented** — nova-snark 0.75, Pallas/Vesta + IPA, Spartan decider |
| **Experiment 1** | **DONE** — full sweep d=2..64, `results/exp1_table.md`, `results/dashboard.png` |
| Halo2 / SuperNova | not benchmarked (project decision) — discussed analytically in the paper |
| **Experiment 2 (EVM)** | **DONE** — Foundry, BN254 precompiles; `results/raw/exp2_gas.csv`, paper §6.3 |
| Experiment 3 (ARM) | pending — runs on a GitHub-hosted `ubuntu-24.04-arm` runner via `.github/workflows/exp3-arm.yml` (no cloud account). See `docs/exp3-github-actions.md` |

Comparison scope: **recursion (Plonky2) vs folding (Nova)**.

- **Exp 1 (wallet-side):** recursion verifies ~34× faster, ~84× less verifier
  memory, ~5600× smaller verification key, all flat in depth; folding wins proof
  size (~13×) and prover scalability.
- **Exp 2 (on-chain):** Groth16-wrapped decider verification is ~202 k gas for
  either family; posting the *raw* aggregate proof as calldata is ~177 k gas
  (Nova) vs ~2.05 M gas (Plonky2) — folding's on-chain advantage mirrors
  recursion's wallet-side one.

## Quick plumbing check

```
cargo run --release -p zkbench-prover  --features noop -- --scheme noop --runs 3 \
  --out-csv results/raw/prove_noop.csv --proof-dir proofs
cargo run --release -p zkbench-verifier --features noop -- --scheme noop --host x86 \
  --depths 8,16 --runs 5 --out-csv results/raw/verify_noop.csv --proof-dir proofs
python analysis/analyze.py --figures     # -> results/dashboard.png + tables
```

## Real run — Plonky2 (Experiment 1)

```
bash scripts/run_exp1.sh plonky2        # full depth sweep 2..64, prove + x86 verify
python analysis/analyze.py --figures    # dashboard + exp1_table.md with real numbers
```
