#!/usr/bin/env python
"""First-pass sensitivity projections for the charged-B D_s modes at 1/ab.

Expected signal yield:
    N = N_B+- x BF x B_sub x eff
with N_B+- = 2 x f+- x sigma_BB x L, sub-chain branching fractions from the
PDG/decay tables (products below), and the efficiency from the forced MC
(fastsim/make_ntuple_ds.py output).

Statistical precision is quoted in two brackets: background-free (sqrt(S)/S)
and B/S = 5 (a conservative placeholder until the dedicated background
study exists).

usage: python analysis/sensitivity_ds.py
       (expects data/sig_dsstkst.root, sig_dsk1.root, sig_ds1k.root)
"""
import numpy as np
import uproot

SIGMA_BB_NB = 1.1
LUMI_INV_AB = 1.0
F_CHARGED = 0.516
N_BPM = 2 * F_CHARGED * SIGMA_BB_NB * 1e9 * LUMI_INV_AB  # charged B mesons

# sub-chain branching fractions (PDG / EvtGen decay tables)
B_DS_PHIPI = 0.045 * 0.492          # D_s -> phi pi, phi -> K K
B_SUB = {
    "dsstkst": 0.935 * B_DS_PHIPI * (2 / 3) * 0.5 * 0.692,  # Ds*->Ds g, K*->KS pi
    "dsk1":    B_DS_PHIPI * 0.14,                            # K1 -> rho0 K
    "ds1k":    0.5 * 0.5 * 0.692 * 0.677 * 0.0395,           # Ds1->D*K0, D*->D0pi, D0->Kpi
}
MODES = [
    ("dsstkst", r"B- -> Ds*+ K*- mu nu", "data/sig_dsstkst.root", 1.8e-3),
    ("dsk1",    r"B- -> Ds+ K1(1270)- mu nu", "data/sig_dsk1.root", 1.0e-3),
    ("ds1k",    r"B- -> Ds1(2536)+ K- mu nu", "data/sig_ds1k.root", 0.5e-3),
]
N_GEN = 5000


def main():
    print(f"N(B+-) at {LUMI_INV_AB} /ab = {N_BPM:.2e}   (mu mode only; e+mu doubles S)\n")
    print(f"{'mode':34s} {'eff':>6s} {'B_sub':>8s} {'assumed BF':>10s} "
          f"{'S':>6s} {'dBF/BF (B=0)':>13s} {'dBF/BF (B/S=5)':>15s}")
    for key, label, path, bf in MODES:
        n_rec = len(uproot.open(path)["events"].arrays(["m2miss"], library="np")["m2miss"])
        eff = n_rec / N_GEN
        s = N_BPM * bf * B_SUB[key] * eff
        rel0 = 1 / np.sqrt(s)
        rel5 = np.sqrt(1 + 5) / np.sqrt(s)
        print(f"{label:34s} {eff:6.1%} {B_SUB[key]:8.4f} {bf:10.1e} "
              f"{s:6.0f} {rel0:13.1%} {rel5:15.1%}")
    print("\nCaveats: PHSP decay models; single sub-chains only (more chains add"
          "\nstatistics); background placeholder B/S=5 pending the dedicated study.")


if __name__ == "__main__":
    main()
