#!/usr/bin/env python
"""Continuum e+e- -> qq (u,d,s,c) background for the exclusive K* l+ l-
analyses: Pythia8 -> combinatorial K pi l+ l- candidates in one pass (no
HepMC intermediate). Candidate definition and branches are those of
fastsim/combinatorial.py; ll_true_src flags lepton pairs from a true
J/psi / psi(2S) (rare in continuum).

For luminosity weighting the printout reports N_generated and sigma:

    weight = (sigma_cont * L) / N_cont_generated

usage: python generation/generate_continuum_exclusive.py <nEvents> <out.root> <seed>
"""
import sys
from pathlib import Path

import numpy as np
import pythia8

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "fastsim"))
from smear import DetectorConfig
from combinatorial import build_candidates, new_columns, write_root

CHARMONIUM = {443, 100443}


def charm_ancestor(ev, j, depth=0):
    """Index of the nearest J/psi / psi(2S) mother in the record, or None."""
    if depth > 12:
        return None
    for m in ev[j].motherList():
        if m <= 0:
            continue
        if abs(ev[m].id()) in CHARMONIUM:
            return m
        up = charm_ancestor(ev, m, depth + 1)
        if up is not None:
            return up
    return None


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

    cols = new_columns()
    n_cand = 0
    for ievt in range(n_events):
        if not py.next():
            continue
        if (ievt + 1) % 500000 == 0:
            print(f"generated {ievt + 1} / {n_events} "
                  f"({n_cand} candidates)", flush=True)
        ev = py.event
        finals = []
        for j in range(1, ev.size()):
            p = ev[j]
            if not p.isFinal():
                continue
            apid = abs(p.id())
            charm = charm_ancestor(ev, j) if apid in (11, 13) else None
            finals.append((p.id(),
                           np.array([p.e(), p.px(), p.py(), p.pz()]), charm))
        n_cand += build_candidates(finals, cfg, rng, 98, ievt, cols)

    write_root(out_path, cols)
    sigma_nb = py.infoPython().sigmaGen() * 1e6
    print(f"{n_events} continuum events (seed {seed}): {n_cand} combinatorial "
          f"candidates -> {out_path}")
    print(f"sigma = {sigma_nb:.3f} nb  "
          f"(weight at L [nb^-1]: sigma * L / {n_events})")


if __name__ == "__main__":
    main()
