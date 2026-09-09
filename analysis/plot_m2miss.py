#!/usr/bin/env python
"""Truth-level discriminating variables for B -> D* tau nu vs B -> D* mu nu.

Reads HepMC3 ascii files produced by generation/bin/generate, finds the
signal-side B (the B whose daughters are D* + lepton/tau + neutrino), and
plots m2_miss, p*_lep (lepton momentum in the B rest frame) and q2.

usage: python analysis/plot_m2miss.py data/signal_taunu.hepmc data/norm_munu.hepmc
"""
import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import pyhepmc

B_PIDS = {511, -511}
DST_PIDS = {413, -413}
TAU_PIDS = {15, -15}
MU_PIDS = {13, -13}


def four_vec(p):
    m = p.momentum
    return np.array([m.e, m.px, m.py, m.pz])


def minv2(v):
    return v[0] ** 2 - v[1] ** 2 - v[2] ** 2 - v[3] ** 2


def boost_to_rest(p, frame):
    """Boost four-vector p into the rest frame of four-vector `frame`."""
    m = np.sqrt(max(minv2(frame), 1e-12))
    beta = -frame[1:] / frame[0]
    b2 = beta @ beta
    if b2 < 1e-16:
        return p.copy()
    gamma = 1.0 / np.sqrt(1.0 - b2)
    bp = beta @ p[1:]
    e = gamma * (p[0] + bp)
    vec = p[1:] + ((gamma - 1.0) * bp / b2 + gamma * p[0]) * beta
    return np.array([e, *vec])


def analyze(path, tau_mode):
    """Return arrays (m2_miss, p_lep_star, q2) for the signal B in each event."""
    m2m, pls, q2s = [], [], []
    with pyhepmc.open(path) as f:
        for event in f:
            for part in event.particles:
                if part.pid not in B_PIDS or not part.end_vertex:
                    continue
                dau = part.end_vertex.particles_out
                pids = [d.pid for d in dau]
                has_dst = any(p in DST_PIDS for p in pids)
                lep_pids = TAU_PIDS if tau_mode else MU_PIDS
                if not (has_dst and any(p in lep_pids for p in pids)):
                    continue
                pB = four_vec(part)
                pDst = four_vec(next(d for d in dau if d.pid in DST_PIDS))
                if tau_mode:
                    tau = next(d for d in dau if d.pid in TAU_PIDS)
                    if not tau.end_vertex:
                        continue
                    mus = [d for d in tau.end_vertex.particles_out if d.pid in MU_PIDS]
                    if not mus:
                        continue
                    pLep = four_vec(mus[0])
                else:
                    pLep = four_vec(next(d for d in dau if d.pid in MU_PIDS))
                m2m.append(minv2(pB - pDst - pLep))
                pls.append(np.linalg.norm(boost_to_rest(pLep, pB)[1:]))
                q2s.append(minv2(pB - pDst))
                break
    return np.array(m2m), np.array(pls), np.array(q2s)


def main():
    sig_path, norm_path = sys.argv[1], sys.argv[2]
    sig = analyze(sig_path, tau_mode=True)
    norm = analyze(norm_path, tau_mode=False)
    print(f"signal B -> D* tau nu : {len(sig[0])} events")
    print(f"norm   B -> D* mu  nu : {len(norm[0])} events")

    out = Path(__file__).resolve().parent.parent / "plots"
    out.mkdir(exist_ok=True)

    specs = [
        ("m2miss", r"$m^2_{\mathrm{miss}}$ [GeV$^2$]", np.linspace(-1, 10, 56)),
        ("plep_star", r"$p^{*}_{\ell}$ [GeV]", np.linspace(0, 2.5, 51)),
        ("q2", r"$q^2$ [GeV$^2$]", np.linspace(0, 12, 49)),
    ]
    for i, (name, label, bins) in enumerate(specs):
        fig, ax = plt.subplots(figsize=(6, 4.2))
        ax.hist(norm[i], bins=bins, histtype="stepfilled", alpha=0.45,
                label=r"$B \to D^{*}\mu\nu$ (norm.)", density=True)
        ax.hist(sig[i], bins=bins, histtype="step", lw=2, color="crimson",
                label=r"$B \to D^{*}\tau\nu,\ \tau \to \mu\nu\nu$ (signal)", density=True)
        ax.set_xlabel(label)
        ax.set_ylabel("normalized entries")
        ax.legend()
        ax.set_title("EvtGen truth level")
        fig.tight_layout()
        fig.savefig(out / f"{name}.png", dpi=150)
        print(f"wrote plots/{name}.png")


if __name__ == "__main__":
    main()
