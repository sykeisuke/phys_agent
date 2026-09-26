#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Descriptor: mixed b loevel

#############################################################
# Steering file based on offical MC production
# B0_DstTaunu
#
# Belle II Collaboration
#############################################################


import basf2 as b2
import generators as ge
import simulation as si
import reconstruction as re
import mdst as mdst
import glob as glob
import sys

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Steering file for Belle II MC production (generation -> simulation ->
reconstruction -> mDST), based on the official MC production setup.
Still MC16ri-like.

Usage:
    basf2 generic_template.py <mode> [-n N_EVENTS] [--home PATH] [--no-bkg]

Examples:
    basf2 generic_template.py B0_Dsttaunu
    basf2 generic_template.py generic_mixed -n 10000
"""

import argparse
import glob
import sys
from pathlib import Path

import basf2 as b2
import generators as ge
import mdst
import reconstruction as re
import simulation as si

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Each mode maps to the EvtGen "finalstate":
#   "signal"  -> use the user decay file generation/dec/<mode>.dec

SIG_MODES = [
    "D_Ds1Kmunu",
    "B_DsK1munu",
    "D_dsstKstmunu",
    "B0_Dstlnu",
    "B0_Dsttaunu",
    "B0_JpsiKst",
    "B0_Kstl",
    "generic_bbbar",
    "tau_native"
]
# generic modes
GEN_MODES = [
    "mixed",
    "charged"
]

DEC_MODES = SIG_MODES + GEN_MODES


DEFAULT_N_EVENTS = 5000
DEFAULT_HOME = "../.."            # project root; override with --home

# Experiment/run numbers: early phase 3 (exp 1003), run 0
EXP_NUMBER = 1003
RUN_NUMBER = 0

# Global tag prepended to the default conditions
GLOBAL_TAG = "release-08-00-09"

# Beam-background overlay files (only available on KEKCC)
BKG_GLOB = ("/group/belle2/dataprod/BGOverlay/early_phase3/"
            "release-08-00-03/overlay/BGx1/set?/*root")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_args():
    """Parse command-line arguments passed to the steering file."""
    parser = argparse.ArgumentParser(
        description="Belle II MC production: gen -> sim -> reco -> mDST")
    parser.add_argument("mode", choices=sorted(DEC_MODES),
                        help="decay mode / sample to produce")
    parser.add_argument("-n", "--n-events", type=int, default=DEFAULT_N_EVENTS,
                        help=f"number of events (default: {DEFAULT_N_EVENTS})")
    parser.add_argument("--home", default=DEFAULT_HOME,
                        help=f"project root directory (default: {DEFAULT_HOME})")
    parser.add_argument("--no-bkg", action="store_true",
                        help="simulate without beam-background overlay")
    return parser.parse_args()


def resolve_paths(home, mode):
    """Return (decay_file, output_file) paths for the given mode."""
    home = Path(home).resolve()
    dec_file = home / "generation" / "dec" / f"{mode}.dec"
    out_file = home / "data" / f"{mode}_mdst.root"
    return dec_file, out_file


def find_background_files(disabled):
    """Locate background overlay files; warn if none are found."""
    if disabled:
        b2.B2INFO("Background overlay disabled by --no-bkg.")
        return None

    files = glob.glob(BKG_GLOB)
    if not files:
        # Passing None (not []) makes the 'no background' choice explicit
        b2.B2WARNING("No background files found (not on KEKCC?). "
                     "Simulating WITHOUT beam background.")
        return None

    b2.B2INFO(f"Using {len(files)} background overlay files.")
    return files


def build_path(mode, n_events, dec_file, out_file, bkg_files):
    """Assemble the full basf2 processing path."""
    main = b2.create_path()

    # Event metadata: experiment, run, number of events
    main.add_module("EventInfoSetter",
                    expList=[EXP_NUMBER], runList=[RUN_NUMBER],
                    evtNumList=[n_events])

    # Event generation with EvtGen
    if mode not in SIG_MODES:
        # User decay file forces the signal chain (e.g. tau -> mu nu nu)
        ge.add_evtgen_generator(main, finalstate="signal",
                                signaldecfile=str(dec_file))
    elif mode not in GEN_MODES:
        # Generic B Bbar: 'mixed' (neutral) or 'charged'
        ge.add_evtgen_generator(main, finalstate=mode)
    else:
        # 
        b2.B2WARNING("unknown mode... fall back is no constraint")
        ge.add_evtgen_generator(main, finalstate='')


    # Detector simulation (with background overlay if available)
    si.add_simulation(path=main, bkgfiles=bkg_files)

    # Full reconstruction
    re.add_reconstruction(path=main)

    # mDST output (the file name is overwritten when running on the grid)
    mdst.add_mdst_output(path=main, filename=str(out_file))

    return main


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = parse_args()
    dec_file, out_file = resolve_paths(args.home, args.mode)

    # Fail early if a signal mode is missing its decay file
    if args.mode not in DEC_MODES:
        sys.exit("{args.mode} not registered. Fix or add.")
    if args.mode not in ["mixed", "charged"] and not dec_file.is_file():
        sys.exit(f"Decay file not found: {dec_file}")

    # Make sure the output directory exists
    out_file.parent.mkdir(parents=True, exist_ok=True)

    bkg_files = find_background_files(args.no_bkg)

    # Conditions database: prepend our tag to the defaults
    b2.conditions.prepend_globaltag(GLOBAL_TAG)

    b2.B2INFO(f"Mode: {args.mode}, "
              f"events: {args.n_events}, output: {out_file}")

    path = build_path(args.mode, args.n_events, dec_file, out_file, bkg_files)

    # Actually run the processing (missing in the original script)
    b2.process(path)
    print(b2.statistics)


if __name__ == "__main__":
    main()