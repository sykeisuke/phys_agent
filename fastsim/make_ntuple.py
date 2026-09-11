#!/usr/bin/env python
"""Produce a flat ROOT ntuple from HepMC events + fast simulation.

Chain: EvtGen (HepMC3 ascii) -> fastsim smearing -> candidate reconstruction
-> one row per reconstructed candidate, written with uproot (no ROOT C++
installation needed; students read the files back with uproot as well).

Reconstruction:
  * D* candidate  : any D*+- whose stable charged descendants are exactly
                    3 tracks (K, pi, slow pi) inside the fast sim
  * muon candidate: highest-momentum stable muon descending from the same
                    B as the D* (but not from the D* itself); covers the
                    direct mu (D* mu nu, D** mu nu) and the tau daughter
                    (D* tau nu) cases
  * p_B is taken from truth (stand-in for the beam/Btag constraint)

All four tracks must survive acceptance + efficiency + smearing, otherwise
the event is dropped (counted in the efficiency printout).

Branches (rec = smeared unless noted):
  m2miss, plep_star, q2      : discriminating variables
  m_d0, delta_m              : m(K pi), m(K pi pi) - m(K pi)
  p_lep_lab, costh_lep_lab   : lab momentum / polar angle of the lepton
  p_dst_lab                  : lab momentum of the D* candidate
  m2miss_true, plep_star_true, q2_true : truth values
  mode_id                    : sample label given on the command line
  event                      : event index in the input file

usage: python fastsim/make_ntuple.py <in.hepmc> <out.root> <mode_id> [seed]
  e.g. python fastsim/make_ntuple.py data/signal_taunu.hepmc data/signal_taunu.root 0 42
"""
import sys
from pathlib import Path

import numpy as np
import pyhepmc
import uproot

sys.path.insert(0, str(Path(__file__).resolve().parent))
from smear import DetectorConfig, detect_track

B_PIDS = {511, -511}
DST_PIDS = {413, -413}
MU_PIDS = {13, -13}
CHARGED_STABLE = {211, 321, 13, 11, 2212}


def four_vec(p):
    m = p.momentum
    return np.array([m.e, m.px, m.py, m.pz])


def minv2(v):
    return v[0] ** 2 - v[1] ** 2 - v[2] ** 2 - v[3] ** 2


def minv(v):
    return np.sqrt(max(minv2(v), 0.0))


def boost_to_rest(p, frame):
    beta = -frame[1:] / frame[0]
    b2 = beta @ beta
    if b2 < 1e-16:
        return p.copy()
    gamma = 1.0 / np.sqrt(1.0 - b2)
    bp = beta @ p[1:]
    e = gamma * (p[0] + bp)
    vec = p[1:] + ((gamma - 1.0) * bp / b2 + gamma * p[0]) * beta
    return np.array([e, *vec])


def stable_descendants(part, pid_set=None):
    out = []
    if not part.end_vertex:
        if pid_set is None or abs(part.pid) in pid_set:
            out.append(part)
        return out
    for d in part.end_vertex.particles_out:
        out.extend(stable_descendants(d, pid_set))
    return out


def b_ancestor(part):
    """Walk up the decay tree to the first B0/anti-B0."""
    v = part.production_vertex
    while v and v.particles_in:
        mom = v.particles_in[0]
        if mom.pid in B_PIDS:
            return mom
        v = mom.production_vertex
    return None


def classify_b(B):
    """Truth label of a B decay: 1 = D* tau nu, 2 = D* mu nu, 0 = other."""
    pids = [abs(d.pid) for d in B.end_vertex.particles_out]
    if 413 in pids and 15 in pids:
        return 1
    if 413 in pids and 13 in pids:
        return 2
    return 0


def count_b_decays(event, counts):
    """Count true B0 decays (mixing transitions excluded) and the
    B0 -> D* tau nu / D* mu nu fractions among them."""
    for part in event.particles:
        if abs(part.pid) != 511 or not part.end_vertex:
            continue
        dau = part.end_vertex.particles_out
        if len(dau) == 1 and abs(dau[0].pid) == 511:
            continue  # B0 <-> anti-B0 mixing transition, not a decay
        counts["n_b0"] += 1
        counts[{1: "n_dsttaunu", 2: "n_dstmunu", 0: "n_other"}[classify_b(part)]] += 1


def find_candidate(event):
    """Return (pB, dst_tracks, dst_daughters_kpi, mu) for the first
    D* + mu pair sharing a B ancestor, or None."""
    for part in event.particles:
        if part.pid not in DST_PIDS or not part.end_vertex:
            continue
        tracks = stable_descendants(part, CHARGED_STABLE)
        if len(tracks) != 3:
            continue
        B = b_ancestor(part)
        if B is None:
            continue
        dst_ids = {t.id for t in tracks}
        mus = [m for m in stable_descendants(B, {13})
               if m.pid in MU_PIDS and m.id not in dst_ids]
        if not mus:
            continue
        mu = max(mus, key=lambda m: np.linalg.norm(four_vec(m)[1:]))
        d0 = next((d for d in part.end_vertex.particles_out
                   if abs(d.pid) == 421), None)
        if d0 is None:
            continue
        # K and pi from the D0, slow pi directly from the D*
        d0_tracks = stable_descendants(d0, CHARGED_STABLE)
        d0_ids = {t.id for t in d0_tracks}
        slow = [t for t in tracks if t.id not in d0_ids]
        if len(d0_tracks) != 2 or len(slow) != 1:
            continue
        return B, d0_tracks, slow[0], mu
    return None


def main():
    in_path, out_path, mode_id = sys.argv[1], sys.argv[2], int(sys.argv[3])
    seed = int(sys.argv[4]) if len(sys.argv) > 4 else 42
    cfg = DetectorConfig()
    rng = np.random.default_rng(seed)

    cols = {k: [] for k in [
        "m2miss", "plep_star", "q2", "m_d0", "delta_m",
        "p_lep_lab", "costh_lep_lab", "p_dst_lab",
        "m2miss_true", "plep_star_true", "q2_true",
        "true_mode", "mode_id", "event"]}
    n_events = n_cand = n_rec = 0
    truth_counts = {"n_b0": 0, "n_dsttaunu": 0, "n_dstmunu": 0, "n_other": 0}

    with pyhepmc.open(in_path) as f:
        for ievt, event in enumerate(f):
            n_events += 1
            count_b_decays(event, truth_counts)
            cand = find_candidate(event)
            if cand is None:
                continue
            n_cand += 1
            B, d0_tracks, slow_pi, mu = cand

            pB = four_vec(B)
            pDst_true = four_vec(slow_pi) + sum(four_vec(t) for t in d0_tracks)
            pLep_true = four_vec(mu)

            sm_d0 = [detect_track(four_vec(t), cfg, rng) for t in d0_tracks]
            sm_slow = detect_track(four_vec(slow_pi), cfg, rng)
            sm_mu = detect_track(pLep_true, cfg, rng)
            if any(s is None for s in sm_d0) or sm_slow is None or sm_mu is None:
                continue
            n_rec += 1

            pD0 = np.sum(sm_d0, axis=0)
            pDst = pD0 + sm_slow
            cols["m2miss"].append(minv2(pB - pDst - sm_mu))
            cols["plep_star"].append(np.linalg.norm(boost_to_rest(sm_mu, pB)[1:]))
            cols["q2"].append(minv2(pB - pDst))
            cols["m_d0"].append(minv(pD0))
            cols["delta_m"].append(minv(pDst) - minv(pD0))
            plep3 = sm_mu[1:]
            cols["p_lep_lab"].append(np.linalg.norm(plep3))
            cols["costh_lep_lab"].append(plep3[2] / np.linalg.norm(plep3))
            cols["p_dst_lab"].append(np.linalg.norm(pDst[1:]))
            cols["m2miss_true"].append(minv2(pB - pDst_true - pLep_true))
            cols["plep_star_true"].append(
                np.linalg.norm(boost_to_rest(pLep_true, pB)[1:]))
            cols["q2_true"].append(minv2(pB - pDst_true))
            cols["true_mode"].append(classify_b(B))
            cols["mode_id"].append(mode_id)
            cols["event"].append(ievt)

    arrays = {k: np.array(v, dtype=np.int32 if k in ("true_mode", "mode_id", "event")
                          else np.float64) for k, v in cols.items()}
    with uproot.recreate(out_path) as f:
        f["events"] = arrays

    print(f"{in_path}: {n_events} events, {n_cand} truth candidates, "
          f"{n_rec} reconstructed (eff = {n_rec / n_events:.1%}) "
          f"-> {out_path} (mode_id={mode_id}, seed={seed})")
    tc = truth_counts
    print(f"truth B0 decays: {tc['n_b0']}  "
          f"D*taunu: {tc['n_dsttaunu']}  D*munu: {tc['n_dstmunu']}  "
          f"other: {tc['n_other']}")


if __name__ == "__main__":
    main()
