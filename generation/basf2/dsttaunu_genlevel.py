#!/usr/bin/env python3
"""basf2 steering file: generator-level B0 -> D* tau nu ntuple.

TEMPLATE — UNTESTED in this repository (requires a basf2 environment,
e.g. cvmfs at KEK: `source /cvmfs/belle.cern.ch/tools/b2setup <release>`).
Mirrors the fast-sim worked example so the two ntuples can be compared
variable by variable (see docs/basf2.md for the mapping).

usage: basf2 generation/basf2/dsttaunu_genlevel.py
"""
import basf2 as b2
import generators as ge
import modularAnalysis as ma
from variables import variables as vm

N_EVENTS = 5000
DEC_FILE = "generation/dec/B0_Dsttaunu.dec"  # same forced chain as fastsim
OUT_FILE = "data/basf2_dsttaunu_genlevel.root"

main = b2.Path()
main.add_module("EventInfoSetter", evtNumList=[N_EVENTS])

# EvtGen with our user decay file (tau -> mu nu nu forced in the dec file)
ge.add_evtgen_generator(main, finalstate="signal", signaldecfile=DEC_FILE)

# MC-truth "reconstruction" of the forced chain (no detector simulation)
ma.fillParticleListFromMC("mu+:gen", "", path=main)
ma.fillParticleListFromMC("K+:gen", "", path=main)
ma.fillParticleListFromMC("pi+:gen", "", path=main)
ma.reconstructMCDecay("anti-D0:gen -> K+:gen pi-:gen", "", path=main)
ma.reconstructMCDecay("D*-:gen -> anti-D0:gen pi-:gen", "", path=main)
ma.reconstructMCDecay(
    "B0:sig -> D*-:gen tau+ nu_tau", "", path=main)  # TODO: verify tau handling
# The Y = D* + mu system used for the recoil variables:
ma.reconstructDecay("Upsilon(4S):Y -> D*-:gen mu+:gen", "", path=main,
                    allowChargeViolation=True)

# event shape for foxWolframR2
ma.fillParticleList("pi+:all", "", path=main)
ma.fillParticleList("gamma:all", "", path=main)
ma.buildEventShape(inputListNames=["pi+:all", "gamma:all"], path=main)

vm.addAlias("m2miss", "m2Recoil")
vm.addAlias("plep_star", "daughter(1, useCMSFrame(p))")
vm.addAlias("m_d0", "daughter(0, daughter(0, M))")
vm.addAlias("delta_m", "daughter(0, massDifference(0))")
vm.addAlias("cos_by", "cosThetaBetweenParticleAndNominalB")
vm.addAlias("r2", "foxWolframR2")

ma.variablesToNtuple(
    "Upsilon(4S):Y",
    ["m2miss", "plep_star", "m_d0", "delta_m", "cos_by", "r2"],
    filename=OUT_FILE, treename="events", path=main)

b2.process(main)
print(b2.statistics)
