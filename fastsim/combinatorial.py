"""Combinatorial B0 -> K+- pi-+ l+ l- candidate builder (shared core).

Unlike make_ntuple_exclusive.py (truth-seeded: only the forced signal B is
reconstructed), this builds EVERY K pi l+ l- combination in the event, so
it models the combinatorial background from generic BBbar and continuum
that the exclusive producers cannot.

Per event:
  1. every stable charged track and photon is smeared once (fast sim);
  2. lepton ID is applied to every track (true leptons with the ID
     efficiencies, pions/kaons with the fake rates);
  3. same-flavor, opposite-charge lepton pairs are combined with K pi
     pairs (kaon/pion species from truth: hadron mis-ID between K and pi
     is not modeled) inside loose windows:
         |m(K pi) - 0.896| < 0.25 GeV, Mbc > 5.20 GeV, |Delta E| < 0.40 GeV;
  4. each surviving candidate is one ntuple row with the same branch
     schema as make_ntuple_exclusive.py, plus:
         ll_true_src  1 if both leptons come from the same true J/psi or
                      psi(2S), else 0 (coarse truth flag for composition
                      tables; fake-lepton candidates are always 0).

The caller supplies the event as a list of final-state entries
(pid, p4 [E,px,py,pz] lab frame, charm_id) where charm_id identifies the
nearest J/psi / psi(2S) ancestor (None if there is none), so the same core
serves both the HepMC (EvtGen) and the Pythia (continuum) drivers.
"""
import numpy as np

from smear import (DetectorConfig, detect_photon, detect_track,
                   reco_lepton_flavor, with_lepton_mass)
from make_ntuple import (CHARGED_STABLE, E_B_CM, P_B_CM, charge_of, minv,
                         minv2, to_cm)

NEUTRINOS = {12, 14, 16}
M_KST, KST_WINDOW = 0.896, 0.25
MBC_MIN, DE_ABS_MAX = 5.20, 0.40
MAX_CANDIDATES_PER_EVENT = 20

COLUMNS = ["m2miss", "plep_star", "q2", "m_visible", "mbc", "delta_e",
           "m_ll", "r2", "e_tag_cm", "m_tag", "n_roe", "q_roe",
           "n_tracks", "n_photons", "n_mu", "lep_flavor", "ll_true_src",
           "mode_id", "event"]
INT_COLUMNS = {"n_roe", "q_roe", "n_tracks", "n_photons", "n_mu",
               "lep_flavor", "ll_true_src", "mode_id", "event"}


def new_columns():
    return {k: [] for k in COLUMNS}


def fox_wolfram_r2(finals):
    ps = [to_cm(p4)[1:] for pid, p4, _ in finals
          if abs(pid) not in NEUTRINOS]
    mags = np.array([np.linalg.norm(p) for p in ps])
    keep = mags > 1e-9
    ps = np.array([p for p, k in zip(ps, keep) if k])
    mags = mags[keep]
    if len(ps) < 2:
        return 1.0
    cos = np.clip((ps @ ps.T) / np.outer(mags, mags), -1.0, 1.0)
    w = np.outer(mags, mags)
    return (w * 0.5 * (3.0 * cos ** 2 - 1.0)).sum() / w.sum()


def build_candidates(finals, cfg: DetectorConfig, rng: np.random.Generator,
                     mode_id: int, ievt: int, cols: dict) -> int:
    """Append every K pi l+ l- candidate of one event to cols.

    finals: list of (pid, p4, charm_id) for the event's final-state
    particles (lab frame). Returns the number of candidates written.
    """
    # smear every visible final-state particle exactly once
    tracks, photons = [], []
    for pid, p4, charm in finals:
        apid = abs(pid)
        if apid in NEUTRINOS:
            continue
        if pid == 22:
            s = detect_photon(p4, cfg, rng)
            if s is not None:
                photons.append(s)
        elif apid in CHARGED_STABLE:
            s = detect_track(p4, cfg, rng)
            if s is not None:
                tracks.append({"pid": pid, "p4": s,
                               "q": charge_of(pid), "charm": charm,
                               "flavor": reco_lepton_flavor(pid, cfg, rng)})
    leps = [t for t in tracks if t["flavor"] in (11, 13)]
    kaons = [t for t in tracks if abs(t["pid"]) == 321 and t["flavor"] == 0]
    pions = [t for t in tracks if abs(t["pid"]) == 211 and t["flavor"] == 0]
    if len(leps) < 2 or not kaons or not pions:
        return 0

    r2 = fox_wolfram_r2(finals)
    n_written = 0
    for i, la in enumerate(leps):
        for lb in leps[i + 1:]:
            if la["flavor"] != lb["flavor"] or la["q"] * lb["q"] >= 0:
                continue
            pa = with_lepton_mass(la["p4"], la["flavor"])
            pb = with_lepton_mass(lb["p4"], lb["flavor"])
            m_ll = minv(pa + pb)
            src = int(la["charm"] is not None
                      and la["charm"] == lb["charm"])
            for k in kaons:
                for pi in pions:
                    if k["q"] * pi["q"] >= 0 or k is la or k is lb \
                            or pi is la or pi is lb:
                        continue
                    pHad = k["p4"] + pi["p4"]
                    m_vis = minv(pHad)
                    if abs(m_vis - M_KST) > KST_WINDOW:
                        continue
                    pY = to_cm(pHad + pa + pb)
                    mbc2 = E_B_CM ** 2 - float(pY[1:] @ pY[1:])
                    if mbc2 <= MBC_MIN ** 2:
                        continue
                    delta_e = pY[0] - E_B_CM
                    if abs(delta_e) > DE_ABS_MAX:
                        continue
                    pHad_cm = to_cm(pHad)
                    used = {id(k["p4"]), id(pi["p4"]),
                            id(la["p4"]), id(lb["p4"])}
                    p_tag = np.zeros(4)
                    n_roe = q_roe = 0
                    for t in tracks:
                        if id(t["p4"]) not in used:
                            p_tag += t["p4"]
                            n_roe += 1
                            q_roe += t["q"]
                    for s in photons:
                        p_tag += s
                        n_roe += 1
                    cols["m2miss"].append(minv2(P_B_CM - pY))
                    cols["plep_star"].append(
                        max(np.linalg.norm(to_cm(pa)[1:]),
                            np.linalg.norm(to_cm(pb)[1:])))
                    cols["q2"].append(minv2(P_B_CM - pHad_cm))
                    cols["m_visible"].append(m_vis)
                    cols["mbc"].append(np.sqrt(mbc2))
                    cols["delta_e"].append(delta_e)
                    cols["m_ll"].append(m_ll)
                    cols["r2"].append(r2)
                    cols["e_tag_cm"].append(to_cm(p_tag)[0])
                    cols["m_tag"].append(minv(p_tag))
                    cols["n_roe"].append(n_roe)
                    cols["q_roe"].append(q_roe)
                    cols["n_tracks"].append(2)
                    cols["n_photons"].append(0)
                    cols["n_mu"].append(2)
                    cols["lep_flavor"].append(la["flavor"])
                    cols["ll_true_src"].append(src)
                    cols["mode_id"].append(mode_id)
                    cols["event"].append(ievt)
                    n_written += 1
                    if n_written >= MAX_CANDIDATES_PER_EVENT:
                        return n_written
    return n_written


def write_root(out_path, cols):
    import uproot
    arrays = {k: np.array(v, dtype=np.int32 if k in INT_COLUMNS
                          else np.float64) for k, v in cols.items()}
    with uproot.recreate(out_path) as f:
        f["events"] = arrays
