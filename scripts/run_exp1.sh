#!/usr/bin/env bash
# Experiment 1 (x86 native, release) — full depth sweep for every scheme, plus
# x86 verification rows. Produces results/raw/*.csv and proofs/*.bin.
#
# Prereq: each adapter in crates/zkbench-core/src/adapters/ implemented and its
# feature enabled below. Until then this runs only for schemes you pass in.
set -euo pipefail
cd "$(dirname "$0")/.."

SCHEMES=("${@:-halo2 plonky2 nova supernova}")
RUNS_PROVE="${RUNS_PROVE:-20}"
RUNS_VERIFY="${RUNS_VERIFY:-100}"
WARMUP="${WARMUP:-3}"

mkdir -p results/raw proofs

for s in ${SCHEMES[@]}; do
  echo "=== $s : prove sweep ==="
  cargo run --release -p zkbench-prover --features "$s" -- \
    --scheme "$s" --runs "$RUNS_PROVE" --warmup "$WARMUP" \
    --out-csv "results/raw/prove_${s}.csv" --proof-dir proofs

  echo "=== $s : verify (x86) ==="
  cargo run --release -p zkbench-verifier --features "$s" -- \
    --scheme "$s" --host x86 --runs "$RUNS_VERIFY" --warmup 10 \
    --out-csv "results/raw/verify_x86_${s}.csv" --proof-dir proofs
done

python analysis/analyze.py --figures
echo "done -> results/summary_*.csv, results/exp1_table.md, results/fig_exp1.png"
