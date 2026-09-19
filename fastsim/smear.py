"""Simple detector smearing for charged tracks (Phase 2 fast sim).

Detector model (Belle II-like, deliberately simple for teaching):

- momentum resolution : sigma_p / p = 0.5 % (Gaussian smearing of |p|,
  direction unchanged, energy recomputed from the true mass)
- acceptance          : 17 deg < theta_lab < 150 deg (CDC-like polar angle)
- tracking efficiency : 95 % per charged track, flat in p and theta

All units are GeV (natural units). Four-vectors are numpy arrays
[E, px, py, pz], same convention as analysis/plot_m2miss.py.
"""
from dataclasses import dataclass

import numpy as np


@dataclass
class DetectorConfig:
    sigma_p_over_p: float = 0.005          # relative momentum resolution
    theta_min: float = np.radians(17.0)    # polar-angle acceptance (lab)
    theta_max: float = np.radians(150.0)
    track_eff: float = 0.95                # per-track detection efficiency
    # photons (ECL-like, used for the rest-of-event reconstruction)
    photon_e_min: float = 0.05             # energy threshold [GeV]
    photon_res_a: float = 0.02             # sigma_E/E = a/sqrt(E) (+) b
    photon_res_b: float = 0.01
    # lepton identification (v1: constant rates, no p/theta dependence yet)
    mu_id_eff: float = 0.90                # true mu identified as mu
    pi_fake_mu: float = 0.02               # pi misidentified as mu
    k_fake_mu: float = 0.01                # K misidentified as mu
    e_id_eff: float = 0.95                 # true e identified as e (ECL, stronger at Belle II)
    pi_fake_e: float = 0.005               # pi misidentified as e
    k_fake_e: float = 0.005                # K misidentified as e


def theta_lab(p4):
    """Polar angle of a four-vector [E, px, py, pz] in the lab frame."""
    pmag = np.linalg.norm(p4[1:])
    if pmag == 0.0:
        return 0.0
    return np.arccos(np.clip(p4[3] / pmag, -1.0, 1.0))


def in_acceptance(p4, cfg: DetectorConfig):
    return cfg.theta_min < theta_lab(p4) < cfg.theta_max


def smear_track(p4, cfg: DetectorConfig, rng: np.random.Generator):
    """Smear |p| by a Gaussian of width sigma_p/p, keep the direction,
    and recompute the energy from the true invariant mass."""
    pvec = p4[1:]
    m2 = max(p4[0] ** 2 - pvec @ pvec, 0.0)
    scale = 1.0 + cfg.sigma_p_over_p * rng.standard_normal()
    pvec = scale * pvec
    e = np.sqrt(m2 + pvec @ pvec)
    return np.array([e, *pvec])


def detect_track(p4, cfg: DetectorConfig, rng: np.random.Generator):
    """Full per-track response: acceptance cut + efficiency roll + smearing.

    Returns the smeared four-vector, or None if the track is lost.
    """
    if not in_acceptance(p4, cfg):
        return None
    if rng.random() > cfg.track_eff:
        return None
    return smear_track(p4, cfg, rng)


MU_MASS = 0.1056584
E_MASS = 0.000511
LEPTON_MASS = {13: MU_MASS, 11: E_MASS}


def reco_lepton_flavor(pid, cfg: DetectorConfig, rng: np.random.Generator):
    """Lepton-ID decision for a detected track. Returns the reconstructed
    flavor: 13 (muon), 11 (electron) or 0 (not identified as a lepton).
    True leptons pass with mu_id_eff / e_id_eff; pions and kaons fake with
    the configured rates (exclusive: mu roll first, then e). v1: constant
    rates, no bremsstrahlung modeling for electrons."""
    apid = abs(pid)
    if apid == 13:
        return 13 if rng.random() < cfg.mu_id_eff else 0
    if apid == 11:
        return 11 if rng.random() < cfg.e_id_eff else 0
    if apid in (211, 321):
        fmu = cfg.pi_fake_mu if apid == 211 else cfg.k_fake_mu
        fe = cfg.pi_fake_e if apid == 211 else cfg.k_fake_e
        r = rng.random()
        if r < fmu:
            return 13
        if r < fmu + fe:
            return 11
    return 0


def identified_as_muon(pid, cfg: DetectorConfig, rng: np.random.Generator):
    """Backward-compatible muon-only ID decision."""
    return reco_lepton_flavor(pid, cfg, rng) == 13


def with_lepton_mass(p4, flavor):
    """Re-assign the lepton mass hypothesis: keep the momentum, recompute E.
    This is what makes misidentified hadrons peak in shifted positions."""
    vec = p4[1:]
    return np.array([np.sqrt(LEPTON_MASS[flavor] ** 2 + vec @ vec), *vec])


def with_muon_mass(p4):
    """Backward-compatible muon mass hypothesis."""
    return with_lepton_mass(p4, 13)


def detect_photon(p4, cfg: DetectorConfig, rng: np.random.Generator):
    """ECL-like photon response: acceptance + energy threshold + Gaussian
    energy smearing sigma_E/E = a/sqrt(E) (+) b, direction unchanged.

    Returns the smeared (massless) four-vector, or None if undetected.
    """
    e = p4[0]
    if e < cfg.photon_e_min or not in_acceptance(p4, cfg):
        return None
    sigma = e * np.hypot(cfg.photon_res_a / np.sqrt(e), cfg.photon_res_b)
    e_new = max(e + sigma * rng.standard_normal(), 1e-6)
    return (e_new / e) * p4
