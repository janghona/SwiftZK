#!/usr/bin/env bash
# Experiment 3 — SSH-to-an-ARM-box variant. The primary path is the
# `.github/workflows/exp3-arm.yml` GitHub Actions workflow (no cloud account);
# use this script only if you already have an ARM64 Linux machine to SSH into.
#
# Drive that machine from the dev machine:
# Copies the source + representative proofs, builds on the VM, runs the verifier
# for the best Recursive and best Folding schemes (from Exp 1), pulls the CSVs.
#
# Usage:  scripts/run_exp3_remote.sh ubuntu@<PUBLIC_IP> "plonky2 nova"
set -euo pipefail
cd "$(dirname "$0")/.."

HOST="${1:?usage: run_exp3_remote.sh user@ip \"<recursive> <folding>\"}"
SCHEMES="${2:-plonky2 nova}"
REMOTE_DIR="~/swiftzk"
DEPTHS="${DEPTHS:-8,16}"
RUNS="${RUNS:-100}"

echo "== sync source + proofs to $HOST =="
rsync -az --delete \
  --exclude target --exclude .git --exclude results/raw \
  ./ "$HOST:$REMOTE_DIR/"

for s in $SCHEMES; do
  echo "== [$s] build + verify on VM =="
  ssh "$HOST" "source ~/.cargo/env && cd $REMOTE_DIR && \
    cargo build --release -p zkbench-verifier --features $s && \
    taskset -c 0 systemd-run --scope --quiet -p MemoryMax=2G -p MemoryHigh=1900M \
      ./target/release/zkbench-verifier \
        --scheme $s --host arm --depths $DEPTHS --runs $RUNS --warmup 10 \
        --out-csv results/raw/verify_arm_${s}.csv --proof-dir proofs"

  echo "== [$s] pull CSV =="
  scp "$HOST:$REMOTE_DIR/results/raw/verify_arm_${s}.csv" results/raw/
done

python analysis/analyze.py --figures
echo "done -> results/exp3_table.md, results/fig_exp3.png"
