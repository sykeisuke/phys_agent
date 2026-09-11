#!/usr/bin/env python
"""Branching-fraction measurement of B0 -> D* tau nu from fast-sim ntuples (v2).

Counting analysis on a luminosity-matched pseudo-dataset:
generic BBbar (contains the signal at the decay-table BF) + continuum qq.
All variables are beam-constrained (see fastsim/make_ntuple.py v2) — nothing
uses the true B momentum, so BBbar and continuum are treated identically.

    BF = N_sig / (N_B0 * eps * B_sub)

Background is taken from MC truth (true_mode != 1), continuum entering with
the luminosity weight  w = (N_BB * sigma_cont / sigma_BB) / N_cont_generated.
A sideband method is the student exercise.

usage:
  python analysis/measure_bf_dsttaunu.py --signal data/signal_taunu.root \
      --data data/generic_*.root --continuum data/continuum_*.root \
      --cont-weight <w> --n-sig-gen 5000 --n-b0 <N> [--truth-taunu <N>]
"""
import argparse
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import uproot

# sub-mode branching fractions as in the EvtGen decay tables
B_DST_D0PI = 0.6770        # D*+ -> D0 pi+
B_D0_KPI = 0.0389          # D0 -> K- pi+
B_TAU_MUNUNU = 0.1736      # tau -> mu nu nu (incl. radiative)
B_SUB = B_DST_D0PI * B_D0_KPI * B_TAU_MUNUNU

# selection (beam-constrained variables)
M_D0, DM = 1.8648, 0.14543
CUT_M_D0 = 0.020           # |m_d0 - M_D0| window [GeV]
CUT_DELTA_M = 0.0025       # |delta_m - DM| window [GeV]
CUT_R2 = 0.30              # Fox-Wolfram R2 (continuum suppression)
M2MISS_SR = 1.5            # signal region: m2_miss > this [GeV^2]

COLS = ["m2miss", "m_d0", "delta_m", "r2", "true_mode"]


def load(paths):
    parts = [uproot.open(p)["events"].arrays(COLS, library="np") for p in paths]
    return {c: np.concatenate([p[c] for p in parts]) for c in COLS}


def preselect(t):
    return (np.abs(t["m_d0"] - M_D0) < CUT_M_D0) & \
           (np.abs(t["delta_m"] - DM) < CUT_DELTA_M) & \
           (t["r2"] < CUT_R2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--signal", required=True)
    ap.add_argument("--data", nargs="+", required=True,
                    help="generic BBbar ntuples (weight 1)")
    ap.add_argument("--continuum", nargs="*", default=[])
    ap.add_argument("--cont-weight", type=float, default=1.0,
                    help="luminosity weight per continuum candidate")
    ap.add_argument("--n-sig-gen", type=int, default=5000)
    ap.add_argument("--n-b0", type=int, required=True,
                    help="true B0 decays in the BBbar sample (from make_ntuple logs)")
    ap.add_argument("--truth-taunu", type=int, default=None,
                    help="true B0 -> D* tau nu decays in the data (for closure)")
    args = ap.parse_args()

    # --- efficiency from the forced signal MC ---
    sig = load([args.signal])
    sel_sig = preselect(sig) & (sig["m2miss"] > M2MISS_SR)
    n_sel_sig = int(sel_sig.sum())
    eps = n_sel_sig / args.n_sig_gen
    eps_err = np.sqrt(eps * (1 - eps) / args.n_sig_gen)
    print(f"signal MC: {n_sel_sig}/{args.n_sig_gen} selected -> "
          f"eps = {eps:.4f} +- {eps_err:.4f}")

    # --- data: BBbar (w=1) + continuum (w=cont_weight) ---
    bb = load(args.data)
    samples = [(bb, 1.0)]
    if args.continuum:
        samples.append((load(args.continuum), args.cont_weight))

    n_obs = n_bkg = var_obs = var_bkg = 0.0
    for t, w in samples:
        sr = preselect(t) & (t["m2miss"] > M2MISS_SR)
        n_obs += w * sr.sum()
        var_obs += w * w * sr.sum()
        is_bkg = sr & (t["true_mode"] != 1)
        n_bkg += w * is_bkg.sum()
        var_bkg += w * w * is_bkg.sum()
    n_sig = n_obs - n_bkg
    print(f"data: {n_obs:.1f} candidates in SR, {n_bkg:.1f} background "
          f"(MC truth, continuum weighted) -> N_sig = {n_sig:.1f}")

    # --- branching fraction ---
    denom = args.n_b0 * eps * B_SUB
    bf = n_sig / denom
    bf_stat = np.sqrt(var_obs + var_bkg) / denom
    bf_eps = bf * eps_err / eps
    print(f"\nBF(B0 -> D* tau nu) = ({bf*100:.3f} "
          f"+- {bf_stat*100:.3f} (stat) +- {bf_eps*100:.3f} (eps)) %")
    if args.truth_taunu is not None:
        bf_true = args.truth_taunu / args.n_b0
        print(f"generator truth     = {bf_true*100:.3f} %   "
              f"pull = {(bf - bf_true)/np.hypot(bf_stat, bf_eps):+.1f} sigma")

    # --- plot: m2miss after D* + R2 cuts, stacked by truth origin ---
    out = Path(__file__).resolve().parent.parent / "plots"
    out.mkdir(exist_ok=True)
    bins = np.linspace(-2, 10, 49)
    stacks, weights, labels, colors = [], [], [], []
    spec = [(0, "other B decays", "#bdbdbd"), (2, r"$B \to D^{*}\mu\nu$", "#64b5f6"),
            (3, "continuum $q\\bar{q}$", "#c9a227"), (1, r"$B \to D^{*}\tau\nu$ (signal)", "crimson")]
    for mode, label, color in spec:
        vals, ws = [], []
        for t, w in samples:
            m = preselect(t) & (t["true_mode"] == mode)
            vals.append(t["m2miss"][m])
            ws.append(np.full(int(m.sum()), w))
        stacks.append(np.concatenate(vals))
        weights.append(np.concatenate(ws))
        labels.append(label)
        colors.append(color)
    fig, ax = plt.subplots(figsize=(6.8, 4.6))
    ax.hist(stacks, bins=bins, weights=weights, stacked=True,
            color=colors, label=labels)
    ax.axvline(M2MISS_SR, color="k", ls="--", lw=1.2)
    ax.set_xlabel(r"$m^2_{\mathrm{miss}}$ (beam-constrained) [GeV$^2$]")
    ax.set_ylabel("candidates / bin (lumi-weighted)")
    ax.set_title(r"pseudo-data: generic $B\bar{B}$ + continuum, after $D^{*}$ + $R_2$ cuts")
    ax.legend(fontsize=9)
    ax.set_yscale("log")
    fig.tight_layout()
    fig.savefig(out / "bf_m2miss_data.png", dpi=150)
    print("wrote plots/bf_m2miss_data.png")


if __name__ == "__main__":
    main()
