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
        "lep_true_pid", "lep_flavor"]


def load(paths):
    parts = [uproot.open(p)["events"].arrays(COLS, library="np") for p in paths]
    return {c: np.concatenate([p[c] for p in parts]) for c in COLS}


def preselect(t):
    return (np.abs(t["m_d0"] - M_D0) < CUT_M_D0) & \
           (np.abs(t["delta_m"] - DM) < CUT_DELTA_M) & \
           (t["r2"] < CUT_R2) & (t["e_tag_cm"] < E_TAG_MAX)


def hists(samples, flavor=None):
    """Return (signal, background, bkg_stat_var, data) histograms,
    optionally restricted to one reconstructed lepton flavor (11 or 13)."""
    nb = len(BINS) - 1
    sig = np.zeros(nb)
    bkg = np.zeros(nb)
    bkg_var = np.zeros(nb)
    data = np.zeros(nb)
    for t, w in samples:
        m = preselect(t)
        if flavor is not None:
            m = m & (t["lep_flavor"] == flavor)
        is_sig = m & (t["true_mode"] == 1) & np.isin(np.abs(t["lep_true_pid"]), (11, 13))
        is_bkg = m & ~((t["true_mode"] == 1) & np.isin(np.abs(t["lep_true_pid"]), (11, 13)))
        sig += w * np.histogram(t["m2miss"][is_sig], bins=BINS)[0]
        h_b = np.histogram(t["m2miss"][is_bkg], bins=BINS)[0]
        bkg += w * h_b
        bkg_var += w * w * h_b
        data += w * np.histogram(t["m2miss"][m], bins=BINS)[0]
    return sig, bkg, bkg_var, data


def channel_spec(name, sig, bkg, bkg_unc):
    """One pyhf channel: mu x signal + background with per-bin shapesys."""
    return {
        "name": name,
        "samples": [
            {"name": "signal", "data": sig.tolist(),
             "modifiers": [{"name": "mu", "type": "normfactor", "data": None}]},
            {"name": "background", "data": bkg.tolist(),
             "modifiers": [{"name": f"uncorr_bkg_{name}", "type": "shapesys",
                            "data": bkg_unc.tolist()}]},
        ],
    }


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

    # simultaneous fit with separate e and mu channels sharing the signal
    # strength, following the practice of the published R(D*) analyses
    floor = 1e-3
    channels, per_channel = [], {}
    for fl, name in [(11, "e"), (13, "mu")]:
        sig, bkg, bkg_var, data = hists(samples, flavor=fl)
        bkg = np.maximum(bkg, floor)
        bkg_unc = np.maximum(np.sqrt(bkg_var + (args.bkg_syst * bkg) ** 2), floor)
        channels.append(channel_spec(name, sig, bkg, bkg_unc))
        per_channel[name] = (sig, bkg, data)
    model = pyhf.Model({"channels": channels}, poi_name="mu")
    fit_data = np.concatenate(
        [per_channel[c][2] for c in model.config.channels]
        + [model.config.auxdata])
    # merged single-histogram fit for comparison
    sig_m, bkg_m, bkg_var_m, data_m = hists(samples)
    bkg_m = np.maximum(bkg_m, floor)
    unc_m = np.maximum(np.sqrt(bkg_var_m + (args.bkg_syst * bkg_m) ** 2), floor)
    model_m = pyhf.simplemodels.uncorrelated_background(
        signal=sig_m.tolist(), bkg=bkg_m.tolist(), bkg_uncertainty=unc_m.tolist())
    fit_data_m = np.concatenate([data_m, model_m.config.auxdata])

    pyhf.set_backend("numpy", "minuit")  # minuit provides parameter uncertainties
    result = np.asarray(pyhf.infer.mle.fit(
        fit_data, model, return_uncertainties=True))
    mu, mu_err = result[model.config.poi_index]
    bf = mu * args.bf_truth
    bf_err = mu_err * args.bf_truth
    print(f"simultaneous e+mu fit: mu = {mu:.3f} +- {mu_err:.3f}")
    print(f"BF(B0 -> D* tau nu) = ({bf*100:.3f} +- {bf_err*100:.3f}) %   "
          f"[truth {args.bf_truth*100:.3f} %, pull {(mu-1)/mu_err:+.1f} sigma]")

    result_m = np.asarray(pyhf.infer.mle.fit(
        fit_data_m, model_m, return_uncertainties=True))
    mu_m, mu_m_err = result_m[model_m.config.poi_index]
    print(f"merged single-histogram fit (cross-check): "
          f"mu = {mu_m:.3f} +- {mu_m_err:.3f}")

    # post-fit plot, one panel per channel
    out = Path(__file__).resolve().parent.parent / "plots"
    out.mkdir(exist_ok=True)
    centers = 0.5 * (BINS[:-1] + BINS[1:])
    width = np.diff(BINS)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
    for ax, name, label in zip(axes, ("e", "mu"),
                               ("electron channel", "muon channel")):
        sig, bkg, data = per_channel[name]
        ax.bar(centers, bkg, width=width, color="#bdbdbd", label="background")
        ax.bar(centers, mu * sig, width=width, bottom=bkg, color="crimson",
               label=rf"$\mu\times$signal ($\mu$ = {mu:.2f})")
        ax.errorbar(centers, data, yerr=np.sqrt(np.maximum(data, 1)),
                    fmt="ko", ms=3.5, lw=1, label="pseudo-data")
        ax.set_xlabel(r"$m^2_{\mathrm{miss}}$ (beam-constrained) [GeV$^2$]")
        ax.set_ylabel("candidates / bin (lumi-weighted)")
        ax.set_title(label, fontsize=10)
        ax.set_yscale("log")
    axes[0].legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(out / "fit_m2miss.png", dpi=150)
    print("wrote plots/fit_m2miss.png")


if __name__ == "__main__":
    main()
