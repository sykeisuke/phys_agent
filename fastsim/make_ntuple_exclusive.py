#!/usr/bin/env python
"""Ntuple producer for exclusive forced modes (truth-seeded, mode-agnostic).

Handles two topologies, detected automatically per event:
  * semileptonic  B -> hadrons + mu nu      (one muon among the B daughters)
  * fully charged B -> hadrons + mu+ mu-    (two muons, e.g. B0 -> K*0 mu mu)

The signal-side B is found in truth; ALL stable charged descendants and
photons of its hadronic daughters plus the muon(s) are passed through the
fast simulation, and the candidate is kept only if everything is detected.

Variables (beam-constrained, definitions as in make_ntuple.py):
  m2miss, plep_star, q2, m_visible, r2, ROE (e_tag_cm, m_tag, n_roe, q_roe)
plus, for the fully reconstructed topology:
  mbc     = sqrt(E_beam^2 - |p_vis|^2)  in the CM frame (basf2 `Mbc`)
  delta_e = E_vis - E_beam              in the CM frame (basf2 `deltaE`)
  m_ll    = m(mu+ mu-)                  (charmonium-veto variable)
(mbc/delta_e are filled for both topologies; m_ll is NaN with one muon.)

usage: python fastsim/make_ntuple_exclusive.py <in.hepmc> <out.root> <mode_id> [seed]
"""
import sys
from pathlib import Path

import numpy as np
import pyhepmc
import uproot

sys.path.insert(0, str(Path(__file__).resolve().parent))
from smear import DetectorConfig, detect_photon, detect_track
from make_ntuple import (CHARGED_STABLE, E_B_CM, P_B_CM, boost_to_rest,
                         count_b_decays, four_vec, fox_wolfram_r2, minv,
                         minv2, roe_tag_momentum, to_cm)

MU_PIDS = {13, -13}
B_ALL = {511, -511, 521, -521}
NEUTRALS_SKIP = {12, 14, 16, 22}


def visible_descendants(part):
    """Stable charged descendants and photons of a particle."""
    out = []
    if not part.end_vertex:
        if abs(part.pid) in CHARGED_STABLE or part.pid == 22:
            out.append(part)
        return out
    for d in part.end_vertex.particles_out:
        out.extend(visible_descendants(d))
    return out


def find_signal_b(event):
    """The forced B -> hadrons + mu nu (1 muon) or hadrons + mu mu (2 muons).
    Returns (hadron daughters, muons) or None."""
    for part in event.particles:
        if part.pid not in B_ALL or not part.end_vertex:
            continue
        dau = part.end_vertex.particles_out
        mus = [d for d in dau if d.pid in MU_PIDS]
        hads = [d for d in dau if abs(d.pid) not in NEUTRALS_SKIP | {13}]
        if len(mus) in (1, 2) and len(hads) >= 1 and len(hads) + len(mus) >= 3:
            return hads, mus
    return None


def main():
    in_path, out_path, mode_id = sys.argv[1], sys.argv[2], int(sys.argv[3])
    seed = int(sys.argv[4]) if len(sys.argv) > 4 else 42
    cfg = DetectorConfig()
    rng = np.random.default_rng(seed)

    cols = {k: [] for k in [
        "m2miss", "plep_star", "q2", "m_visible", "mbc", "delta_e", "m_ll",
        "r2", "e_tag_cm", "m_tag", "n_roe", "q_roe",
        "n_tracks", "n_photons", "n_mu", "mode_id", "event"]}
    n_events = n_cand = n_rec = 0

    with pyhepmc.open(in_path) as f:
        for ievt, event in enumerate(f):
            n_events += 1
            found = find_signal_b(event)
            if found is None:
                continue
            hads, mus = found
            n_cand += 1

            vis = []
            for h in hads:
                vis.extend(visible_descendants(h))
            smeared = []
            n_trk = n_pho = 0
            ok = True
            for p in vis:
                v = four_vec(p)
                if p.pid == 22:
                    s = detect_photon(v, cfg, rng)
                    n_pho += 1
                else:
                    s = detect_track(v, cfg, rng)
                    n_trk += 1
                if s is None:
                    ok = False
                    break
                smeared.append(s)
            sm_mus = [detect_track(four_vec(m), cfg, rng) for m in mus]
            if not ok or any(m is None for m in sm_mus) or not smeared:
                continue
            n_rec += 1

            pHad = np.sum(smeared, axis=0)
            pMu = np.sum(sm_mus, axis=0)
            pHad_cm = to_cm(pHad)
            pMu_cm = to_cm(pMu)
            pY = pHad_cm + pMu_cm
            cols["m2miss"].append(minv2(P_B_CM - pY))
            cols["plep_star"].append(
                max(np.linalg.norm(to_cm(m)[1:]) for m in sm_mus))
            cols["q2"].append(minv2(P_B_CM - pHad_cm))
            cols["m_visible"].append(minv(pHad))
            cols["mbc"].append(np.sqrt(max(
                E_B_CM ** 2 - float(pY[1:] @ pY[1:]), 0.0)))
            cols["delta_e"].append(pY[0] - E_B_CM)
            cols["m_ll"].append(minv(np.sum(sm_mus, axis=0))
                                if len(sm_mus) == 2 else np.nan)
            cols["r2"].append(fox_wolfram_r2(event))
            used = {p.id for p in vis} | {m.id for m in mus}
            p_tag, n_roe, q_roe = roe_tag_momentum(event, used, cfg, rng)
            cols["e_tag_cm"].append(to_cm(p_tag)[0])
            cols["m_tag"].append(minv(p_tag))
            cols["n_roe"].append(n_roe)
            cols["q_roe"].append(q_roe)
            cols["n_tracks"].append(n_trk)
            cols["n_photons"].append(n_pho)
            cols["n_mu"].append(len(sm_mus))
            cols["mode_id"].append(mode_id)
            cols["event"].append(ievt)

    arrays = {k: np.array(v, dtype=np.int32
                          if k in ("n_roe", "q_roe", "n_tracks", "n_photons",
                                   "n_mu", "mode_id", "event")
                          else np.float64) for k, v in cols.items()}
    with uproot.recreate(out_path) as f:
        f["events"] = arrays

    print(f"{in_path}: {n_events} events, {n_cand} signal decays, "
          f"{n_rec} fully reconstructed (eff = {n_rec / max(n_cand, 1):.1%}) "
          f"-> {out_path} (mode_id={mode_id}, seed={seed})")


if __name__ == "__main__":
    main()
