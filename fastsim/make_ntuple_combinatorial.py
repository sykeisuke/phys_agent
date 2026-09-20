#!/usr/bin/env python
"""Combinatorial K pi l+ l- ntuple from an EvtGen HepMC file (generic
BBbar): every K pi l+ l- combination inside loose windows becomes one row.
See fastsim/combinatorial.py for the candidate definition and branches.

usage: python fastsim/make_ntuple_combinatorial.py <in.hepmc> <out.root> <mode_id> [seed]
"""
import sys
from pathlib import Path

import numpy as np
import pyhepmc

sys.path.insert(0, str(Path(__file__).resolve().parent))
from smear import DetectorConfig
from make_ntuple import four_vec
from combinatorial import build_candidates, new_columns, write_root

CHARMONIUM = {443, 100443}


def charm_ancestor(part, depth=0):
    """The id() of the nearest J/psi / psi(2S) ancestor, or None."""
    if depth > 12 or not part.production_vertex:
        return None
    for m in part.production_vertex.particles_in:
        if abs(m.pid) in CHARMONIUM:
            return m.id
        up = charm_ancestor(m, depth + 1)
        if up is not None:
            return up
    return None


def main():
    in_path, out_path, mode_id = sys.argv[1], sys.argv[2], int(sys.argv[3])
    seed = int(sys.argv[4]) if len(sys.argv) > 4 else 42
    cfg = DetectorConfig()
    rng = np.random.default_rng(seed)

    cols = new_columns()
    n_events = n_cand = 0
    with pyhepmc.open(in_path) as f:
        for ievt, event in enumerate(f):
            n_events += 1
            finals = []
            for p in event.particles:
                if p.end_vertex:
                    continue
                apid = abs(p.pid)
                charm = charm_ancestor(p) if apid in (11, 13) else None
                finals.append((p.pid, four_vec(p), charm))
            n_cand += build_candidates(finals, cfg, rng, mode_id, ievt, cols)

    write_root(out_path, cols)
    print(f"{in_path}: {n_events} events -> {n_cand} combinatorial "
          f"candidates -> {out_path} (mode_id={mode_id}, seed={seed})")


if __name__ == "__main__":
    main()
