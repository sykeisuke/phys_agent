#!/usr/bin/env python
"""B0 -> K*0 l+ l- sensitivity at 1/ab, with the charmonium-veto demonstration.

Signal (BTOSLLBALL) and the dominant peaking background
B0 -> J/psi(-> l l) K*0 share the same visible final state; the veto
windows in m(l+l-) remove the charmonium resonances. Yields:

    N = 2 f00 sigma_BB L x BF x B(K*0 -> K+ pi-) x [B(J/psi -> ll)] x eff

Combinatorial (non-peaking) backgrounds are not modeled here — Mbc/deltaE
sidebands handle them in a real analysis.

usage: python analysis/sensitivity_kstll.py
       (expects data/sig_kstll.root and data/bkg_jpsikst.root)
"""
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import uproot

SIGMA_BB_NB, LUMI_INV_AB, F00 = 1.1, 1.0, 0.486
N_B0 = 2 * F00 * SIGMA_BB_NB * 1e9 * LUMI_INV_AB
B_KST_KPI = 2 / 3
BF_SIG = {11: 1.03e-6, 13: 1.05e-6}      # B0 -> K*0 ee / mumu (decay table)
BF_JPSI_KST = 1.27e-3
B_JPSI_LL = {11: 0.0597, 13: 0.0596}

# selection
MBC_WIN = 0.030          # |mbc - m_B| [GeV]
DE_LO, DE_HI = -0.30, 0.25
# asymmetric charmonium vetoes (lo, hi) around J/psi and psi(2S); the ee
# windows extend further down to catch the FSR/bremsstrahlung tail
VETO = {11: [(3.097 - 0.25, 3.097 + 0.10), (3.686 - 0.15, 3.686 + 0.08)],
        13: [(3.097 - 0.12, 3.097 + 0.08), (3.686 - 0.10, 3.686 + 0.08)]}
M_B = 5.2795

N_GEN = {"sig": 10000, "jpsi": 5000}     # generated events per sample


def load(path):
    return uproot.open(path)["events"].arrays(
        ["mbc", "delta_e", "m_ll", "lep_flavor"], library="np")


def selected(t, veto=True):
    m = (np.abs(t["mbc"] - M_B) < MBC_WIN) & \
        (t["delta_e"] > DE_LO) & (t["delta_e"] < DE_HI)
    if veto:
        for fl in (11, 13):
            infl = t["lep_flavor"] == fl
            for lo, hi in VETO[fl]:
                m &= ~(infl & (t["m_ll"] > lo) & (t["m_ll"] < hi))
    return m


def main():
    sig = load("data/sig_kstll.root")
    jpsi = load("data/bkg_jpsikst.root")

    print(f"{'channel':8s} {'eff':>6s} {'S @1/ab':>8s} "
          f"{'J/psiK* before veto':>20s} {'after veto':>11s} {'dBF/BF':>7s}")
    for fl, name in [(11, "ee"), (13, "mumu")]:
        # forced 50/50 flavor mix -> per-flavor N_gen = N_GEN/2
        s_m = sig["lep_flavor"] == fl
        j_m = jpsi["lep_flavor"] == fl
        eff_s = selected(sig)[s_m].sum() / (N_GEN["sig"] / 2)
        eff_j0 = selected(jpsi, veto=False)[j_m].sum() / (N_GEN["jpsi"] / 2)
        eff_j1 = selected(jpsi, veto=True)[j_m].sum() / (N_GEN["jpsi"] / 2)
        S = N_B0 * BF_SIG[fl] * B_KST_KPI * eff_s
        J0 = N_B0 * BF_JPSI_KST * B_JPSI_LL[fl] * B_KST_KPI * eff_j0
        J1 = N_B0 * BF_JPSI_KST * B_JPSI_LL[fl] * B_KST_KPI * eff_j1
        rel = np.sqrt(S + J1) / S
        print(f"{name:8s} {eff_s:6.1%} {S:8.0f} {J0:20.0f} {J1:11.1f} {rel:7.1%}")

    # demo plot: m_ll and Mbc, lumi-weighted
    out = Path(__file__).resolve().parent.parent / "plots"
    out.mkdir(exist_ok=True)
    w_sig = N_B0 * (BF_SIG[11] + BF_SIG[13]) / 2 * B_KST_KPI / (N_GEN["sig"])
    w_j = N_B0 * BF_JPSI_KST * 0.0596 * B_KST_KPI / (N_GEN["jpsi"])
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    base_s = (np.abs(sig["mbc"] - M_B) < MBC_WIN)
    base_j = (np.abs(jpsi["mbc"] - M_B) < MBC_WIN)
    bins = np.linspace(0.2, 4.6, 80)
    axes[0].hist(jpsi["m_ll"][base_j], bins=bins, weights=np.full(base_j.sum(), w_j),
                 color="#c9a227", label=r"$B \to J/\psi K^{*}$ (peaking bkg)")
    axes[0].hist(sig["m_ll"][base_s], bins=bins, weights=np.full(base_s.sum(), w_sig),
                 histtype="step", lw=2, color="crimson", label=r"$B \to K^{*}\ell\ell$ signal")
    for lo, hi in VETO[11]:
        axes[0].axvspan(lo, hi, color="gray", alpha=0.3)
    axes[0].set_yscale("log")
    axes[0].set_xlabel(r"$m(\ell^+\ell^-)$ [GeV]")
    axes[0].set_ylabel("candidates / bin @ 1 ab$^{-1}$")
    axes[0].legend(fontsize=9)
    bins = np.linspace(5.2, 5.3, 50)
    sel_s = selected(sig)
    sel_j = selected(jpsi)
    axes[1].hist(jpsi["mbc"][sel_j], bins=bins, weights=np.full(sel_j.sum(), w_j),
                 color="#c9a227", label=r"$J/\psi K^{*}$ after veto")
    axes[1].hist(sig["mbc"][sel_s], bins=bins, weights=np.full(sel_s.sum(), w_sig),
                 histtype="step", lw=2, color="crimson", label="signal after veto")
    axes[1].set_xlabel(r"$M_{\rm bc}$ [GeV]")
    axes[1].set_ylabel("candidates / bin @ 1 ab$^{-1}$")
    axes[1].legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(out / "kstll_veto_demo.png", dpi=150)
    print("wrote plots/kstll_veto_demo.png")

    # selection variables: Mbc and deltaE for signal, by lepton flavor
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.0))
    for fl, name, color in [(11, "ee", "#3a6ea5"), (13, r"$\mu\mu$", "crimson")]:
        m = sig["lep_flavor"] == fl
        axes[0].hist(sig["mbc"][m], bins=np.linspace(5.2, 5.3, 50),
                     histtype="step", lw=2, color=color, label=name)
        axes[1].hist(sig["delta_e"][m], bins=np.linspace(-0.6, 0.3, 60),
                     histtype="step", lw=2, color=color, label=name)
    axes[0].axvline(M_B - MBC_WIN, color="k", ls="--", lw=1)
    axes[0].axvline(M_B + MBC_WIN, color="k", ls="--", lw=1)
    axes[1].axvline(DE_LO, color="k", ls="--", lw=1)
    axes[1].axvline(DE_HI, color="k", ls="--", lw=1)
    axes[0].set_xlabel(r"$M_{\rm bc}$ [GeV]")
    axes[1].set_xlabel(r"$\Delta E$ [GeV]")
    for ax in axes:
        ax.set_ylabel("candidates")
        ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(out / "kstll_sel.png", dpi=150)
    print("wrote plots/kstll_sel.png")


if __name__ == "__main__":
    main()
