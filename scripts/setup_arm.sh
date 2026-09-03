#!/usr/bin/env bash
# Provision an Oracle Cloud "Always Free" Ampere A1 (aarch64 Ubuntu) instance as
# the Experiment 3 mobile proxy. Run this ON the VM after first SSH login.
set -euo pipefail

echo "== apt =="
sudo apt-get update -y
sudo apt-get install -y build-essential pkg-config libssl-dev git

echo "== rust (nightly; pinned by rust-toolchain.toml) =="
if ! command -v cargo >/dev/null; then
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
fi
# shellcheck disable=SC1090
source "$HOME/.cargo/env"
rustup toolchain install nightly-2026-09-02 --profile minimal || true
rustc --version
uname -m   # expect: aarch64

echo "== cpu / memory budget helpers =="
# performance governor if available (best-effort; ignore on VMs without cpufreq)
sudo cpupower frequency-set -g performance 2>/dev/null || true
# systemd-run is used at RUN time to cap memory:
#   taskset -c 0 systemd-run --scope -p MemoryMax=2G -p MemoryHigh=1900M <cmd>
command -v systemd-run >/dev/null && echo "systemd-run OK" || echo "WARN: no systemd-run"
command -v taskset >/dev/null && echo "taskset OK" || echo "WARN: no taskset (apt install util-linux)"

echo "== done. Record for the paper: =="
echo "  instance shape, OCPU count, RAM, region"
echo "  $(uname -srm)"
echo "  $(rustc --version)"
