#!/usr/bin/env python
"""Figures and numbers for the B0 -> D* tau nu analysis note.

Produces, from the standard ntuples:
  note_presel.png      D0-mass and delta-m distributions with the windows
  note_discrim.png     R2 and e_tag_cm distributions (why each cut is needed)
  note_cr.png          control regions: delta-m sideband, D*lnu CR, high-R2 CR
  note_fit_linlog.png  post-fit m2miss in linear and log scale
  note_fit_pulls.png   toy-MC pull distribution of the pyhf fit (validation)
plus the printed control-region purities used in the note.

usage: python analysis/note_plots.py   (expects the standard data/*.root)
"""
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pyhf

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fit_m2miss import BINS, E_TAG_MAX, hists, load, preselect

PLOTS = Path(__file__).resolve().parent.parent / "plots"
M_D0, DM = 1.8648, 0.14543
CONT_W = 0.995

COLORS = {0: "#bdbdbd", 2: "#64b5f6", 3: "#c9a227", 1: "crimson"}
LABELS = {0: "other $B$ decays", 2: r"$B \to D^{*}\ell\nu$",
          3: r"continuum $q\bar{q}$", 1: r"$B \to D^{*}\tau\nu$ (signal)"}


def stack(ax, samples, var, mask_fn, bins, xlabel, title=""):
    vals, ws, cols, labs = [], [], [], []
    for mode in (0, 2, 3, 1):
        v, w = [], []
        for t, wt in samples:
            m = mask_fn(t) & (t["true_mode"] == mode)
            v.append(t[var][m])
            w.append(np.full(int(m.sum()), wt))
        vals.append(np.concatenate(v))
        ws.append(np.concatenate(w))
        cols.append(COLORS[mode])
        labs.append(LABELS[mode])
    ax.hist(vals, bins=bins, weights=ws, stacked=True, color=cols, label=labs)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("candidates / bin")
    if title:
        ax.set_title(title, fontsize=10)


def main():
    bb = load([f"data/generic_{i}.root" for i in range(5)])
    ct = load([f"data/continuum_{i}.root" for i in range(3)])
    # extra columns for the discriminant plots
    import uproot
    def load2(ps, cols):
        parts = [uproot.open(p)["events"].arrays(cols, library="np") for p in ps]
        return {c: np.concatenate([x[c] for x in parts]) for c in cols}
    cols2 = ["m2miss", "m_d0", "delta_m", "r2", "e_tag_cm", "true_mode",
             "lep_true_pid"]
    samples = [(bb, 1.0), (ct, CONT_W)]

    def dstar(t):
        return (np.abs(t["m_d0"] - M_D0) < 0.020) & \
               (np.abs(t["delta_m"] - DM) < 0.0025)

    # --- 1. preselection windows -------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.0))
    stack(axes[0], samples, "m_d0",
          lambda t: np.abs(t["delta_m"] - DM) < 0.0025,
          np.linspace(1.75, 1.98, 60), r"$m(K\pi)$ [GeV]")
    for x in (M_D0 - 0.020, M_D0 + 0.020):
        axes[0].axvline(x, color="k", ls="--", lw=1)
    stack(axes[1], samples, "delta_m",
          lambda t: np.abs(t["m_d0"] - M_D0) < 0.020,
          np.linspace(0.139, 0.165, 60), r"$\Delta m$ [GeV]")
    for x in (DM - 0.0025, DM + 0.0025):
        axes[1].axvline(x, color="k", ls="--", lw=1)
    axes[0].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(PLOTS / "note_presel.png", dpi=150)

    # --- 2. discriminating variables ---------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.0))
    stack(axes[0], samples, "r2", dstar, np.linspace(0, 0.8, 40),
          r"Fox-Wolfram $R_2$", "after $D^{*}$ windows")
    axes[0].axvline(0.3, color="k", ls="--", lw=1)
    stack(axes[1], samples, "e_tag_cm",
          lambda t: dstar(t) & (t["r2"] < 0.3),
          np.linspace(0, 8, 40), r"$E^{\rm CM}_{\rm ROE}$ [GeV]",
          "after $D^{*}$ + $R_2$")
    axes[1].axvline(4.0, color="k", ls="--", lw=1)
    axes[1].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(PLOTS / "note_discrim.png", dpi=150)

    # --- 3. control regions -------------------------------------------------
    def full_but_sr(t):
        return dstar(t) & (t["r2"] < 0.3) & (t["e_tag_cm"] < E_TAG_MAX)

    # NOTE: a Delta-m sideband CR (fake D*) is empty by construction here:
    # the candidate finder is seeded on true D* mesons, so random K-pi-pi
    # combinations are not modeled. Stated as a limitation in the note.
    crs = {
        r"wrong-pairing CR ($E^{\rm CM}_{\rm ROE} > 5$ GeV)":
            lambda t: dstar(t) & (t["r2"] < 0.3) & (t["e_tag_cm"] > 5.0)
                      & (t["m2miss"] > 1.5),
        r"$D^{*}\ell\nu$ CR ($-2 < m^2_{\rm miss} < 0.5$)":
            lambda t: full_but_sr(t) & (t["m2miss"] > -2) & (t["m2miss"] < 0.5),
        r"continuum CR ($R_2 > 0.4$)":
            lambda t: dstar(t) & (t["r2"] > 0.4) & (t["e_tag_cm"] < E_TAG_MAX)
                      & (t["m2miss"] > 1.5),
    }
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.0))
    print("control-region composition (lumi-weighted):")
    for ax, (name, sel) in zip(axes, crs.items()):
        stack(ax, samples, "m2miss", sel, np.linspace(-2, 10, 30),
              r"$m^2_{\rm miss}$ [GeV$^2$]", name)
        tot = sum(w * sel(t).sum() for t, w in samples)
        parts = {m: sum(w * (sel(t) & (t["true_mode"] == m)).sum()
                        for t, w in samples) for m in (0, 1, 2, 3)}
        dom = max(parts, key=parts.get)
        print(f"  {name}: N={tot:.0f}; " +
              ", ".join(f"{LABELS[m].replace('$','')}: {parts[m]/tot:.0%}"
                        for m in (0, 2, 3, 1)))
    axes[2].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(PLOTS / "note_cr.png", dpi=150)

    # --- 4. fit: post-fit lin+log and toy pulls -----------------------------
    sig, bkg, bkg_var, data = hists(samples)
    floor = 1e-3
    bkg = np.maximum(bkg, floor)
    bkg_unc = np.maximum(np.sqrt(bkg_var + (0.10 * bkg) ** 2), floor)
    model = pyhf.simplemodels.uncorrelated_background(
        signal=sig.tolist(), bkg=bkg.tolist(), bkg_uncertainty=bkg_unc.tolist())
    pyhf.set_backend("numpy", "minuit")
    fit_data = np.concatenate([data, model.config.auxdata])
    res = np.asarray(pyhf.infer.mle.fit(fit_data, model,
                                        return_uncertainties=True))
    mu, mu_err = res[model.config.poi_index]
    print(f"nominal fit: mu = {mu:.3f} +- {mu_err:.3f}")

    centers = 0.5 * (BINS[:-1] + BINS[1:])
    width = np.diff(BINS)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    for ax, yscale in zip(axes, ("linear", "log")):
        ax.bar(centers, bkg, width=width, color="#bdbdbd", label="background")
        ax.bar(centers, mu * sig, width=width, bottom=bkg, color="crimson",
               label=rf"$\mu\times$signal ($\mu={mu:.2f}$)")
        ax.errorbar(centers, data, yerr=np.sqrt(np.maximum(data, 1)),
                    fmt="ko", ms=3.5, lw=1, label="pseudo-data")
        ax.set_xlabel(r"$m^2_{\rm miss}$ [GeV$^2$]")
        ax.set_ylabel("candidates / bin")
        ax.set_yscale(yscale)
        if yscale == "linear":
            ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(PLOTS / "note_fit_linlog.png", dpi=150)

    # toy pulls: generate Poisson toys from the mu=1 expectation and refit
    rng = np.random.default_rng(2026)
    expected = np.asarray(model.expected_data(
        pyhf.tensorlib.astensor([1.0] + [1.0] * (len(bkg)))))
    n_main = len(bkg)
    pulls = []
    for i in range(300):
        toy_main = rng.poisson(np.maximum(expected[:n_main], 0))
        toy_aux = rng.poisson(np.maximum(expected[n_main:], 0))
        toy = np.concatenate([toy_main, toy_aux]).astype(float)
        try:
            r = np.asarray(pyhf.infer.mle.fit(toy, model,
                                              return_uncertainties=True))
            m, e = r[model.config.poi_index]
            if e > 0:
                pulls.append((m - 1.0) / e)
        except Exception:
            continue
    pulls = np.array(pulls)
    print(f"toys: {len(pulls)} fits, pull mean = {pulls.mean():+.2f}, "
          f"width = {pulls.std():.2f}")

    # luminosity projection: Asimov expected precision vs integrated lumi
    L0 = 0.906e-3  # ab^-1 equivalent of the pseudo-dataset
    lumis = np.array([0.005, 0.02, 0.1, 0.36, 1.0, 5.0, 50.0]) * 1e-3 * 1000
    # (values in ab^-1: 5/ab steps from 5 fb^-1 to 50 ab^-1)
    lumis = np.array([0.005, 0.02, 0.1, 0.36, 1.0, 5.0, 50.0])
    rels = []
    for L in lumis:
        k = L / L0
        bkg_k = np.maximum(k * bkg, floor)
        # statistical-only projection: background shape treated as known
        # (no systematic placeholder), so the curve is the pure 1/sqrt(L)
        # scaling; the systematic floor is drawn separately.
        unc_k = np.maximum(1e-3 * bkg_k, floor)
        m_k = pyhf.simplemodels.uncorrelated_background(
            signal=(k * sig).tolist(), bkg=bkg_k.tolist(),
            bkg_uncertainty=unc_k.tolist())
        asimov = np.asarray(m_k.expected_data(
            pyhf.tensorlib.astensor([1.0] * (1 + len(bkg)))))
        r = np.asarray(pyhf.infer.mle.fit(asimov, m_k,
                                          return_uncertainties=True))
        rels.append(float(r[m_k.config.poi_index][1]))
    rels = np.array(rels)
    fig, ax = plt.subplots(figsize=(6.0, 4.2))
    ax.loglog(lumis, rels * 100, "o-", color="#5c7fb8",
              label="expected stat. precision (Asimov)")
    ax.axhline(3.0, color="crimson", ls="--", lw=1.2,
               label="indicative syst. floor (~3%)")
    ax.axvline(0.906e-3, color="gray", ls=":", lw=1,
               label="this pseudo-dataset")
    ax.set_xlabel(r"integrated luminosity [ab$^{-1}$]")
    ax.set_ylabel(r"$\delta\mathcal{B}/\mathcal{B}$ [%]")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3, which="both")
    fig.tight_layout()
    fig.savefig(PLOTS / "note_lumi_projection.png", dpi=150)
    for L, r in zip(lumis, rels):
        print(f"  L = {L:g} /ab: expected rel. precision = {r*100:.1f}%")
    fig, ax = plt.subplots(figsize=(5.6, 4.0))
    ax.hist(pulls, bins=np.linspace(-4, 4, 33), color="#5c7fb8",
            histtype="stepfilled")
    ax.set_xlabel(r"pull $(\hat\mu - 1)/\sigma_{\hat\mu}$")
    ax.set_ylabel("toys")
    ax.set_title(f"mean = {pulls.mean():+.2f}, width = {pulls.std():.2f}",
                 fontsize=10)
    fig.tight_layout()
    fig.savefig(PLOTS / "note_fit_pulls.png", dpi=150)
    print("wrote note_presel/discrim/cr/fit_linlog/fit_pulls .png")


if __name__ == "__main__":
    main()
