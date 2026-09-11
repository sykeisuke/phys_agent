#!/usr/bin/env python
"""Ntuple producer for the charged-B D_s modes (truth-seeded, mode-agnostic).

Works for any forced sample of the form  B -> X_c X_K mu nu  (e.g. the
B_DsstKstmunu / B_DsK1munu / B_Ds1Kmunu decay files): the signal-side B is
found in truth, ALL stable charged descendants and photons of its hadronic
daughters are passed through the fast simulation, and the candidate is kept
only if every one of them is detected. Variables are beam-constrained and
identical in definition to fastsim/make_ntuple.py:
m2miss, plep_star, q2, m_visible (mass of the hadronic system), r2,
e_tag_cm/m_tag/n_roe/q_roe from the rest of event.

This is a first-pass efficiency/sensitivity tool: no combinatorial
candidate finding, no D*-style mass windows (the modes have different
sub-resonances). Use it to get per-mode efficiencies and m2miss shapes.

usage: python fastsim/make_ntuple_ds.py <in.hepmc> <out.root> <mode_id> [seed]
"""
import sys
from pathlib import Path

import numpy as np
import pyhepmc
import uproot

sys.path.insert(0, str(Path(__file__).resolve().parent))
from smear import DetectorConfig, detect_photon, detect_track
from make_ntuple import (CHARGED_STABLE, E_B_CM, P_B_CM, boost_to_rest,
                         charge_of, count_b_decays, four_vec,
                         fox_wolfram_r2, minv, minv2, roe_tag_momentum, to_cm)

MU_PIDS = {13, -13}
B_CHARGED = {521, -521}


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
    """The forced charged B -> hadrons + mu + nu decay.
    Returns (hadron daughters, mu) or None."""
    for part in event.particles:
        if part.pid not in B_CHARGED or not part.end_vertex:
            continue
        dau = part.end_vertex.particles_out
        mus = [d for d in dau if d.pid in MU_PIDS]
        hads = [d for d in dau if abs(d.pid) not in (12, 13, 14, 16, 22)]
        if len(mus) == 1 and len(hads) >= 2:
            return hads, mus[0]
    return None


def main():
    in_path, out_path, mode_id = sys.argv[1], sys.argv[2], int(sys.argv[3])
    seed = int(sys.argv[4]) if len(sys.argv) > 4 else 42
    cfg = DetectorConfig()
    rng = np.random.default_rng(seed)

    cols = {k: [] for k in [
        "m2miss", "plep_star", "q2", "m_visible", "r2",
        "e_tag_cm", "m_tag", "n_roe", "q_roe",
        "n_tracks", "n_photons", "mode_id", "event"]}
    n_events = n_cand = n_rec = 0

    with pyhepmc.open(in_path) as f:
        for ievt, event in enumerate(f):
            n_events += 1
            found = find_signal_b(event)
            if found is None:
                continue
            hads, mu = found
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
            sm_mu = detect_track(four_vec(mu), cfg, rng)
            if not ok or sm_mu is None or not smeared:
                continue
            n_rec += 1

            pHad = np.sum(smeared, axis=0)
            pHad_cm = to_cm(pHad)
            pMu_cm = to_cm(sm_mu)
            pY = pHad_cm + pMu_cm
            cols["m2miss"].append(minv2(P_B_CM - pY))
            cols["plep_star"].append(np.linalg.norm(pMu_cm[1:]))
            cols["q2"].append(minv2(P_B_CM - pHad_cm))
            cols["m_visible"].append(minv(pHad))
            cols["r2"].append(fox_wolfram_r2(event))
            used = {p.id for p in vis} | {mu.id}
            p_tag, n_roe, q_roe = roe_tag_momentum(event, used, cfg, rng)
            cols["e_tag_cm"].append(to_cm(p_tag)[0])
            cols["m_tag"].append(minv(p_tag))
            cols["n_roe"].append(n_roe)
            cols["q_roe"].append(q_roe)
            cols["n_tracks"].append(n_trk)
            cols["n_photons"].append(n_pho)
            cols["mode_id"].append(mode_id)
            cols["event"].append(ievt)

    arrays = {k: np.array(v, dtype=np.int32
                          if k in ("n_roe", "q_roe", "n_tracks", "n_photons",
                                   "mode_id", "event")
                          else np.float64) for k, v in cols.items()}
    with uproot.recreate(out_path) as f:
        f["events"] = arrays

    print(f"{in_path}: {n_events} events, {n_cand} signal decays, "
          f"{n_rec} fully reconstructed (eff = {n_rec / max(n_cand, 1):.1%}) "
          f"-> {out_path} (mode_id={mode_id}, seed={seed})")


if __name__ == "__main__":
    main()
