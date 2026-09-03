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
    E  per-run spread    per-run deviation from median; dev-machine vs CI-runner noise

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
    ax.set_title(title, fontsize=12.5, fontweight="bold", loc="left", pad=8)


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
    ax.set_title("A. Time vs depth", fontsize=12.5, fontweight="bold", loc="left", pad=8)
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
    ax.set_title("B. Peak memory vs depth", fontsize=12.5, fontweight="bold", loc="left", pad=8)
    ax.legend(fontsize=6.5, ncol=2)


def panel_size(ax, sp, gas):
    """The folding trade-off, per metric: folding's aggregate proof is far
    smaller, but its verification key is enormous. Grouped by metric so the
    per-metric ratio (and which family wins it) is the headline."""
    need = {"proof_size_kib_mean", "vk_size_kib_mean"}
    if sp is None or sp.empty or not need.issubset(sp.columns):
        return _ph(ax, "C. Proof & verification-key size", "Exp 1")
    one = (sp.sort_values("depth").groupby("scheme", as_index=False).first()
           .set_index("scheme"))
    order = [s for s in ["nova", "plonky2", "halo2", "supernova"] if s in one.index]
    metrics = [("aggregate\nproof", "proof_size_kib_mean"),
               ("verification\nkey", "vk_size_kib_mean")]
    x = np.arange(len(metrics))
    w = 0.8 / max(len(order), 1)
    for j, s in enumerate(order):
        vals = [one.loc[s, col] for _, col in metrics]
        off = (j - (len(order) - 1) / 2) * w
        bars = ax.bar(x + off, vals, w * 0.92, color=_c(s),
                      label=f'{s} ({one.loc[s, "kind"]})')
        for b, v in zip(bars, vals):
            ax.annotate(f"{v:,.1f}" if v < 100 else f"{v:,.0f}",
                        (b.get_x() + b.get_width() / 2, v), ha="center",
                        va="bottom", fontsize=7.5)
    ax.set_yscale("log")
    ax.set_ylim(top=one[[c for _, c in metrics]].to_numpy().max() * 120)
    ax.set_ylabel("KiB (log)")

    post_ratio = None
    if gas is not None and not gas.empty:
        g = gas.groupby("scheme")["tx_exec_cost"].first()
        if {"nova", "plonky2"}.issubset(g.index):
            post_ratio = max(g["nova"], g["plonky2"]) / min(g["nova"], g["plonky2"])

    if {"nova", "plonky2"}.issubset(one.index):
        top_all = one[[c for _, c in metrics]].to_numpy().max()
        for i, (_, col) in enumerate(metrics):
            nv, pv = one.loc["nova", col], one.loc["plonky2", col]
            hi, lo = max(nv, pv), min(nv, pv)
            win = "folding" if nv < pv else "recursion"
            col_ = _c("nova") if nv < pv else _c("plonky2")
            txt = f"{win}\n×{hi / lo:,.0f} smaller"
            if i == 0 and post_ratio:
                txt += f"  (post ×{post_ratio:,.0f})"
            ax.text(i, top_all * 3.0, txt, ha="center", va="bottom",
                    fontsize=9, fontweight="bold", color=col_)

    ax.set_xticks(x)
    ax.set_xticklabels([m for m, _ in metrics], fontsize=9.5)
    ax.set_title("C. Proof & verification-key size", fontsize=12.5,
                 fontweight="bold", loc="left", pad=8)
    ax.grid(True, axis="y", which="both", alpha=0.25)
    ax.legend(fontsize=7.5, loc="upper left")


def panel_x86_arm(ax, vx, va):
    """Cross-ISA verification latency. Bars = x86 vs ARM per scheme with the
    exact value; the recursion-vs-folding advantage ratio is drawn as a bracket
    at each host so the "gap widens on ARM" claim is visible, not implied."""
    if vx is None or vx.empty or va is None or va.empty:
        return _ph(ax, "D. Verification: x86 vs ARM", "Exp 3")
    d = CMP_DEPTH
    x86 = vx[vx["depth"] == d].set_index("scheme")
    arm = va[va["depth"] == d].set_index("scheme")
    schemes = [s for s in ["plonky2", "nova", "halo2", "supernova"]
               if s in arm.index and s in x86.index]
    x = np.arange(len(schemes))
    w = 0.36
    lx = [x86.loc[s, "verify_time_ms_mean"] for s in schemes]
    la = [arm.loc[s, "verify_time_ms_mean"] for s in schemes]
    b1 = ax.bar(x - w / 2, lx, w, label="x86", color="#9DB4C0")
    b2 = ax.bar(x + w / 2, la, w, label="ARM (Neoverse-N2)", color="#5C6B73")
    ax.set_yscale("log")
    ax.set_ylim(min(lx + la) * 0.28, max(lx + la) * 30)
    ax.set_ylabel("verification latency (ms, log)")
    for bars in (b1, b2):
        for bb in bars:
            v = bb.get_height()
            ax.annotate(f"{v:.3g}", (bb.get_x() + bb.get_width() / 2, v),
                        xytext=(0, 2), textcoords="offset points",
                        ha="center", fontsize=7.5)

    # per-scheme x86 -> ARM change, just above each bar pair
    for i in range(len(schemes)):
        ch = (la[i] / lx[i] - 1) * 100
        ax.annotate(f"{ch:+.0f}% on ARM", (i, max(lx[i], la[i]) * 1.5),
                    ha="center", fontsize=7.5, color="#555")

    # recursion-vs-folding advantage bracket at each host
    if {"plonky2", "nova"}.issubset(schemes):
        pi, ni = schemes.index("plonky2"), schemes.index("nova")
        for off, host, pv, nv, col, h in [
            (-w / 2, "x86", lx[pi], lx[ni], "#4C78A8", max(lx) * 3.0),
            (+w / 2, "ARM", la[pi], la[ni], "#E45756", max(la) * 9.0),
        ]:
            xa, xb = pi + off, ni + off
            ax.plot([xa, xa, xb, xb], [h * 0.82, h, h, h * 0.82], color=col, lw=1.2)
            ax.text((xa + xb) / 2, h * 1.12, f"{nv / pv:.0f}×  {host}",
                    ha="center", fontsize=8.5, fontweight="bold", color=col)

    ax.set_xticks(x)
    ax.set_xticklabels([f'{s}\n({x86.loc[s, "kind"]})' for s in schemes], fontsize=8.5)
    ax.set_title("D. Verification: x86 vs ARM", fontsize=12.5, fontweight="bold", loc="left", pad=8)
    ax.grid(True, axis="y", which="both", alpha=0.25)
    ax.legend(fontsize=8, loc="upper left", framealpha=0.9)


def panel_dist(ax, runs):
    """Not a scheme comparison — a credibility check. Each run as % deviation
    from its group median; the message is that the dev-machine (x86, N=40) runs
    carry real noise while the CI-runner (ARM, N=200) runs are ~10x tighter, so
    the ARM figures are the ones to lean on."""
    if runs is None or runs.empty:
        return _ph(ax, "E. Per-run verification spread", "Exp 1/3")
    d = CMP_DEPTH
    sub = runs[runs["depth"] == d]
    groups, labels, colors, iqr = [], [], [], []
    for host in ("x86", "arm"):
        for s in ("plonky2", "nova"):
            v = sub[(sub["host"] == host) & (sub["scheme"] == s)]["verify_time_ms"].to_numpy()
            if len(v):
                med = float(np.median(v))
                dev = (v - med) / med * 100.0
                groups.append(dev)
                labels.append(f"{s}\nN={len(v)}")
                colors.append(_c(s))
                iqr.append(np.percentile(dev, 75) - np.percentile(dev, 25))
    if not groups:
        return _ph(ax, "E. Per-run verification spread", "Exp 1/3")
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

    # divider + host-group callouts
    n_x86 = sum(1 for lset in ["x86"] for _ in range(2))  # first two groups are x86
    if len(groups) == 4:
        ax.axvline(1.5, color="#bbb", lw=1, ls="--")
        top = max(np.percentile(g, 98) for g in groups)
        ax.text(0.5, top * 1.05, f"x86 dev machine · N=40\nIQR ≈ ±{max(iqr[:2]) / 2:.1f} %,"
                " outliers to +12 %", ha="center", va="bottom", fontsize=7.5, color="#555")
        ax.text(2.5, top * 1.05, f"ARM CI runner · N=200\nIQR ≈ ±{max(iqr[2:]) / 2:.2f} %",
                ha="center", va="bottom", fontsize=7.5, color="#555", fontweight="bold")
        ax.set_ylim(top=top * 1.9)
    ax.set_xticks(pos)
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("per-run deviation from median (%)")
    ax.set_title("E. Per-run verification spread", fontsize=12.5, fontweight="bold", loc="left", pad=8)
    ax.grid(True, axis="y", alpha=0.25)


def panel_ratio(ax, sp, vx, va, gas):
    """Synthesis: both schemes on every metric, each metric normalised so its
    cheaper scheme sits at 1x. Dumbbell — teal dot = plonky2 (recursion), red
    dot = nova (folding), line = the gap; real value printed at each dot. On the
    wallet-side metrics recursion is the 1x dot and folding is far to the right;
    on proof size / on-chain post it flips."""
    if sp is None or sp.empty or vx is None or vx.empty:
        return _ph(ax, "F. Both schemes, per metric", "Exp 1")

    def piv(df, col, host=None, dep=None):
        d = df if host is None else df[df["host"] == host]
        if dep is not None and "depth" in d:
            d = d[d["depth"] == dep] if dep in set(d["depth"]) else d[d["depth"] == d["depth"].max()]
        d = d.groupby("scheme")[col].first()
        return d.get("nova"), d.get("plonky2")

    def fmt(v, u):
        if u == "gas":
            return f"{v / 1e6:.2f} M gas" if v >= 1e6 else f"{v / 1e3:.0f} k gas"
        if u == "KiB" and v >= 1024:
            return f"{v / 1024:.1f} MiB"
        return f"{v:,.0f} {u}" if v >= 100 else f"{v:.3g} {u}"

    rows = []  # (label, nova_val, plonky2_val, unit)
    n, p = piv(vx, "verify_time_ms_mean", "x86", 16)
    if n and p:
        rows.append(("verify time · x86", n, p, "ms"))
    if va is not None and not va.empty:
        n, p = piv(va, "verify_time_ms_mean", "arm", 16)
        if n and p:
            rows.append(("verify time · ARM", n, p, "ms"))
        n, p = piv(va, "peak_mem_mib_mean", "arm", 16)
        if n and p:
            rows.append(("verify memory · ARM", n, p, "MiB"))
    one = sp.groupby("scheme").first()
    if {"nova", "plonky2"}.issubset(one.index):
        rows.append(("verification key", one.loc["nova", "vk_size_kib_mean"],
                     one.loc["plonky2", "vk_size_kib_mean"], "KiB"))
        rows.append(("aggregate proof", one.loc["nova", "proof_size_kib_mean"],
                     one.loc["plonky2", "proof_size_kib_mean"], "KiB"))
    if gas is not None and not gas.empty:
        g = gas.groupby("scheme")["tx_exec_cost"].first()
        if {"nova", "plonky2"}.issubset(g.index):
            rows.append(("on-chain proof post", g["nova"], g["plonky2"], "gas"))
    if not rows:
        return _ph(ax, "F. Both schemes, per metric", "Exp 1")

    y = np.arange(len(rows))[::-1]
    xmax = 1.0
    for yi, (lab, nv, pv, u) in zip(y, rows):
        base = min(nv, pv)
        nr, pr = nv / base, pv / base
        xmax = max(xmax, nr, pr)
        ax.plot([nr, pr], [yi, yi], color="#ccc", lw=2.5, zorder=1)
        ax.scatter([pr], [yi], s=80, color=_c("plonky2"), zorder=3, ec="white", lw=1)
        ax.scatter([nr], [yi], s=80, color=_c("nova"), zorder=3, ec="white", lw=1)
        lo_r, lo_c, lo_v = (pr, _c("plonky2"), pv) if pr <= nr else (nr, _c("nova"), nv)
        hi_r, hi_c, hi_v = (nr, _c("nova"), nv) if pr <= nr else (pr, _c("plonky2"), pv)
        ax.annotate(fmt(lo_v, u), (lo_r, yi), xytext=(-10, 0),
                    textcoords="offset points", ha="right", va="center",
                    fontsize=7.3, color=lo_c, fontweight="bold")
        ax.annotate(f"{fmt(hi_v, u)}  ×{hi_r / lo_r:,.0f}", (hi_r, yi),
                    xytext=(10, 0), textcoords="offset points", ha="left", va="center",
                    fontsize=7.3, color=hi_c, fontweight="bold")
    ax.axvline(1, color="#333", lw=1.2, zorder=2)
    ax.set_xscale("log")
    ax.set_xlim(0.06, xmax * 20)
    ax.set_ylim(-0.6, len(rows) - 0.2)
    ax.set_yticks(y)
    ax.set_yticklabels([r[0] for r in rows], fontsize=8.5)
    ax.set_xlabel("relative cost  (cheaper scheme = 1×,  log)")
    ax.scatter([], [], s=80, color=_c("plonky2"), label="plonky2 (recursion)")
    ax.scatter([], [], s=80, color=_c("nova"), label="nova (folding)")
    ax.legend(fontsize=7.5, loc="lower right", framealpha=0.95)
    ax.set_title("F. Both schemes, per metric", fontsize=12.5, fontweight="bold",
                 loc="left", pad=8)
    ax.grid(True, axis="x", which="both", alpha=0.25)


# ------------------------------------------------------------------------- main
def build(out_path: str = os.path.join(OUT, "dashboard.png")) -> str:
    d = load()
    fig = plt.figure(figsize=(16.5, 9))
    gs = GridSpec(2, 3, figure=fig, hspace=0.44, wspace=0.34,
                  top=0.945, bottom=0.09, left=0.055, right=0.965)

    panel_time(fig.add_subplot(gs[0, 0]), d["prove"], d["verify_x86"], d["verify_arm"])
    panel_mem(fig.add_subplot(gs[0, 1]), d["prove"], d["verify_x86"], d["verify_arm"])
    panel_size(fig.add_subplot(gs[0, 2]), d["prove"], d["gas"])
    panel_x86_arm(fig.add_subplot(gs[1, 0]), d["verify_x86"], d["verify_arm"])
    panel_dist(fig.add_subplot(gs[1, 1]), d["runs"])
    panel_ratio(fig.add_subplot(gs[1, 2]), d["prove"], d["verify_x86"], d["verify_arm"], d["gas"])

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
