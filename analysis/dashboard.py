#!/usr/bin/env python3
"""Single-image evaluation dashboard for the SwiftZK-Wallet paper.

Driven entirely by the experiment CSVs (Python is used only for stats/figures):

    results/summary_prove.csv     <- analyze.py (from results/raw/prove_*.csv)
    results/summary_verify.csv    <- analyze.py (from results/raw/verify_*.csv)
    results/raw/exp2_gas.csv      <- hand-entered from `forge test` output
                                     cols: scheme,depth,verification_gas,tx_exec_cost,note

Every panel degrades gracefully to an "awaiting data" placeholder so the layout
can be reviewed before the runs are complete. No numbers are invented here.

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
REF_DEPTH = 32  # depth at which the selection scorecard is computed

SCHEME_COLOR = {
    "halo2": "#4C78A8",
    "plonky2": "#72B7B2",
    "nova": "#E45756",
    "supernova": "#F58518",
}
KIND_STYLE = {"recursive": "-", "folding": "--"}
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
def _placeholder(ax, msg: str) -> None:
    ax.text(0.5, 0.5, msg, ha="center", va="center", fontsize=10,
            color="#888", style="italic", transform=ax.transAxes, wrap=True)
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)


def _line_panel(ax, df, ycol, title, ylabel, logx=True, logy=False):
    if df is None or df.empty or ycol not in df:
        _placeholder(ax, f"awaiting data\n({title})")
        ax.set_title(title, fontsize=10, loc="left")
        return
    for scheme, g in df.groupby("scheme"):
        g = g.sort_values("depth")
        kind = g["kind"].iloc[0]
        c = SCHEME_COLOR.get(scheme, "#666")
        ax.plot(g["depth"], g[ycol], color=c,
                linestyle=KIND_STYLE.get(kind, "-"),
                marker=KIND_MARKER.get(kind, "o"), markersize=4, label=scheme)
        err = ycol.replace("_mean", "_ci95")
        if err in g:
            ax.fill_between(g["depth"], g[ycol] - g[err], g[ycol] + g[err],
                            color=c, alpha=0.15, linewidth=0)
    if logx:
        ax.set_xscale("log", base=2)
    if logy:
        ax.set_yscale("log")
    ax.set_xlabel("aggregation depth")
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontsize=10, loc="left")
    ax.grid(True, which="both", alpha=0.25)
    ax.legend(fontsize=8, ncol=2, loc="best", framealpha=0.9)


def _gas_panel(ax, gas: pd.DataFrame):
    if gas is None or gas.empty:
        _placeholder(ax, "awaiting data\n(Exp 2 — EVM gas)")
        ax.set_title("E. EVM verification cost", fontsize=10, loc="left")
        return
    g = gas.copy()
    g["label"] = g["scheme"] + "\nd=" + g["depth"].astype(str)
    x = np.arange(len(g))
    w = 0.38
    ax.bar(x - w / 2, g["verification_gas"], w,
           label="Groth16 decider verify (exec)", color="#4C78A8")
    ax.bar(x + w / 2, g["tx_exec_cost"], w,
           label="raw aggregate-proof post (tx)", color="#F58518")
    ax.set_xticks(x)
    ax.set_xticklabels(g["label"], fontsize=8)
    ax.set_ylabel("gas")
    ax.set_title("E. EVM verification cost (Exp 2)", fontsize=10, loc="left")
    ax.legend(fontsize=8)
    ax.grid(True, axis="y", alpha=0.25)


def _arm_panel(ax, arm: pd.DataFrame):
    if arm is None or arm.empty:
        _placeholder(ax, "awaiting data\n(Exp 3 — ARM verify)")
        ax.set_title("F. ARM mobile-class verification (Exp 3)", fontsize=10, loc="left")
        return
    a = arm.sort_values(["kind", "depth"]).copy()
    a["label"] = a["scheme"] + "\nd=" + a["depth"].astype(str)
    x = np.arange(len(a))
    colors = [SCHEME_COLOR.get(s, "#666") for s in a["scheme"]]
    bars = ax.bar(x, a["verify_time_ms_mean"], 0.6, color=colors,
                  yerr=a.get("verify_time_ms_ci95"), capsize=3)
    ax.set_ylim(0, a["verify_time_ms_mean"].max() * 1.25)
    for b, (_, r) in zip(bars, a.iterrows()):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() * 0.5,
                f'{r["peak_mem_mib_mean"]:.0f}\nMiB', va="center", ha="center",
                fontsize=7, color="white", fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(a["label"], fontsize=8)
    ax.set_ylabel("verify latency (ms)")
    ax.set_title("F. ARM verify latency (Exp 3)  ·  in-bar = peak mem",
                 fontsize=10, loc="left")
    ax.grid(True, axis="y", alpha=0.25)


def _scorecard(ax, prove: pd.DataFrame, vx: pd.DataFrame):
    """Rank schemes on wallet-side (verify time, verify peak mem, proof size)
    at REF_DEPTH. Memory here is the VERIFIER's peak, not the prover's."""
    ax.axis("off")
    ax.set_title(f"G. Selection scorecard @ depth {REF_DEPTH}  "
                 f"(wallet-side; lower = better; ● = best)", fontsize=10, loc="left")
    if prove is None or prove.empty:
        _placeholder(ax, "awaiting data (Exp 1)")
        return

    p = prove[prove["depth"] == REF_DEPTH].set_index("scheme")
    v = (vx[vx["depth"] == REF_DEPTH].set_index("scheme")
         if vx is not None and not vx.empty else pd.DataFrame())

    rows = []
    for scheme in ["halo2", "plonky2", "nova", "supernova"]:
        if scheme not in p.index:
            continue
        has_v = not v.empty and scheme in v.index
        vt = v.loc[scheme, "verify_time_ms_mean"] if has_v else np.nan
        vm = v.loc[scheme, "peak_mem_mib_mean"] if has_v else np.nan
        rows.append((
            scheme,
            p.loc[scheme, "kind"],
            vt,
            vm,
            p.loc[scheme, "proof_size_kib_mean"],
        ))
    if not rows:
        _placeholder(ax, "awaiting data (Exp 1)")
        return

    df = pd.DataFrame(rows, columns=["scheme", "kind", "verify_ms", "mem_MiB", "proof_KiB"])
    best = {c: df[c].idxmin() if df[c].notna().any() else None
            for c in ["verify_ms", "mem_MiB", "proof_KiB"]}
    def _mem(v):
        return f"{v:,.2f}" if v < 10 else f"{v:,.0f}"
    fmt = {"verify_ms": lambda v: f"{v:,.2f}",
           "mem_MiB": _mem,
           "proof_KiB": lambda v: f"{v:,.1f}"}

    cells, colors = [], []
    for i, r in df.iterrows():
        row_c, row_col = [r["scheme"], r["kind"]], ["#f5f5f5", "#f5f5f5"]
        for c in ["verify_ms", "mem_MiB", "proof_KiB"]:
            val = r[c]
            txt = "—" if pd.isna(val) else fmt[c](val)
            if best[c] == i:
                txt = "● " + txt
                row_col.append("#cdebcd")
            else:
                row_col.append("#ffffff")
            row_c.append(txt)
        cells.append(row_c)
        colors.append(row_col)

    tbl = ax.table(cellText=cells, cellColours=colors,
                   colLabels=["scheme", "kind", "verify (ms)", "verify peak mem (MiB)", "proof (KiB)"],
                   cellLoc="center", bbox=[0.0, 0.0, 1.0, 0.80])
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    for (row, _), cell in tbl.get_celld().items():
        if row == 0:
            cell.set_text_props(fontweight="bold")


# ------------------------------------------------------------------------- main
def build(out_path: str = os.path.join(OUT, "dashboard.png")) -> str:
    d = load()
    fig = plt.figure(figsize=(15, 11))
    gs = GridSpec(3, 3, figure=fig, hspace=0.45, wspace=0.26,
                  height_ratios=[1.0, 1.0, 0.62],
                  top=0.90, bottom=0.07, left=0.07, right=0.97)

    fig.suptitle("SwiftZK-Wallet — Recursive vs Folding ZK Aggregation for Mobile Wallet Verification",
                 fontsize=15, fontweight="bold", x=0.07, ha="left", y=0.965)
    fig.text(0.07, 0.935,
             "Selection criteria: verification time → peak memory → proof size "
             "(Exp 1), working EVM verifier (Exp 2), ARM confirmation (Exp 3).",
             fontsize=9.5, color="#555", ha="left")

    _line_panel(fig.add_subplot(gs[0, 0]), d["prove"], "proving_time_ms_mean",
                "A. Proving time", "ms", logy=True)
    _line_panel(fig.add_subplot(gs[0, 1]), d["verify_x86"], "verify_time_ms_mean",
                "B. Verification time  (key metric)", "ms", logy=True)
    _line_panel(fig.add_subplot(gs[0, 2]), d["prove"], "proof_size_kib_mean",
                "C. Proof size", "KiB", logy=True)
    _line_panel(fig.add_subplot(gs[1, 0]), d["prove"], "peak_mem_mib_mean",
                "D. Peak memory (proving host)", "MiB")

    _gas_panel(fig.add_subplot(gs[1, 1]), d["gas"])
    _arm_panel(fig.add_subplot(gs[1, 2]), d["verify_arm"])
    _scorecard(fig.add_subplot(gs[2, :]), d["prove"], d["verify_x86"])

    prov = []
    for k, label in [("prove", "prove"), ("verify_x86", "verify/x86"),
                     ("verify_arm", "verify/arm"), ("gas", "gas")]:
        n = 0 if d[k] is None or d[k].empty else len(d[k])
        prov.append(f"{label}:{n} rows")
    fig.text(0.07, 0.02,
             "data: " + "  |  ".join(prov)
             + f"   generated {_dt.datetime.now().strftime('%Y-%m-%d %H:%M')}",
             fontsize=8, color="#888", ha="left")

    os.makedirs(OUT, exist_ok=True)
    fig.savefig(out_path, dpi=170)
    plt.close(fig)
    print(f"wrote {out_path}")
    return out_path


if __name__ == "__main__":
    build()
