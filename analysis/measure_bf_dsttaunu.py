#!/usr/bin/env python
"""Branching-fraction measurement of B0 -> D* tau nu from fast-sim ntuples.

A counting analysis on a generic BBbar sample treated as the dataset:

    BF = N_sig / (N_B0 * eps * B_sub)

  N_sig  : background-subtracted candidate count in the m2_miss signal
           region (background taken from MC truth here; a sideband method
           is the student exercise)
  N_B0   : number of true B0 decays in the dataset (2 per B0 event)
  eps    : selection efficiency from the forced signal MC
  B_sub  : product of the sub-mode branching fractions the signal MC forces:
           B(D*+ -> D0 pi+) * B(D0 -> K pi) * B(tau -> mu nu nu (gamma))

usage:
  python analysis/measure_bf_dsttaunu.py --signal data/signal_taunu.root \
      --data data/generic_0.root ... --n-sig-gen 5000 --n-b0 <N> [--truth-taunu <N>]
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

# selection
M_D0, DM = 1.8648, 0.14543
CUT_M_D0 = 0.020           # |m_d0 - M_D0| window [GeV]
CUT_DELTA_M = 0.0025       # |delta_m - DM| window [GeV]
M2MISS_SR = 1.5            # signal region: m2_miss > this [GeV^2]


def load(paths):
    cols = ["m2miss", "m_d0", "delta_m", "true_mode"]
    parts = [uproot.open(p)["events"].arrays(cols, library="np") for p in paths]
    return {c: np.concatenate([p[c] for p in parts]) for c in cols}


def dstar_cuts(t):
    return (np.abs(t["m_d0"] - M_D0) < CUT_M_D0) & \
           (np.abs(t["delta_m"] - DM) < CUT_DELTA_M)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--signal", required=True)
    ap.add_argument("--data", nargs="+", required=True)
    ap.add_argument("--n-sig-gen", type=int, default=5000)
    ap.add_argument("--n-b0", type=int, required=True,
                    help="true B0 decays in the data sample (from make_ntuple logs)")
    ap.add_argument("--truth-taunu", type=int, default=None,
                    help="true B0 -> D* tau nu decays in the data (for closure)")
    args = ap.parse_args()

    # --- efficiency from the forced signal MC ---
    sig = load([args.signal])
    sel_sig = dstar_cuts(sig) & (sig["m2miss"] > M2MISS_SR)
    n_sel_sig = int(sel_sig.sum())
    eps = n_sel_sig / args.n_sig_gen
    eps_err = np.sqrt(eps * (1 - eps) / args.n_sig_gen)
    print(f"signal MC: {n_sel_sig}/{args.n_sig_gen} selected -> "
          f"eps = {eps:.4f} +- {eps_err:.4f}")

    # --- counting in the data ---
    data = load(args.data)
    presel = dstar_cuts(data)
    sr = presel & (data["m2miss"] > M2MISS_SR)
    n_obs = int(sr.sum())
    n_bkg = int((sr & (data["true_mode"] != 1)).sum())  # MC-truth background
    n_sig = n_obs - n_bkg
    print(f"data: {n_obs} candidates in SR, {n_bkg} background (MC truth) "
          f"-> N_sig = {n_sig}")

    # --- branching fraction ---
    denom = args.n_b0 * eps * B_SUB
    bf = n_sig / denom
    bf_stat = np.sqrt(n_obs + n_bkg) / denom      # subtraction: both counts fluctuate
    bf_eps = bf * eps_err / eps
    print(f"\nBF(B0 -> D* tau nu) = ({bf*100:.3f} "
          f"+- {bf_stat*100:.3f} (stat) +- {bf_eps*100:.3f} (eps)) %")
    if args.truth_taunu is not None:
        bf_true = args.truth_taunu / args.n_b0
        print(f"generator truth     = {bf_true*100:.3f} %   "
              f"(decay-table value 1.5 %)   pull = "
              f"{(bf - bf_true)/np.hypot(bf_stat, bf_eps):+.1f} sigma")

    # --- plot: m2miss after D* cuts, split by truth ---
    out = Path(__file__).resolve().parent.parent / "plots"
    out.mkdir(exist_ok=True)
    bins = np.linspace(-1, 10, 45)
    m2 = data["m2miss"][presel]
    tm = data["true_mode"][presel]
    fig, ax = plt.subplots(figsize=(6.8, 4.6))
    ax.hist([m2[tm == 0], m2[tm == 2], m2[tm == 1]], bins=bins, stacked=True,
            color=["#bdbdbd", "#64b5f6", "crimson"],
            label=["other B decays", r"$B \to D^{*}\mu\nu$",
                   r"$B \to D^{*}\tau\nu$ (signal)"])
    ax.axvline(M2MISS_SR, color="k", ls="--", lw=1.2)
    ax.text(M2MISS_SR + 0.15, ax.get_ylim()[1] * 0.9, "signal region",
            fontsize=10)
    ax.set_xlabel(r"$m^2_{\mathrm{miss}}$ [GeV$^2$]")
    ax.set_ylabel("candidates")
    ax.set_title(r"generic $B\bar{B}$, after $D^{*}$ selection")
    ax.legend()
    ax.set_yscale("log")
    fig.tight_layout()
    fig.savefig(out / "bf_m2miss_data.png", dpi=150)
    print("wrote plots/bf_m2miss_data.png")


if __name__ == "__main__":
    main()
