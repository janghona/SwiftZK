#!/usr/bin/env python3
"""Evaluation dashboard for the SwiftZK-Wallet paper.

Six consolidated panels, driven entirely by the experiment CSVs:

    results/summary_prove.csv     <- analyze.py (from results/raw/prove_*.csv)
    results/summary_verify.csv    <- analyze.py (from results/raw/verify_*.csv, x86 + arm)
    results/raw/verify_*.csv      <- per-run measurements (used by panel E)
    results/raw/exp2_gas.csv      <- hand-entered from `forge test` output

    A  time vs depth        proving vs verification, both schemes, + ARM points
    B  peak memory vs depth prover vs verifier, both schemes, + ARM points
    C  artifact size        aggregate proof & verification key (+ on-chain post cost)
    D  x86 vs ARM           verification latency and peak RSS side by side
    E  per-run distribution box plot of individual verification-time measurements
    F  measurement stability coefficient of variation vs depth

Each panel degrades to an "awaiting data" placeholder. No numbers are invented.
Usage:  python analysis/dashboard.py            # -> results/dashboard.png
"""
from __future__ import annotations

import datetime as _dt
import glob
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.gridspec import GridSpec  # noqa: E402

OUT = "results"
CMP_DEPTH = 16   # depth used for the x86-vs-ARM and distribution panels (Exp 3 ran 8, 16)

SCHEME_COLOR = {"halo2": "#4C78A8", "plonky2": "#2A9D8F",
                "nova": "#E45756", "supernova": "#F58518"}


# --------------------------------------------------------------------------- io
def _read(path: str) -> pd.DataFrame:
    p = os.path.join(*path.split("/"))
    return pd.read_csv(p) if os.path.exists(p) else pd.DataFrame()


def _raw_verify() -> pd.DataFrame:
    files = sorted(glob.glob(os.path.join("results", "raw", "verify_*.csv")))
    if not files:
        return pd.DataFrame()
    df = pd.concat((pd.read_csv(f) for f in files), ignore_index=True)
    return df[df["scheme"] != "noop"]


def load() -> dict:
    sv = _read("results/summary_verify.csv")
    return {
        "prove": _read("results/summary_prove.csv"),
        "verify_x86": sv[sv["host"] == "x86"] if not sv.empty else sv,
        "verify_arm": sv[sv["host"] == "arm"] if not sv.empty else sv,
        "gas": _read("results/raw/exp2_gas.csv"),
        "runs": _raw_verify(),
    }


# ------------------------------------------------------------------- primitives
def _c(s: str) -> str:
    return SCHEME_COLOR.get(s, "#666")


def _ph(ax, title: str, what: str) -> None:
    ax.text(0.5, 0.5, f"awaiting data\n({what})", ha="center", va="center",
            fontsize=10, color="#888", style="italic", transform=ax.transAxes)
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_title(title, fontsize=10, loc="left")


def _depthx(ax):
    ax.set_xscale("log", base=2)
    ax.set_xlabel("aggregation depth")
    ax.grid(True, which="both", alpha=0.25)


# ------------------------------------------------------------------------ panels
def panel_time(ax, sp, vx, va):
    if sp is None or sp.empty:
        return _ph(ax, "A. Time vs depth", "Exp 1")
    for s, g in sp.groupby("scheme"):
        g = g.sort_values("depth")
        ax.plot(g["depth"], g["proving_time_ms_mean"], color=_c(s), ls="-",
                marker="o", ms=4, label=f"{s} — prove")
    if vx is not None and not vx.empty:
        for s, g in vx.groupby("scheme"):
            g = g.sort_values("depth")
            ax.plot(g["depth"], g["verify_time_ms_mean"], color=_c(s), ls=":",
                    marker="v", ms=4, label=f"{s} — verify (x86)")
    if va is not None and not va.empty:
        for s, g in va.groupby("scheme"):
            g = g.sort_values("depth")
            ax.scatter(g["depth"], g["verify_time_ms_mean"], color=_c(s),
                       marker="*", s=140, ec="black", lw=0.6, zorder=6,
                       label=f"{s} — verify (ARM)")
    _depthx(ax)
    ax.set_yscale("log")
    ax.set_ylabel("time (ms, log)")
    ax.set_title("A. Time vs depth", fontsize=10, loc="left")
    ax.legend(fontsize=6.5, ncol=2)


def panel_mem(ax, sp, vx, va):
    if sp is None or sp.empty:
        return _ph(ax, "B. Peak memory vs depth", "Exp 1")
    for s, g in sp.groupby("scheme"):
        g = g.sort_values("depth")
        ax.plot(g["depth"], g["peak_mem_mib_mean"], color=_c(s), ls="-",
                marker="o", ms=4, label=f"{s} — prover")
    if vx is not None and not vx.empty:
        for s, g in vx.groupby("scheme"):
            g = g.sort_values("depth")
            ax.plot(g["depth"], g["peak_mem_mib_mean"], color=_c(s), ls=":",
                    marker="v", ms=4, label=f"{s} — verifier (x86)")
    if va is not None and not va.empty:
        for s, g in va.groupby("scheme"):
            g = g.sort_values("depth")
            ax.scatter(g["depth"], g["peak_mem_mib_mean"], color=_c(s),
                       marker="*", s=140, ec="black", lw=0.6, zorder=6,
                       label=f"{s} — verifier (ARM)")
    _depthx(ax)
    ax.set_yscale("log")
    ax.set_ylabel("peak memory (MiB, log)")
    ax.set_title("B. Peak memory vs depth", fontsize=10, loc="left")
    ax.legend(fontsize=6.5, ncol=2)


def panel_size(ax, sp, gas):
    need = {"proof_size_kib_mean", "vk_size_kib_mean"}
    if sp is None or sp.empty or not need.issubset(sp.columns):
        return _ph(ax, "C. Artifact size & on-chain cost", "Exp 1")
    one = sp.sort_values("depth").groupby("scheme", as_index=False).first()
    schemes = list(one["scheme"])
    x = np.arange(len(schemes))
    w = 0.38
    b1 = ax.bar(x - w / 2, one["proof_size_kib_mean"], w, label="aggregate proof",
                color="#4C78A8")
    b2 = ax.bar(x + w / 2, one["vk_size_kib_mean"], w, label="verification key",
                color="#F58518")
    ax.set_yscale("log")
    ax.set_ylabel("KiB (log)")
    for bars in (b1, b2):
        for b in bars:
            v = b.get_height()
            ax.annotate(f"{v:,.1f}" if v < 100 else f"{v:,.0f}",
                        (b.get_x() + b.get_width() / 2, v), ha="center",
                        va="bottom", fontsize=7)
    # on-chain raw-proof post cost from Exp 2, annotated under each scheme
    labels = []
    for s in schemes:
        gg = gas[(gas["scheme"] == s)] if gas is not None and not gas.empty else pd.DataFrame()
        post = f"{gg['tx_exec_cost'].iloc[0] / 1000:,.0f}k gas" if len(gg) else "—"
        k = one.loc[one["scheme"] == s, "kind"].iloc[0]
        labels.append(f"{s}\n({k})\npost {post}")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=7.5)
    ax.set_title("C. Proof & verification-key size", fontsize=10, loc="left")
    ax.grid(True, axis="y", which="both", alpha=0.25)
    ax.legend(fontsize=8)


def panel_x86_arm(ax, vx, va):
    if vx is None or vx.empty or va is None or va.empty:
        return _ph(ax, "D. Verification: x86 vs ARM", "Exp 3")
    d = CMP_DEPTH
    x86 = vx[vx["depth"] == d].set_index("scheme")
    arm = va[va["depth"] == d].set_index("scheme")
    schemes = [s for s in ["plonky2", "nova", "halo2", "supernova"] if s in arm.index]
    x = np.arange(len(schemes))
    w = 0.38
    lat_x86 = [x86.loc[s, "verify_time_ms_mean"] if s in x86.index else np.nan for s in schemes]
    lat_arm = [arm.loc[s, "verify_time_ms_mean"] for s in schemes]
    b1 = ax.bar(x - w / 2, lat_x86, w, label="latency x86", color="#9DB4C0")
    b2 = ax.bar(x + w / 2, lat_arm, w, label="latency ARM (Neoverse-N2)", color="#5C6B73")
    ax.set_yscale("log")
    allv = [v for v in lat_x86 + lat_arm if not np.isnan(v)]
    ax.set_ylim(min(allv) * 0.3, max(allv) * 8)
    ax.set_ylabel("verification latency (ms, log)")

    ax2 = ax.twinx()
    mem_x86 = [x86.loc[s, "peak_mem_mib_mean"] if s in x86.index else np.nan for s in schemes]
    mem_arm = [arm.loc[s, "peak_mem_mib_mean"] for s in schemes]
    ax2.scatter(x - w / 2, mem_x86, marker="o", s=55, color="#1b4965",
                ec="white", lw=0.8, zorder=6, label="peak RSS x86")
    ax2.scatter(x + w / 2, mem_arm, marker="s", s=55, color="#e07a1f",
                ec="white", lw=0.8, zorder=6, label="peak RSS ARM")
    ax2.set_ylabel("peak RSS (MiB)")
    ax2.set_ylim(0, max(v for v in mem_x86 + mem_arm if not np.isnan(v)) * 1.6)

    ax.set_xticks(x)
    ax.set_xticklabels(schemes, fontsize=9)
    ax.set_title("D. Verification: x86 vs ARM", fontsize=10, loc="left")
    ax.grid(True, axis="y", which="both", alpha=0.25)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, fontsize=6.5, ncol=2, loc="upper left")


def panel_dist(ax, runs):
    """Per-run spread. Absolute verify times span 50x across groups, so plot
    each run as % deviation from its own group median — puts all groups on one
    readable linear axis and shows the actual run-to-run noise."""
    if runs is None or runs.empty:
        return _ph(ax, "E. Per-run verification time", "Exp 1/3")
    d = CMP_DEPTH
    sub = runs[runs["depth"] == d]
    groups, labels, colors = [], [], []
    for host in ("x86", "arm"):
        for s in ("plonky2", "nova"):
            v = sub[(sub["host"] == host) & (sub["scheme"] == s)]["verify_time_ms"].to_numpy()
            if len(v):
                med = float(np.median(v))
                groups.append((v - med) / med * 100.0)
                labels.append(f"{s} / {host}\nN={len(v)}\nmed {med:.3g} ms")
                colors.append(_c(s))
    if not groups:
        return _ph(ax, "E. Per-run verification time", "Exp 1/3")
    pos = np.arange(len(groups))
    rng = np.random.default_rng(0)
    for i, (v, col) in enumerate(zip(groups, colors)):
        ax.scatter(np.full(len(v), i) + rng.normal(0, 0.08, len(v)), v,
                   s=10, color=col, alpha=0.35, lw=0, zorder=2)
    bp = ax.boxplot(groups, positions=pos, widths=0.5, showfliers=False,
                    patch_artist=True, zorder=3)
    for patch, col in zip(bp["boxes"], colors):
        patch.set_facecolor(col); patch.set_alpha(0.55)
    for med in bp["medians"]:
        med.set_color("black")
    ax.axhline(0, color="#888", lw=0.8, zorder=1)
    ax.set_xticks(pos)
    ax.set_xticklabels(labels, fontsize=7.5)
    ax.set_ylabel("per-run deviation from median (%)")
    ax.set_title("E. Per-run verification spread", fontsize=10, loc="left")
    ax.grid(True, axis="y", alpha=0.25)


def panel_cv(ax, sp, vx, va):
    if sp is None or sp.empty:
        return _ph(ax, "F. Measurement stability (CV)", "Exp 1")
    for s, g in sp.groupby("scheme"):
        g = g.sort_values("depth")
        ax.plot(g["depth"], g["proving_time_ms_cv"] * 100, color=_c(s), ls="-",
                marker="o", ms=4, label=f"{s} — prove time")
    if vx is not None and not vx.empty:
        for s, g in vx.groupby("scheme"):
            g = g.sort_values("depth")
            ax.plot(g["depth"], g["verify_time_ms_cv"] * 100, color=_c(s), ls=":",
                    marker="v", ms=4, label=f"{s} — verify time (x86)")
    if va is not None and not va.empty:
        for s, g in va.groupby("scheme"):
            g = g.sort_values("depth")
            ax.scatter(g["depth"], g["verify_time_ms_cv"] * 100, color=_c(s),
                       marker="*", s=130, ec="black", lw=0.6, zorder=6,
                       label=f"{s} — verify (ARM)")
    ax.axhline(10, color="#c00", lw=0.8, ls="--", alpha=0.6)
    ax.text(2.05, 10.8, "10%", color="#c00", fontsize=7, va="bottom")
    ax.annotate("nova d=2: cold-start warmup artifact", xy=(4.2, 55),
                fontsize=6.5, color="#888", ha="left", va="center")
    ax.annotate("plonky2 prove d=32:\nhost noise", xy=(20, 18), xytext=(9, 30),
                fontsize=6.5, color="#888",
                arrowprops=dict(arrowstyle="->", color="#aaa", lw=0.7))
    _depthx(ax)
    ax.set_ylabel("coefficient of variation (%)")
    ax.set_title("F. Timing stability (CV)", fontsize=10, loc="left")
    ax.legend(fontsize=6.5, ncol=2, loc="upper right")


# ------------------------------------------------------------------------- main
def build(out_path: str = os.path.join(OUT, "dashboard.png")) -> str:
    d = load()
    fig = plt.figure(figsize=(16.5, 9))
    gs = GridSpec(2, 3, figure=fig, hspace=0.44, wspace=0.32,
                  top=0.945, bottom=0.09, left=0.055, right=0.955)

    panel_time(fig.add_subplot(gs[0, 0]), d["prove"], d["verify_x86"], d["verify_arm"])
    panel_mem(fig.add_subplot(gs[0, 1]), d["prove"], d["verify_x86"], d["verify_arm"])
    panel_size(fig.add_subplot(gs[0, 2]), d["prove"], d["gas"])
    panel_x86_arm(fig.add_subplot(gs[1, 0]), d["verify_x86"], d["verify_arm"])
    panel_dist(fig.add_subplot(gs[1, 1]), d["runs"])
    panel_cv(fig.add_subplot(gs[1, 2]), d["prove"], d["verify_x86"], d["verify_arm"])

    prov = []
    for k, lab in [("prove", "prove"), ("verify_x86", "verify/x86"),
                   ("verify_arm", "verify/arm"), ("gas", "gas"), ("runs", "runs")]:
        n = 0 if d[k] is None or d[k].empty else len(d[k])
        prov.append(f"{lab}:{n}")
    fig.text(0.06, 0.02,
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
