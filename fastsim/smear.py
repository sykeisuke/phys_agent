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
