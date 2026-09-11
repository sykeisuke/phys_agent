#!/usr/bin/env python
"""Continuum e+e- -> qq (u,d,s,c) background: Pythia8 -> fast sim -> ntuple
in one pass (no HepMC intermediate — the Pythia mother/daughter structure
does not map cleanly onto HepMC vertices, and the file would be huge).

Beams match the BBbar driver: e- 7 GeV (+z) x e+ 4 GeV (-z). The candidate
definition and every branch are identical to fastsim/make_ntuple.py (v2):
a true D*+- with 3 charged tracks + the highest-p* charge-correlated muon,
beam-constrained variables in the CM frame, Fox-Wolfram R2. Truth-B branches
are NaN and true_mode = 3 (continuum).

For luminosity weighting, the printout reports N_generated and sigma:

    weight = (N_BB * sigma_cont / sigma_BB) / N_cont_generated

usage: python generation/generate_continuum.py <nEvents> <out.root> <seed>
"""
import sys
from pathlib import Path

import numpy as np
import pythia8
import uproot

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "fastsim"))
from smear import DetectorConfig, detect_track
from make_ntuple import (CHARGED_STABLE, NEUTRINOS, E_B_CM, M_B, P_B_CM,
                         P_B_MAG, minv, minv2, to_cm)


def four_vec(p):
    return np.array([p.e(), p.px(), p.py(), p.pz()])


def stable_charged(ev, i):
    p = ev[i]
    if p.isFinal():
        return [i] if abs(p.id()) in CHARGED_STABLE else []
    out = []
    for d in p.daughterList():
        out.extend(stable_charged(ev, d))
    return out


def find_candidate(ev):
    """Mirror of make_ntuple.find_candidate on a Pythia event record.
    Returns (dst_idx, d0_track_idxs, slow_idx, mu_idx) or None."""
    for i in range(1, ev.size()):
        if abs(ev[i].id()) != 413:
            continue
        dau = ev[i].daughterList()
        if len(dau) == 1 and abs(ev[dau[0]].id()) == 413:
            continue  # carbon copy — use the final one
        tracks = stable_charged(ev, i)
        if len(tracks) != 3:
            continue
        d0 = next((d for d in dau if abs(ev[d].id()) == 421), None)
        if d0 is None:
            continue
        d0_tracks = stable_charged(ev, d0)
        slow = [t for t in tracks if t not in set(d0_tracks)]
        if len(d0_tracks) != 2 or len(slow) != 1:
            continue
        track_set = set(tracks)
        mus = [j for j in range(1, ev.size())
               if abs(ev[j].id()) == 13 and ev[j].isFinal()
               and j not in track_set and ev[j].id() * ev[i].id() > 0]
        if not mus:
            continue
        mu = max(mus, key=lambda j: np.linalg.norm(to_cm(four_vec(ev[j]))[1:]))
        return i, d0_tracks, slow[0], mu
    return None


def fox_wolfram_r2(ev):
    ps = [to_cm(four_vec(ev[i]))[1:] for i in range(1, ev.size())
          if ev[i].isFinal() and abs(ev[i].id()) not in NEUTRINOS]
    mags = np.array([np.linalg.norm(p) for p in ps])
    keep = mags > 1e-9
    ps = np.array([p for p, k in zip(ps, keep) if k])
    mags = mags[keep]
    if len(ps) < 2:
        return 1.0
    cos = np.clip((ps @ ps.T) / np.outer(mags, mags), -1.0, 1.0)
    w = np.outer(mags, mags)
    return (w * 0.5 * (3.0 * cos ** 2 - 1.0)).sum() / w.sum()


def main():
    n_events, out_path, seed = int(sys.argv[1]), sys.argv[2], int(sys.argv[3])
    cfg = DetectorConfig()
    rng = np.random.default_rng(seed)

    py = pythia8.Pythia("", False)
    for s in ["Beams:idA = 11", "Beams:idB = -11", "Beams:frameType = 2",
              "Beams:eA = 7.0", "Beams:eB = 4.0",
              "WeakSingleBoson:ffbar2gmZ = on",
              "23:onMode = off", "23:onIfAny = 1 2 3 4",
              "Random:setSeed = on", f"Random:seed = {seed % 900000000}",
              "Print:quiet = on"]:
        py.readString(s)
    py.init()

    cols = {k: [] for k in [
        "m2miss", "plep_star", "q2", "m_d0", "delta_m", "cos_by", "r2",
        "p_lep_lab", "costh_lep_lab", "p_dst_lab",
        "m2miss_true", "plep_star_true", "q2_true",
        "true_mode", "mode_id", "event"]}
    n_cand = n_rec = 0

    for ievt in range(n_events):
        if not py.next():
            continue
        if (ievt + 1) % 200000 == 0:
            print(f"generated {ievt + 1} / {n_events} "
                  f"({n_rec} reconstructed)", flush=True)
        cand = find_candidate(py.event)
        if cand is None:
            continue
        n_cand += 1
        dst_i, d0_tracks, slow_i, mu_i = cand
        ev = py.event

        sm_d0 = [detect_track(four_vec(ev[t]), cfg, rng) for t in d0_tracks]
        sm_slow = detect_track(four_vec(ev[slow_i]), cfg, rng)
        sm_mu = detect_track(four_vec(ev[mu_i]), cfg, rng)
        if any(s is None for s in sm_d0) or sm_slow is None or sm_mu is None:
            continue
        n_rec += 1

        pD0 = np.sum(sm_d0, axis=0)
        pDst = pD0 + sm_slow
        pDst_cm = to_cm(pDst)
        pMu_cm = to_cm(sm_mu)
        pY = pDst_cm + pMu_cm
        pY_mag = np.linalg.norm(pY[1:])
        cols["m2miss"].append(minv2(P_B_CM - pY))
        cols["plep_star"].append(np.linalg.norm(pMu_cm[1:]))
        cols["q2"].append(minv2(P_B_CM - pDst_cm))
        cols["m_d0"].append(minv(pD0))
        cols["delta_m"].append(minv(pDst) - minv(pD0))
        cols["cos_by"].append(
            (2.0 * E_B_CM * pY[0] - M_B ** 2 - minv2(pY))
            / (2.0 * P_B_MAG * pY_mag) if pY_mag > 0 else np.nan)
        cols["r2"].append(fox_wolfram_r2(ev))
        plep3 = sm_mu[1:]
        cols["p_lep_lab"].append(np.linalg.norm(plep3))
        cols["costh_lep_lab"].append(plep3[2] / np.linalg.norm(plep3))
        cols["p_dst_lab"].append(np.linalg.norm(pDst[1:]))
        cols["m2miss_true"].append(np.nan)
        cols["plep_star_true"].append(np.nan)
        cols["q2_true"].append(np.nan)
        cols["true_mode"].append(3)
        cols["mode_id"].append(99)
        cols["event"].append(ievt)

    arrays = {k: np.array(v, dtype=np.int32 if k in ("true_mode", "mode_id", "event")
                          else np.float64) for k, v in cols.items()}
    with uproot.recreate(out_path) as f:
        f["events"] = arrays

    sigma_nb = py.infoPython().sigmaGen() * 1e6
    print(f"{n_events} continuum events (seed {seed}): {n_cand} candidates, "
          f"{n_rec} reconstructed -> {out_path}")
    print(f"sigma = {sigma_nb:.3f} nb  "
          f"(luminosity weight vs BBbar: N_BB * {sigma_nb:.3f}/1.1 / {n_events})")


if __name__ == "__main__":
    main()
