#!/usr/bin/env python
"""Phase 2: apply the fast detector simulation and compare with truth.

For each event the signal-side B (B -> D* + lepton + nu) is found, the four
charged final-state tracks of the visible system (K, pi, slow pi from the D*
chain, and the muon) are passed through the detector model in smear.py, and
the discriminating variables are recomputed with the smeared tracks:

    m2_miss = (p_B - p_D*(rec) - p_lep(rec))^2
    p*_lep  = |p| of the smeared lepton boosted into the (truth) B frame
    q2      = (p_B - p_D*(rec))^2

p_B is taken from truth (a stand-in for the beam/Btag constraint until
Phase 3). The reconstructed D* is the sum of the three smeared track
four-vectors, so FSR photons are lost -- as they would be for a
track-only reconstruction.

usage: python fastsim/apply_fastsim.py data/signal_taunu.hepmc data/norm_munu.hepmc [seed]
"""
import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import pyhepmc

sys.path.insert(0, str(Path(__file__).resolve().parent))
from smear import DetectorConfig, detect_track

B_PIDS = {511, -511}
DST_PIDS = {413, -413}
TAU_PIDS = {15, -15}
MU_PIDS = {13, -13}
CHARGED_STABLE = {211, 321, 13, 11, 2212}  # |pid| of charged tracks we care about


def four_vec(p):
    m = p.momentum
    return np.array([m.e, m.px, m.py, m.pz])


def minv2(v):
    return v[0] ** 2 - v[1] ** 2 - v[2] ** 2 - v[3] ** 2


def boost_to_rest(p, frame):
    m2 = minv2(frame)
    beta = -frame[1:] / frame[0]
    b2 = beta @ beta
    if b2 < 1e-16:
        return p.copy()
    gamma = 1.0 / np.sqrt(1.0 - b2)
    bp = beta @ p[1:]
    e = gamma * (p[0] + bp)
    vec = p[1:] + ((gamma - 1.0) * bp / b2 + gamma * p[0]) * beta
    return np.array([e, *vec])


def charged_descendants(part):
    """Recursively collect stable charged descendants of a particle."""
    out = []
    if not part.end_vertex:
        if abs(part.pid) in CHARGED_STABLE:
            out.append(part)
        return out
    for d in part.end_vertex.particles_out:
        out.extend(charged_descendants(d))
    return out


def analyze(path, tau_mode, cfg, rng):
    """Return dict with truth and smeared arrays plus reconstruction counts."""
    truth = {"m2miss": [], "plep_star": [], "q2": []}
    rec = {"m2miss": [], "plep_star": [], "q2": []}
    n_sig, n_rec = 0, 0

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
                dst = next(d for d in dau if d.pid in DST_PIDS)
                if tau_mode:
                    tau = next(d for d in dau if d.pid in TAU_PIDS)
                    if not tau.end_vertex:
                        continue
                    mus = [d for d in tau.end_vertex.particles_out if d.pid in MU_PIDS]
                    if not mus:
                        continue
                    mu = mus[0]
                else:
                    mu = next(d for d in dau if d.pid in MU_PIDS)
                n_sig += 1

                pB = four_vec(part)
                pDst_true = four_vec(dst)
                pLep_true = four_vec(mu)
                truth["m2miss"].append(minv2(pB - pDst_true - pLep_true))
                truth["plep_star"].append(
                    np.linalg.norm(boost_to_rest(pLep_true, pB)[1:]))
                truth["q2"].append(minv2(pB - pDst_true))

                # --- fast sim: K, pi, slow pi from the D* chain + the muon ---
                dst_tracks = charged_descendants(dst)
                if len(dst_tracks) != 3:  # unexpected chain, skip
                    break
                smeared = [detect_track(four_vec(t), cfg, rng) for t in dst_tracks]
                mu_smeared = detect_track(pLep_true, cfg, rng)
                if any(s is None for s in smeared) or mu_smeared is None:
                    break  # a track was lost -> event not reconstructed
                n_rec += 1
                pDst_rec = np.sum(smeared, axis=0)
                rec["m2miss"].append(minv2(pB - pDst_rec - mu_smeared))
                rec["plep_star"].append(
                    np.linalg.norm(boost_to_rest(mu_smeared, pB)[1:]))
                rec["q2"].append(minv2(pB - pDst_rec))
                break

    return ({k: np.array(v) for k, v in truth.items()},
            {k: np.array(v) for k, v in rec.items()},
            n_sig, n_rec)


def main():
    sig_path, norm_path = sys.argv[1], sys.argv[2]
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 42
    cfg = DetectorConfig()
    rng = np.random.default_rng(seed)

    sig_t, sig_r, sig_n, sig_nrec = analyze(sig_path, True, cfg, rng)
    norm_t, norm_r, norm_n, norm_nrec = analyze(norm_path, False, cfg, rng)

    print(f"detector model: sigma_p/p = {cfg.sigma_p_over_p:.3%}, "
          f"{np.degrees(cfg.theta_min):.0f} < theta < {np.degrees(cfg.theta_max):.0f} deg, "
          f"track eff = {cfg.track_eff:.0%}  (seed {seed})")
    for label, n, nrec in [("signal B -> D* tau nu", sig_n, sig_nrec),
                           ("norm   B -> D* mu  nu", norm_n, norm_nrec)]:
        print(f"{label}: {nrec}/{n} reconstructed "
              f"(eff = {nrec / n:.1%})")

    out = Path(__file__).resolve().parent.parent / "plots"
    out.mkdir(exist_ok=True)

    specs = [
        ("m2miss", r"$m^2_{\mathrm{miss}}$ [GeV$^2$]", np.linspace(-1, 10, 56)),
        ("plep_star", r"$p^{*}_{\ell}$ [GeV]", np.linspace(0, 2.5, 51)),
        ("q2", r"$q^2$ [GeV$^2$]", np.linspace(0, 12, 49)),
    ]

    # truth vs smeared, per mode
    for name, label, bins in specs:
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=False)
        for ax, t, r, title in [
            (axes[0], sig_t, sig_r, r"$B \to D^{*}\tau\nu$ (signal)"),
            (axes[1], norm_t, norm_r, r"$B \to D^{*}\mu\nu$ (norm.)"),
        ]:
            ax.hist(t[name], bins=bins, histtype="stepfilled", alpha=0.4,
                    color="gray", label="truth", density=True)
            ax.hist(r[name], bins=bins, histtype="step", lw=2,
                    color="tab:blue", label="fast sim", density=True)
            ax.set_xlabel(label)
            ax.set_ylabel("normalized entries")
            ax.set_title(title)
            ax.legend()
        fig.tight_layout()
        fig.savefig(out / f"{name}_fastsim_vs_truth.png", dpi=150)
        print(f"wrote plots/{name}_fastsim_vs_truth.png")

    # smeared signal vs normalization (post-fastsim discrimination)
    for name, label, bins in specs:
        fig, ax = plt.subplots(figsize=(6, 4.2))
        ax.hist(norm_r[name], bins=bins, histtype="stepfilled", alpha=0.45,
                label=r"$B \to D^{*}\mu\nu$ (norm.)", density=True)
        ax.hist(sig_r[name], bins=bins, histtype="step", lw=2, color="crimson",
                label=r"$B \to D^{*}\tau\nu$ (signal)", density=True)
        ax.set_xlabel(label)
        ax.set_ylabel("normalized entries")
        ax.set_title("fast sim (smeared)")
        ax.legend()
        fig.tight_layout()
        fig.savefig(out / f"{name}_fastsim.png", dpi=150)
        print(f"wrote plots/{name}_fastsim.png")

    # zoom on the m2miss peak of the normalization mode: resolution effect
    fig, ax = plt.subplots(figsize=(6, 4.2))
    bins = np.linspace(-0.5, 0.5, 101)
    ax.hist(norm_t["m2miss"], bins=bins, histtype="stepfilled", alpha=0.4,
            color="gray", label="truth", density=True)
    ax.hist(norm_r["m2miss"], bins=bins, histtype="step", lw=2,
            color="tab:blue", label="fast sim", density=True)
    ax.set_xlabel(r"$m^2_{\mathrm{miss}}$ [GeV$^2$]")
    ax.set_ylabel("normalized entries")
    ax.set_title(r"$B \to D^{*}\mu\nu$: $m^2_{\mathrm{miss}}$ peak")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "m2miss_peak_zoom.png", dpi=150)
    print("wrote plots/m2miss_peak_zoom.png")

    # numeric resolution summary
    core = norm_r["m2miss"][np.abs(norm_r["m2miss"]) < 0.5]
    print(f"norm-mode m2_miss after smearing: mean = {core.mean():+.4f} GeV^2, "
          f"RMS(|m2|<0.5) = {core.std():.4f} GeV^2")


if __name__ == "__main__":
    main()
