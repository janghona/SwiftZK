#!/usr/bin/env python3
"""Figure rendering for the paper. Called via `analyze.py --figures`.

One consistent style, log-x on aggregation depth. Four Experiment-1 panels
(prove time, verify time, peak memory, proof size) plus one Experiment-3 panel
(ARM verify latency). Colour by scheme; line style by kind.
"""
from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

SCHEME_COLOR = {
    "halo2": "#4C78A8",
    "plonky2": "#72B7B2",
    "nova": "#E45756",
    "supernova": "#F58518",
}
KIND_STYLE = {"recursive": "-", "folding": "--"}


def _panel(ax, df, ycol, ylabel, logy=False):
    for scheme, g in df.groupby("scheme"):
        g = g.sort_values("depth")
        kind = g["kind"].iloc[0]
        ax.plot(
            g["depth"], g[ycol],
            marker="o", markersize=4,
            color=SCHEME_COLOR.get(scheme, "#666"),
            linestyle=KIND_STYLE.get(kind, "-"),
            label=scheme,
        )
        err = ycol.replace("_mean", "_ci95")
        if err in g:
            ax.fill_between(g["depth"], g[ycol] - g[err], g[ycol] + g[err],
                            color=SCHEME_COLOR.get(scheme, "#666"), alpha=0.15)
    ax.set_xscale("log", base=2)
    if logy:
        ax.set_yscale("log")
    ax.set_xlabel("Aggregation depth")
    ax.set_ylabel(ylabel)
    ax.grid(True, which="both", alpha=0.25)


def render_all(sp, sv, out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)

    if sp is not None and not sp.empty:
        fig, axes = plt.subplots(2, 2, figsize=(9, 6.5))
        _panel(axes[0, 0], sp, "proving_time_ms_mean", "Proving time (ms)", logy=True)
        vx = sv[sv["host"] == "x86"] if (sv is not None and not sv.empty) else None
        if vx is not None and not vx.empty:
            _panel(axes[0, 1], vx, "verify_time_ms_mean", "Verification time (ms)", logy=True)
        _panel(axes[1, 0], sp, "peak_mem_mib_mean", "Peak memory (MiB)")
        _panel(axes[1, 1], sp, "proof_size_kib_mean", "Proof size (KiB)", logy=True)
        axes[0, 0].legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(os.path.join(out_dir, "fig_exp1.png"), dpi=200)
        plt.close(fig)
        print("wrote results/fig_exp1.png")

    if sv is not None and not sv.empty:
        arm = sv[sv["host"] == "arm"]
        if not arm.empty:
            fig, ax = plt.subplots(figsize=(5, 3.5))
            _panel(ax, arm, "verify_time_ms_mean", "ARM verify latency (ms)", logy=True)
            ax.legend(fontsize=8)
            fig.tight_layout()
            fig.savefig(os.path.join(out_dir, "fig_exp3.png"), dpi=200)
            plt.close(fig)
            print("wrote results/fig_exp3.png")


if __name__ == "__main__":
    import pandas as pd

    def _load(p):
        return pd.read_csv(p) if os.path.exists(p) else None

    render_all(_load("results/summary_prove.csv"), _load("results/summary_verify.csv"), "results")
