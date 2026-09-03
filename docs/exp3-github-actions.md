# Experiment 3 — mobile-class ARM verification via GitHub Actions

No cloud account, no VM to provision. GitHub already operates ARM runners
(`ubuntu-24.04-arm` = Ampere Altra / Neoverse-N1); the workflow rents one per
run and throws it away.

## One-time: put the repo on GitHub

```bash
cd /c/Users/janghona/PycharmProjects/SwiftZK
git init -b main
git add -A
git commit -m "SwiftZK-Wallet: harness, Exp1+Exp2 results, paper draft"
# create an EMPTY repo named SwiftZK on github.com (Public = free ARM minutes),
# do NOT add a README/.gitignore there, then:
git remote add origin https://github.com/<you>/SwiftZK.git
git push -u origin main
```

Public repo → ARM runner minutes are free and unmetered. A private repo also
works but consumes included Actions minutes.

## Run it

The push above triggers `exp3-arm` automatically (it watches `crates/**`,
`Cargo.lock`, `analysis/**`, and the workflow file). Or run it by hand:
GitHub → **Actions** tab → **exp3-arm** → **Run workflow**.

The job (~15–40 min, mostly the first cold build):

1. records the ARM host (`lscpu`, `/proc/meminfo`) for the paper
2. installs `nightly-2026-09-02`, builds `zkbench-verifier` with `plonky2,nova`
3. regenerates the `d ∈ {8, 16}` proofs on the runner (deterministic)
4. `taskset -c 0 zkbench-verifier --host arm` — 20 warmup + 200 measured runs
5. runs `analysis/analyze.py --figures`
6. uploads an **`exp3-arm-results`** artifact

## Collect the results

Actions → the finished run → **Artifacts** → download `exp3-arm-results`.
Extract into the repo:

```
results/raw/verify_arm_plonky2.csv
results/raw/verify_arm_nova.csv
```

Then locally:

```bash
python analysis/analyze.py --figures
```

→ fills `results/exp3_table.md` and dashboard panel F. Paste the host `lscpu`
line from `results_host_info.md` into paper Table 4, and the Table 3 numbers
into §6.4.

## Tuning

Workflow `env:` — `VERIFY_RUNS` (default 200), `VERIFY_WARMUP` (20),
`DEPTHS` (`8,16`). Bump runs if the coefficient of variation reported by
`analyze.py` is high (shared CI VM).
