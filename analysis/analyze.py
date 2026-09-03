#!/usr/bin/env python3
"""Aggregate raw benchmark CSVs into per-(scheme, depth) summary statistics.

Python is used ONLY for statistics and figures. It never runs a ZK system.

Inputs  (results/raw/):
    prove_<scheme>.csv        columns: scheme,kind,depth,run,proving_time_ms,peak_mem_bytes,proof_size_bytes
    verify_<host>_<scheme>.csv columns: scheme,kind,depth,run,verify_time_ms,peak_mem_bytes,proof_size_bytes,host

Outputs (results/):
    summary_prove.csv         mean/std/ci95/cv per (scheme, depth)
    summary_verify.csv        mean/std/ci95/cv per (scheme, depth, host)
    exp1_table.md / exp3_table.md   paper-ready tables (numbers only after real runs)
"""
from __future__ import annotations

import argparse
import glob
import os

import numpy as np
import pandas as pd

RAW = os.path.join("results", "raw")
OUT = "results"


def _agg(df: pd.DataFrame, value_col: str, keys: list[str]) -> pd.DataFrame:
    """mean, sample std, 95% CI half-width (normal approx), coeff. of variation."""
    rows = []
    for key_vals, g in df.groupby(keys):
        x = g[value_col].to_numpy(dtype=float)
        n = len(x)
        mean = float(np.mean(x))
        std = float(np.std(x, ddof=1)) if n > 1 else 0.0
        ci95 = 1.96 * std / np.sqrt(n) if n > 1 else 0.0
        cv = (std / mean) if mean else 0.0
        rec = dict(zip(keys, key_vals if isinstance(key_vals, tuple) else (key_vals,)))
        rec.update(n=n, **{
            f"{value_col}_mean": mean,
            f"{value_col}_std": std,
            f"{value_col}_ci95": ci95,
            f"{value_col}_cv": cv,
        })
        rows.append(rec)
    return pd.DataFrame(rows).sort_values(keys).reset_index(drop=True)


def load_prove() -> pd.DataFrame:
    files = sorted(glob.glob(os.path.join(RAW, "prove_*.csv")))
    if not files:
        return pd.DataFrame()
    df = pd.concat((pd.read_csv(f) for f in files), ignore_index=True)
    return df[df["scheme"] != "noop"]


def load_verify() -> pd.DataFrame:
    files = sorted(glob.glob(os.path.join(RAW, "verify_*.csv")))
    if not files:
        return pd.DataFrame()
    df = pd.concat((pd.read_csv(f) for f in files), ignore_index=True)
    return df[df["scheme"] != "noop"]


def summarize_prove(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    keys = ["scheme", "kind", "depth"]
    t = _agg(df, "proving_time_ms", keys)
    m = _agg(df, "peak_mem_bytes", keys)
    s = _agg(df, "proof_size_bytes", keys)
    out = t.merge(m, on=keys + ["n"]).merge(s, on=keys + ["n"])
    out["peak_mem_mib_mean"] = out["peak_mem_bytes_mean"] / 2**20
    out["proof_size_kib_mean"] = out["proof_size_bytes_mean"] / 2**10
    if "vk_size_bytes" in df:
        vk = df.groupby(keys)["vk_size_bytes"].first().reset_index()
        out = out.merge(vk, on=keys)
        out["vk_size_kib_mean"] = out["vk_size_bytes"] / 2**10
    return out


def summarize_verify(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    keys = ["scheme", "kind", "depth", "host"]
    t = _agg(df, "verify_time_ms", keys)
    m = _agg(df, "peak_mem_bytes", keys)
    s = _agg(df, "proof_size_bytes", keys)
    out = t.merge(m, on=keys + ["n"]).merge(s, on=keys + ["n"])
    out["peak_mem_mib_mean"] = out["peak_mem_bytes_mean"] / 2**20
    return out


def md_table_exp1(sp: pd.DataFrame, sv: pd.DataFrame) -> str:
    """Two tables: (a) wallet-side verification cost (the selection basis),
    (b) prover-side cost (context)."""
    if sp.empty:
        return "_No Experiment 1 data yet. Run zkbench-prover / zkbench-verifier._\n"
    vx = sv[sv["host"] == "x86"] if not sv.empty else pd.DataFrame()
    has_vk = "vk_size_kib_mean" in sp

    a = ["**Table 1a — Wallet-side verification (x86), mean ± 95% CI.**", "",
         "| Scheme | Kind | Depth | Verify (ms) | Verify Peak Mem (MiB) | Proof (KiB) | VK (KiB) |",
         "|---|---|---:|---:|---:|---:|---:|"]
    for _, r in sp.sort_values(["kind", "scheme", "depth"]).iterrows():
        vr = vx[(vx["scheme"] == r["scheme"]) & (vx["depth"] == r["depth"])]
        if len(vr):
            vt = f'{vr["verify_time_ms_mean"].iloc[0]:.3f} ± {vr["verify_time_ms_ci95"].iloc[0]:.3f}'
            vm = f'{vr["peak_mem_mib_mean"].iloc[0]:.2f}'
        else:
            vt = vm = "—"
        vk = f'{r["vk_size_kib_mean"]:.2f}' if has_vk else "—"
        a.append(
            f'| {r["scheme"]} | {r["kind"]} | {int(r["depth"])} | {vt} | {vm} '
            f'| {r["proof_size_kib_mean"]:.2f} | {vk} |'
        )

    b = ["", "**Table 1b — Prover-side cost (x86), mean ± 95% CI.**", "",
         "| Scheme | Kind | Depth | Prove (ms) | Prove Peak Mem (MiB) |",
         "|---|---|---:|---:|---:|"]
    for _, r in sp.sort_values(["kind", "scheme", "depth"]).iterrows():
        b.append(
            f'| {r["scheme"]} | {r["kind"]} | {int(r["depth"])} '
            f'| {r["proving_time_ms_mean"]:.1f} ± {r["proving_time_ms_ci95"]:.1f} '
            f'| {r["peak_mem_mib_mean"]:.1f} |'
        )
    return "\n".join(a + b) + "\n"


def load_gas() -> pd.DataFrame:
    """Exp 2 results, hand-entered from `forge test` output.
    cols: scheme,depth,verification_gas,tx_exec_cost,note"""
    p = os.path.join(RAW, "exp2_gas.csv")
    return pd.read_csv(p) if os.path.exists(p) else pd.DataFrame()


def md_table_exp2(gas: pd.DataFrame) -> str:
    if gas is None or gas.empty:
        return "_No Experiment 2 data yet. Run `forge test --gas-report` and record results/raw/exp2_gas.csv._\n"
    lines = [
        "| Scheme | Depth | Verification Gas | Tx/Execution Cost | Note |",
        "|---|---:|---:|---:|---|",
    ]
    for _, r in gas.sort_values(["scheme", "depth"]).iterrows():
        lines.append(
            f'| {r["scheme"]} | {int(r["depth"])} | {int(r["verification_gas"]):,} '
            f'| {int(r["tx_exec_cost"]):,} | {r.get("note", "")} |'
        )
    return "\n".join(lines) + "\n"


def md_table_exp3(sv: pd.DataFrame) -> str:
    arm = sv[sv["host"] == "arm"] if not sv.empty else pd.DataFrame()
    if arm.empty:
        return "_No Experiment 3 (ARM) data yet. Run zkbench-verifier --host arm on the Ampere A1 VM._\n"
    lines = [
        "| Scheme | Kind | Depth | Verify Latency (ms) | Peak Mem (MiB) |",
        "|---|---|---:|---:|---:|",
    ]
    for _, r in arm.iterrows():
        lines.append(
            f'| {r["scheme"]} | {r["kind"]} | {int(r["depth"])} '
            f'| {r["verify_time_ms_mean"]:.3f} ± {r["verify_time_ms_ci95"]:.3f} '
            f'| {r["peak_mem_mib_mean"]:.1f} |'
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--figures", action="store_true", help="also render PNG figures")
    args = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    prove, verify = load_prove(), load_verify()
    sp, sv = summarize_prove(prove), summarize_verify(verify)

    if not sp.empty:
        sp.to_csv(os.path.join(OUT, "summary_prove.csv"), index=False)
        print("wrote results/summary_prove.csv")
    if not sv.empty:
        sv.to_csv(os.path.join(OUT, "summary_verify.csv"), index=False)
        print("wrote results/summary_verify.csv")

    gas = load_gas()
    with open(os.path.join(OUT, "exp1_table.md"), "w", encoding="utf-8") as f:
        f.write(md_table_exp1(sp, sv))
    with open(os.path.join(OUT, "exp2_table.md"), "w", encoding="utf-8") as f:
        f.write(md_table_exp2(gas))
    with open(os.path.join(OUT, "exp3_table.md"), "w", encoding="utf-8") as f:
        f.write(md_table_exp3(sv))
    print("wrote results/exp1_table.md, results/exp2_table.md, results/exp3_table.md")

    if args.figures:
        from figures import render_all
        from dashboard import build as build_dashboard

        render_all(sp, sv, OUT)
        build_dashboard()


if __name__ == "__main__":
    main()
