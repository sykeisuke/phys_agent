#!/usr/bin/env python
"""Produce a flat ROOT ntuple from HepMC events + fast simulation (v2).

v2 makes the reconstruction realistic enough to include continuum
background: nothing is taken from the true B four-momentum any more.

Candidate = a true D*+- whose stable charged descendants are exactly 3
tracks (K pi from the D0, slow pi) + the highest-p* charge-correlated
muon in the event (D*- pairs with mu+ and vice versa). All discriminating
variables are computed in the e+e- CM frame with the BEAM CONSTRAINT
p_B = (sqrt(s)/2, 0) — the B energy is known at the Upsilon(4S), its small
momentum (~0.34 GeV) is neglected:

    m2miss  = (p_B - p_D*(rec) - p_lep(rec))^2
    q2      = (p_B - p_D*(rec))^2
    plep_star = |p_lep| in the CM frame
    cos_by  = cos of the angle between the B and the D*-lep system
              (physical range [-1, 1] for signal-like decays)
    r2      = Fox-Wolfram H2/H0 over all stable visible particles
              (continuum suppression; truth momenta, no smearing)

Truth-based variables (m2miss_true, ...) use the true parent-B momentum
and are NaN for candidates without a B ancestor (continuum).
true_mode: 1 = B -> D* tau nu, 2 = B -> D* mu nu, 0 = other B decay,
3 = no B ancestor (continuum).

usage: python fastsim/make_ntuple.py <in.hepmc> <out.root> <mode_id> [seed]
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
NEUTRINOS = {12, 14, 16}

M_B = 5.2795
P_EE = np.array([np.hypot(10.5794, 3.0), 0.0, 0.0, 3.0])  # e+e- four-momentum
SQRT_S = 10.5794
E_B_CM = SQRT_S / 2.0
P_B_CM = np.array([E_B_CM, 0.0, 0.0, 0.0])                # beam-constrained B
P_B_MAG = np.sqrt(E_B_CM ** 2 - M_B ** 2)


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


def to_cm(p):
    return boost_to_rest(p, P_EE)


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
    v = part.production_vertex
    while v and v.particles_in:
        mom = v.particles_in[0]
        if mom.pid in B_PIDS:
            return mom
        v = mom.production_vertex
    return None


def classify_b(B):
    """1 = D* tau nu, 2 = D* mu nu, 0 = other."""
    pids = [abs(d.pid) for d in B.end_vertex.particles_out]
    if 413 in pids and 15 in pids:
        return 1
    if 413 in pids and 13 in pids:
        return 2
    return 0


def count_b_decays(event, counts):
    for part in event.particles:
        if abs(part.pid) != 511 or not part.end_vertex:
            continue
        dau = part.end_vertex.particles_out
        if len(dau) == 1 and abs(dau[0].pid) == 511:
            continue  # mixing transition
        counts["n_b0"] += 1
        counts[{1: "n_dsttaunu", 2: "n_dstmunu", 0: "n_other"}[classify_b(part)]] += 1


def fox_wolfram_r2(event):
    """H2/H0 over stable visible particles (truth momenta, CM frame)."""
    ps = [to_cm(four_vec(p))[1:] for p in event.particles
          if not p.end_vertex and abs(p.pid) not in NEUTRINOS]
    mags = np.array([np.linalg.norm(p) for p in ps])
    keep = mags > 1e-9
    ps = np.array([p for p, k in zip(ps, keep) if k])
    mags = mags[keep]
    if len(ps) < 2:
        return 1.0
    cos = np.clip((ps @ ps.T) / np.outer(mags, mags), -1.0, 1.0)
    w = np.outer(mags, mags)
    h0 = w.sum()
    h2 = (w * 0.5 * (3.0 * cos ** 2 - 1.0)).sum()
    return h2 / h0


def find_candidate(event):
    """First D* + charge-correlated muon pair in the event, or None.
    Returns (dst, d0_tracks, slow_pi, mu, B_or_None)."""
    for part in event.particles:
        if part.pid not in DST_PIDS or not part.end_vertex:
            continue
        tracks = stable_descendants(part, CHARGED_STABLE)
        if len(tracks) != 3:
            continue
        d0 = next((d for d in part.end_vertex.particles_out
                   if abs(d.pid) == 421), None)
        if d0 is None:
            continue
        d0_tracks = stable_descendants(d0, CHARGED_STABLE)
        d0_ids = {t.id for t in d0_tracks}
        slow = [t for t in tracks if t.id not in d0_ids]
        if len(d0_tracks) != 2 or len(slow) != 1:
            continue
        dst_ids = {t.id for t in tracks}
        # charge correlation: D*- (pid<0) pairs with mu+ (pid<0), and c.c.
        mus = [m for m in event.particles
               if m.pid in MU_PIDS and not m.end_vertex
               and m.id not in dst_ids and m.pid * part.pid > 0]
        if not mus:
            continue
        mu = max(mus, key=lambda m: np.linalg.norm(to_cm(four_vec(m))[1:]))
        return part, d0_tracks, slow[0], mu, b_ancestor(part)
    return None


def main():
    in_path, out_path, mode_id = sys.argv[1], sys.argv[2], int(sys.argv[3])
    seed = int(sys.argv[4]) if len(sys.argv) > 4 else 42
    cfg = DetectorConfig()
    rng = np.random.default_rng(seed)

    cols = {k: [] for k in [
        "m2miss", "plep_star", "q2", "m_d0", "delta_m", "cos_by", "r2",
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
            dst, d0_tracks, slow_pi, mu, B = cand

            pLep_true = four_vec(mu)
            sm_d0 = [detect_track(four_vec(t), cfg, rng) for t in d0_tracks]
            sm_slow = detect_track(four_vec(slow_pi), cfg, rng)
            sm_mu = detect_track(pLep_true, cfg, rng)
            if any(s is None for s in sm_d0) or sm_slow is None or sm_mu is None:
                continue
            n_rec += 1

            pD0 = np.sum(sm_d0, axis=0)
            pDst = pD0 + sm_slow
            # CM frame, beam-constrained B
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
            cols["r2"].append(fox_wolfram_r2(event))
            plep3 = sm_mu[1:]
            cols["p_lep_lab"].append(np.linalg.norm(plep3))
            cols["costh_lep_lab"].append(plep3[2] / np.linalg.norm(plep3))
            cols["p_dst_lab"].append(np.linalg.norm(pDst[1:]))
            # truth reference (only for candidates from a true B decay)
            if B is not None:
                pB = four_vec(B)
                pDst_true = four_vec(slow_pi) + sum(four_vec(t) for t in d0_tracks)
                cols["m2miss_true"].append(minv2(pB - pDst_true - pLep_true))
                cols["plep_star_true"].append(
                    np.linalg.norm(boost_to_rest(pLep_true, pB)[1:]))
                cols["q2_true"].append(minv2(pB - pDst_true))
                cols["true_mode"].append(classify_b(B))
            else:
                cols["m2miss_true"].append(np.nan)
                cols["plep_star_true"].append(np.nan)
                cols["q2_true"].append(np.nan)
                cols["true_mode"].append(3)
            cols["mode_id"].append(mode_id)
            cols["event"].append(ievt)

    arrays = {k: np.array(v, dtype=np.int32 if k in ("true_mode", "mode_id", "event")
                          else np.float64) for k, v in cols.items()}
    with uproot.recreate(out_path) as f:
        f["events"] = arrays

    print(f"{in_path}: {n_events} events, {n_cand} truth candidates, "
          f"{n_rec} reconstructed (eff = {n_rec / max(n_events, 1):.1%}) "
          f"-> {out_path} (mode_id={mode_id}, seed={seed})")
    tc = truth_counts
    print(f"truth B0 decays: {tc['n_b0']}  "
          f"D*taunu: {tc['n_dsttaunu']}  D*munu: {tc['n_dstmunu']}  "
          f"other: {tc['n_other']}")


if __name__ == "__main__":
    main()
