#!/usr/bin/env python3
"""Single-image evaluation dashboard for the SwiftZK-Wallet paper.

Driven entirely by the experiment CSVs (Python is used only for stats/figures):

    results/summary_prove.csv     <- analyze.py (from results/raw/prove_*.csv)
    results/summary_verify.csv    <- analyze.py (from results/raw/verify_*.csv, x86 + arm)
    results/raw/exp2_gas.csv      <- hand-entered from `forge test` output
                                     cols: scheme,depth,verification_gas,tx_exec_cost,note

Panels (each degrades to an "awaiting data" placeholder):
    A  proving time vs depth
    B  verification time vs depth (x86 lines + ARM points overlaid)
    C  memory vs depth: prover peak vs verifier peak, both schemes (log-y)
    D  proof size vs verification-key size, per scheme (log-y bars)
    E  EVM cost (Exp 2): decider-verify gas vs raw-proof calldata gas (log-y bars)
    F  verification cost x86 vs ARM (Exp 1 vs Exp 3), latency + peak mem
    G  selection scorecard @ REF_DEPTH

No numbers are invented here.

Usage:  python analysis/dashboard.py            # -> results/dashboard.png
"""
from __future__ import annotations

import datetime as _dt
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.gridspec import GridSpec  # noqa: E402

OUT = "results"
REF_DEPTH = 32          # depth for the selection scorecard (x86 sweep)
ARM_REF_DEPTH = 16      # depth for the x86-vs-ARM comparison (Exp 3 ran 8, 16)

SCHEME_COLOR = {
    "halo2": "#4C78A8",
    "plonky2": "#2A9D8F",
    "nova": "#E45756",
    "supernova": "#F58518",
}
KIND_MARKER = {"recursive": "o", "folding": "s"}


# --------------------------------------------------------------------------- io
def _read(path: str) -> pd.DataFrame:
    p = os.path.join(*path.split("/"))
    return pd.read_csv(p) if os.path.exists(p) else pd.DataFrame()


def load() -> dict[str, pd.DataFrame]:
    sp = _read("results/summary_prove.csv")
    sv = _read("results/summary_verify.csv")
    gas = _read("results/raw/exp2_gas.csv")
    return {
        "prove": sp,
        "verify_x86": sv[sv["host"] == "x86"] if not sv.empty else sv,
        "verify_arm": sv[sv["host"] == "arm"] if not sv.empty else sv,
        "gas": gas,
    }


# ------------------------------------------------------------------- primitives
def _placeholder(ax, title: str, what: str) -> None:
    ax.text(0.5, 0.5, f"awaiting data\n({what})", ha="center", va="center",
            fontsize=10, color="#888", style="italic", transform=ax.transAxes)
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_title(title, fontsize=10, loc="left")


def _c(scheme: str) -> str:
    return SCHEME_COLOR.get(scheme, "#666")


def _depth_axis(ax):
    ax.set_xscale("log", base=2)
    ax.set_xlabel("aggregation depth")
    ax.grid(True, which="both", alpha=0.25)


# ------------------------------------------------------------------------ panels
def panel_prove_time(ax, sp):
    if sp is None or sp.empty:
        return _placeholder(ax, "A. Proving time", "Exp 1")
    for scheme, g in sp.groupby("scheme"):
        g = g.sort_values("depth")
        ax.plot(g["depth"], g["proving_time_ms_mean"], color=_c(scheme),
                marker=KIND_MARKER.get(g["kind"].iloc[0], "o"), ms=5,
                label=f'{scheme} ({g["kind"].iloc[0]})')
        e = g["proving_time_ms_ci95"]
        ax.fill_between(g["depth"], g["proving_time_ms_mean"] - e,
                        g["proving_time_ms_mean"] + e, color=_c(scheme),
                        alpha=0.15, lw=0)
    _depth_axis(ax)
    ax.set_yscale("log")
    ax.set_ylabel("proving time (ms)")
    ax.set_title("A. Proving time  ·  grows with depth", fontsize=10, loc="left")
    ax.legend(fontsize=8)


def panel_verify_time(ax, vx, va):
    if vx is None or vx.empty:
        return _placeholder(ax, "B. Verification time", "Exp 1")
    for scheme, g in vx.groupby("scheme"):
        g = g.sort_values("depth")
        ax.plot(g["depth"], g["verify_time_ms_mean"], color=_c(scheme),
                marker=KIND_MARKER.get(g["kind"].iloc[0], "o"), ms=5,
                label=f'{scheme} — x86')
    if va is not None and not va.empty:
        for scheme, g in va.groupby("scheme"):
            g = g.sort_values("depth")
            ax.scatter(g["depth"], g["verify_time_ms_mean"], color=_c(scheme),
                       marker="*", s=150, edgecolor="black", linewidth=0.6,
                       zorder=5, label=f'{scheme} — ARM')
    _depth_axis(ax)
    ax.set_yscale("log")
    ax.set_ylabel("verification time (ms)")
    ax.set_title("B. Verification time (KEY)  ·  flat in depth; ★ = ARM (Exp 3)",
                 fontsize=10, loc="left")
    ax.legend(fontsize=7, ncol=2)


def panel_memory(ax, sp, vx):
    if sp is None or sp.empty:
        return _placeholder(ax, "C. Memory: prover vs verifier", "Exp 1")
    for scheme, g in sp.groupby("scheme"):
        g = g.sort_values("depth")
        ax.plot(g["depth"], g["peak_mem_mib_mean"], color=_c(scheme),
                ls="-", marker="o", ms=4, label=f"{scheme} — prover")
    if vx is not None and not vx.empty:
        for scheme, g in vx.groupby("scheme"):
            g = g.sort_values("depth")
            ax.plot(g["depth"], g["peak_mem_mib_mean"], color=_c(scheme),
                    ls=":", marker="v", ms=4, label=f"{scheme} — verifier")
    _depth_axis(ax)
    ax.set_yscale("log")
    ax.set_ylabel("peak memory (MiB)")
    ax.set_title("C. Peak memory  ·  prover (—) climbs, verifier (⋯) is flat & tiny",
                 fontsize=10, loc="left")
    ax.legend(fontsize=7, ncol=2)


def panel_sizes(ax, sp):
    need = {"proof_size_kib_mean", "vk_size_kib_mean"}
    if sp is None or sp.empty or not need.issubset(sp.columns):
        return _placeholder(ax, "D. Proof size vs verification-key size", "Exp 1")
    one = (sp.sort_values("depth").groupby("scheme", as_index=False).first())
    schemes = list(one["scheme"])
    x = np.arange(len(schemes))
    w = 0.38
    proof = one["proof_size_kib_mean"].to_numpy()
    vk = one["vk_size_kib_mean"].to_numpy()
    b1 = ax.bar(x - w / 2, proof, w, label="aggregate proof", color="#4C78A8")
    b2 = ax.bar(x + w / 2, vk, w, label="verification key", color="#F58518")
    ax.set_yscale("log")
    ax.set_xticks(x)
    ax.set_xticklabels([f'{s}\n({k})' for s, k in zip(one["scheme"], one["kind"])],
                       fontsize=8)
    ax.set_ylabel("KiB (log)")
    ax.set_title("D. Proof & verification-key size  ·  constant in depth",
                 fontsize=10, loc="left")
    ax.grid(True, axis="y", which="both", alpha=0.25)
    for bars in (b1, b2):
        for b in bars:
            v = b.get_height()
            ax.annotate(f"{v:,.1f}" if v < 100 else f"{v:,.0f}",
                        (b.get_x() + b.get_width() / 2, v), ha="center",
                        va="bottom", fontsize=7)
    ax.legend(fontsize=8)


def panel_evm(ax, gas):
    if gas is None or gas.empty:
        return _placeholder(ax, "E. EVM verification cost (Exp 2)", "Exp 2")
    g = gas.copy()
    g["label"] = g["scheme"] + "\nd=" + g["depth"].astype(str)
    x = np.arange(len(g))
    w = 0.38
    b1 = ax.bar(x - w / 2, g["verification_gas"], w,
                label="Groth16 decider verify (exec)", color="#4C78A8")
    b2 = ax.bar(x + w / 2, g["tx_exec_cost"], w,
                label="raw aggregate-proof post (tx)", color="#F58518")
    ax.set_yscale("log")
    top = float(pd.concat([g["verification_gas"], g["tx_exec_cost"]]).max())
    ax.set_ylim(1e4, top * 3)
    ax.set_xticks(x)
    ax.set_xticklabels(g["label"], fontsize=8)
    ax.set_ylabel("gas (log)")
    ax.set_title("E. EVM cost (Exp 2)  ·  exec ≈ equal; calldata favours folding",
                 fontsize=10, loc="left")
    ax.grid(True, axis="y", which="both", alpha=0.25)
    for bars in (b1, b2):
        for b in bars:
            v = b.get_height()
            ax.annotate(f"{v/1000:,.0f}k", (b.get_x() + b.get_width() / 2, v),
                        ha="center", va="bottom", fontsize=7)
    ax.legend(fontsize=8, loc="upper left")


def panel_x86_vs_arm(ax, vx, va):
    if vx is None or vx.empty or va is None or va.empty:
        return _placeholder(ax, "F. Verification: x86 vs ARM", "Exp 3")
    d = ARM_REF_DEPTH
    x86 = vx[vx["depth"] == d].set_index("scheme")
    arm = va[va["depth"] == d].set_index("scheme")
    schemes = [s for s in ["plonky2", "nova", "halo2", "supernova"] if s in arm.index]
    x = np.arange(len(schemes))
    w = 0.38
    x86v = [x86.loc[s, "verify_time_ms_mean"] if s in x86.index else np.nan for s in schemes]
    armv = [arm.loc[s, "verify_time_ms_mean"] for s in schemes]
    b1 = ax.bar(x - w / 2, x86v, w, label="x86 (Exp 1)", color="#9DB4C0")
    b2 = ax.bar(x + w / 2, armv, w, label="ARM / Neoverse-N1 (Exp 3)", color="#5C6B73")
    ax.set_yscale("log")
    allv = [v for v in x86v + armv if not np.isnan(v)]
    ax.set_ylim(min(allv) * 0.35, max(allv) * 6)
    ax.set_xticks(x)
    ax.set_xticklabels(schemes, fontsize=9)
    ax.set_ylabel("verification latency (ms, log)")
    ax.set_title(f"F. Verification x86 vs ARM @ depth {d}  ·  bar label = ms / peak MiB",
                 fontsize=9.5, loc="left")
    ax.grid(True, axis="y", which="both", alpha=0.25)
    for s, b in zip(schemes, b1):
        m = x86.loc[s, "peak_mem_mib_mean"] if s in x86.index else np.nan
        ax.annotate(f'{b.get_height():.1f}\n{m:.1f}', xy=(b.get_x() + b.get_width() / 2, b.get_height()),
                    xytext=(0, 2), textcoords="offset points",
                    ha="center", va="bottom", fontsize=6.5)
    for s, b in zip(schemes, b2):
        m = arm.loc[s, "peak_mem_mib_mean"]
        ax.annotate(f'{b.get_height():.1f}\n{m:.1f}', xy=(b.get_x() + b.get_width() / 2, b.get_height()),
                    xytext=(0, 2), textcoords="offset points",
                    ha="center", va="bottom", fontsize=6.5)
    ax.legend(fontsize=8, loc="upper left")


def panel_scorecard(ax, sp, vx):
    ax.axis("off")
    ax.set_title(f"G. Selection scorecard @ depth {REF_DEPTH}  "
                 f"(wallet-side; lower = better; ● = best)", fontsize=10, loc="left")
    if sp is None or sp.empty:
        return _placeholder(ax, "", "Exp 1")
    p = sp[sp["depth"] == REF_DEPTH].set_index("scheme")
    v = (vx[vx["depth"] == REF_DEPTH].set_index("scheme")
         if vx is not None and not vx.empty else pd.DataFrame())
    has_vk = "vk_size_kib_mean" in sp.columns

    rows = []
    for s in ["halo2", "plonky2", "nova", "supernova"]:
        if s not in p.index:
            continue
        hv = not v.empty and s in v.index
        rows.append((
            s, p.loc[s, "kind"],
            v.loc[s, "verify_time_ms_mean"] if hv else np.nan,
            v.loc[s, "peak_mem_mib_mean"] if hv else np.nan,
            p.loc[s, "proof_size_kib_mean"],
            p.loc[s, "vk_size_kib_mean"] if has_vk else np.nan,
        ))
    if not rows:
        return _placeholder(ax, "", "Exp 1")
    df = pd.DataFrame(rows, columns=["scheme", "kind", "vt", "vm", "pf", "vk"])
    metric_cols = ["vt", "vm", "pf", "vk"]
    best = {c: (df[c].idxmin() if df[c].notna().any() else None) for c in metric_cols}

    def f_ms(x):
        return f"{x:,.2f}"

    def f_mib(x):
        return f"{x:,.2f}" if x < 10 else f"{x:,.0f}"

    def f_kib(x):
        return f"{x:,.2f}" if x < 100 else f"{x:,.0f}"

    fmt = {"vt": f_ms, "vm": f_mib, "pf": f_kib, "vk": f_kib}
    cells, colors = [], []
    for i, r in df.iterrows():
        rc, cc = [r["scheme"], r["kind"]], ["#f5f5f5", "#f5f5f5"]
        for c in metric_cols:
            val = r[c]
            t = "—" if pd.isna(val) else fmt[c](val)
            if best[c] == i:
                t = "● " + t
                cc.append("#cdebcd")
            else:
                cc.append("#ffffff")
            rc.append(t)
        cells.append(rc)
        colors.append(cc)
    tbl = ax.table(
        cellText=cells, cellColours=colors,
        colLabels=["scheme", "kind", "verify (ms)", "verify mem (MiB)",
                   "proof (KiB)", "vk (KiB)"],
        cellLoc="center", bbox=[0.0, 0.05, 1.0, 0.95])
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    for (row, _), cell in tbl.get_celld().items():
        if row == 0:
            cell.set_text_props(fontweight="bold")


# ------------------------------------------------------------------------- main
def build(out_path: str = os.path.join(OUT, "dashboard.png")) -> str:
    d = load()
    fig = plt.figure(figsize=(16, 10.8))
    gs = GridSpec(3, 3, figure=fig, hspace=0.38, wspace=0.27,
                  height_ratios=[1.0, 1.0, 0.42],
                  top=0.9, bottom=0.055, left=0.06, right=0.985)

    fig.suptitle(
        "SwiftZK-Wallet — Recursive (Plonky2) vs Folding (Nova) ZK Aggregation, "
        "Wallet-Side Verification",
        fontsize=15, fontweight="bold", x=0.06, ha="left", y=0.965)
    fig.text(0.06, 0.933,
             "Exp 1: native x86 depth sweep 2–64  ·  Exp 2: EVM verification cost "
             "(Foundry / BN254)  ·  Exp 3: ARM Neoverse-N1 verification.",
             fontsize=9.5, color="#555", ha="left")

    panel_prove_time(fig.add_subplot(gs[0, 0]), d["prove"])
    panel_verify_time(fig.add_subplot(gs[0, 1]), d["verify_x86"], d["verify_arm"])
    panel_memory(fig.add_subplot(gs[0, 2]), d["prove"], d["verify_x86"])
    panel_sizes(fig.add_subplot(gs[1, 0]), d["prove"])
    panel_evm(fig.add_subplot(gs[1, 1]), d["gas"])
    panel_x86_vs_arm(fig.add_subplot(gs[1, 2]), d["verify_x86"], d["verify_arm"])
    panel_scorecard(fig.add_subplot(gs[2, :]), d["prove"], d["verify_x86"])

    prov = []
    for k, lab in [("prove", "prove"), ("verify_x86", "verify/x86"),
                   ("verify_arm", "verify/arm"), ("gas", "gas")]:
        n = 0 if d[k] is None or d[k].empty else len(d[k])
        prov.append(f"{lab}:{n}")
    fig.text(0.06, 0.015,
             "rows — " + "  |  ".join(prov)
             + f"    ·    generated {_dt.datetime.now():%Y-%m-%d %H:%M}",
             fontsize=8, color="#888", ha="left")

    os.makedirs(OUT, exist_ok=True)
    fig.savefig(out_path, dpi=170)
    plt.close(fig)
    print(f"wrote {out_path}")
    return out_path


if __name__ == "__main__":
    build()
