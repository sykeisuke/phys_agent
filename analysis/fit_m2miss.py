#!/usr/bin/env python
"""Binned template fit of m2_miss with pyhf: the statistical-analysis stage.

Model: data(m2miss) = mu * S + B, built with
pyhf.simplemodels.uncorrelated_background —
  S : the true B0 -> D* tau nu component of the pseudo-dataset (shape and
      normalization at the generator-truth BF, so mu_hat = BF/BF_truth)
  B : everything else (other B decays, D* mu nu, weighted continuum)
  per-bin background uncertainty: MC statistics (+) a conservative 10%
      normalization component, until proper systematic estimates exist
      (take them from published Belle II analyses where available).

Compared with the counting analysis (analysis/measure_bf_dsttaunu.py) the
fit uses the full m2_miss shape, so the mu nu peak and the sidebands
constrain the background under the signal.

usage:
  python analysis/fit_m2miss.py --data data/generic_*.root \
      --continuum data/continuum_*.root --cont-weight 0.995 \
      [--bf-truth 0.01483] [--bkg-syst 0.10]
"""
import argparse
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import pyhf
import uproot

M_D0, DM = 1.8648, 0.14543
CUT_M_D0, CUT_DELTA_M, CUT_R2 = 0.020, 0.0025, 0.30
E_TAG_MAX = 4.0            # ROE energy consistency (CM); np.inf disables
BINS = np.linspace(-2.0, 10.0, 25)

COLS = ["m2miss", "m_d0", "delta_m", "r2", "e_tag_cm", "true_mode",
        "lep_true_pid"]


def load(paths):
    parts = [uproot.open(p)["events"].arrays(COLS, library="np") for p in paths]
    return {c: np.concatenate([p[c] for p in parts]) for c in COLS}


def preselect(t):
    return (np.abs(t["m_d0"] - M_D0) < CUT_M_D0) & \
           (np.abs(t["delta_m"] - DM) < CUT_DELTA_M) & \
           (t["r2"] < CUT_R2) & (t["e_tag_cm"] < E_TAG_MAX)


def hists(samples):
    """Return (signal, background, bkg_stat_var, data) histograms."""
    nb = len(BINS) - 1
    sig = np.zeros(nb)
    bkg = np.zeros(nb)
    bkg_var = np.zeros(nb)
    data = np.zeros(nb)
    for t, w in samples:
        m = preselect(t)
        is_sig = m & (t["true_mode"] == 1) & (np.abs(t["lep_true_pid"]) == 13)
        is_bkg = m & ~((t["true_mode"] == 1) & (np.abs(t["lep_true_pid"]) == 13))
        sig += w * np.histogram(t["m2miss"][is_sig], bins=BINS)[0]
        h_b = np.histogram(t["m2miss"][is_bkg], bins=BINS)[0]
        bkg += w * h_b
        bkg_var += w * w * h_b
        data += w * np.histogram(t["m2miss"][m], bins=BINS)[0]
    return sig, bkg, bkg_var, data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", nargs="+", required=True)
    ap.add_argument("--continuum", nargs="*", default=[])
    ap.add_argument("--cont-weight", type=float, default=1.0)
    ap.add_argument("--bf-truth", type=float, default=0.01483,
                    help="generator-truth BF; mu is measured relative to it")
    ap.add_argument("--bkg-syst", type=float, default=0.10,
                    help="conservative flat background normalization syst")
    args = ap.parse_args()

    samples = [(load(args.data), 1.0)]
    if args.continuum:
        samples.append((load(args.continuum), args.cont_weight))
    sig, bkg, bkg_var, data = hists(samples)

    floor = 1e-3
    bkg = np.maximum(bkg, floor)
    bkg_unc = np.sqrt(bkg_var + (args.bkg_syst * bkg) ** 2)
    bkg_unc = np.maximum(bkg_unc, floor)

    model = pyhf.simplemodels.uncorrelated_background(
        signal=sig.tolist(), bkg=bkg.tolist(), bkg_uncertainty=bkg_unc.tolist())
    fit_data = np.concatenate([data, model.config.auxdata])

    pyhf.set_backend("numpy", "minuit")  # minuit provides parameter uncertainties
    result = np.asarray(pyhf.infer.mle.fit(
        fit_data, model, return_uncertainties=True))
    i = model.config.poi_index
    mu, mu_err = result[i]  # shape (n_params, 2): (best fit, uncertainty)
    bf = mu * args.bf_truth
    bf_err = mu_err * args.bf_truth
    print(f"template fit: mu = {mu:.3f} +- {mu_err:.3f}")
    print(f"BF(B0 -> D* tau nu) = ({bf*100:.3f} +- {bf_err*100:.3f}) %   "
          f"[truth {args.bf_truth*100:.3f} %, pull {(mu-1)/mu_err:+.1f} sigma]")

    # post-fit plot
    out = Path(__file__).resolve().parent.parent / "plots"
    out.mkdir(exist_ok=True)
    centers = 0.5 * (BINS[:-1] + BINS[1:])
    width = np.diff(BINS)
    fig, ax = plt.subplots(figsize=(6.8, 4.6))
    ax.bar(centers, bkg, width=width, color="#bdbdbd", label="background (post-fit norm fixed)")
    ax.bar(centers, mu * sig, width=width, bottom=bkg, color="crimson",
           label=rf"$\mu \times$ signal ($\mu$ = {mu:.2f})")
    ax.errorbar(centers, data, yerr=np.sqrt(np.maximum(data, 1)), fmt="ko",
                ms=3.5, lw=1, label="pseudo-data")
    ax.set_xlabel(r"$m^2_{\mathrm{miss}}$ (beam-constrained) [GeV$^2$]")
    ax.set_ylabel("candidates / bin (lumi-weighted)")
    ax.set_title("pyhf template fit")
    ax.set_yscale("log")
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(out / "fit_m2miss.png", dpi=150)
    print("wrote plots/fit_m2miss.png")


if __name__ == "__main__":
    main()
