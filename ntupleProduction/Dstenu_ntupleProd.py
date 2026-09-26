import basf2 as b2
import vertex 
from modularAnalysis import ma
import variables.collections as vc 
from variables import variables as vm
import variables.util as vu 
from variables.MCGenTopo import mc_gen_topo
import sys 
import argparse 
# Check the skim output
from skim.WGs. import fei, semileptonic

if len(sys.argv) != 2:
    sys.exit("Usage: Dstellnu_ntupleProd.py <e/mu>")

mode = sys.argv
if mode not in ["e", "mu"]:
    sys.exit("Expecting either e or mu. Try again")

"""
Let's try to write this python file in a format 
that can be used by agents or batch systems. 

So components of the code should be modular to assist with this. 
"""

# run 1
b2.conditions.prepend_globaltag(ma.getAnalysisGlobaltag()) #needed for FEI 
b2.conditions.prepend_globaltag("release-08-00-09")


# dummy name for input, can overwrite in basf2 using -i option on command line
rootInputName = "basf2_dsttaunu_genlevel.root"

# dummy name for output, can overwrite in basf2 using -o option on command line
rootOutputName = f"basf2_dst{mode}nu_ntuple.root"

# create path
path = b2.create_path()

# read in input
inputPath = "../generation"
ma.inputMdstList(filelist = [f"{inputPath}/{rootInputName}"], path = path)

# start with final state particles 
# TODO: we need to have some minor cuts for purity
# TODO: Look at b2help-recommendation (https://belle2.pages.desy.de/performance/recommendations/)

# for when we want to see how our selection does w/ existing skims
skim_list = {
    "feiSL": fei.feiSL(udstOutput = False), 
    "feiHadronicB0": fei.feiHadronicB0(udstOutput = False), 
    "feiSLB0_RDstar": fei.feiSLB0_RDstar(udstOutput = False),
    "feiSLB0": fei.feiSLB0(udstOutput = False),
    "feiHadronic_DstEllNu": fei.feiHadronic_DstEllNu,
    "SLUntagged": semileptonic.SLUntagged(udstOutput = False), 
}
for key, value in skim_list.items():
    value(path=path)
    vm.add_alias(f"skim_{key}", value.flag)



skim_feiSL = fei.feiSLB0_RDstar(udstOutput = False)
skim_feiSL(path=path)
vm.addAlias("skim_feiSL", f"{skim_feiSL.flag}")

# b2help track recommendations 
list_track_cuts = [
    "thetaInCDCAcceptance",
    "dr < 1",
    "abs(dz) < 3"
]
track_cuts = " and ".join(list_track_cuts)
photon_cuts = "abs(clusterTiming)<200 and thetaInCDCAcceptance"

# ROE mask for continuum suppression -- b2help
track_selection = " and ".join([
    "[dr < 2]",
    "[abs(dz) < 4]",
    "[pt > 0.2]",
    "[thetaInCDCAcceptance==1]"
])
ecl_selection = "'[[[clusterReg==1] and [E>0.080]] or [[clusterReg==2] and [E > 0.03]] or [[clusterReg==3] and [E > 0.06]]] "
ecl_selection += "and [clusterNHits > 1.5] and [0.2967 < clusterTheta < 2.6180] and [abs(clusterTiming) < 200]"
roe_mask = (track_selection, ecl_selection)

slow_pion_cut = "dr < 2 and abs(dz) < 4 and thetaInCDCAcceptance"

# so I am reconstructing B0 -> D* e nu 
# maybe easier to keep e and µ channels separate
# where D* -> D0bar (-> K pi) pi
# start with final state particles and build up from there

# signal side final state particles
ma.fillParticleList("e+:sig", f"{track_cuts}", path=path)
ma.fillParticleList("mu+:sig", f"{track_cuts}", path=path)
ma.fillParticleList("K+:D0", f"{track_cuts}", path=path)
ma.fillParticleList("pi+:D0", f"{track_cuts}", path=path) 
ma.fillParticleList("pi+:Dstr", f"{slow_pion_cut}", path=path) # slow pion
#TODO: do slow pion efficiency corrections at some point

# Do I need to do photon corrections or is this built in? 

# reconstruct signal neutral B
ma.reconstructDecay("anti-D0:Dst -> K+:D0 pi-:D0", "", path=path)
ma.reconstructDecay("D*-:sig -> anti-D0:Dst pi-:Dst", "", path=path)
if mode == "e":
    ma.reconstructDecay(
        "B0:sig -> D*-:sig e+:sig ?nu", "", path=path)  
if mode == "mu":
    ma.reconstructDecay(
        "B0:sig -> D*-:sig mu+:sig ?nu", "", path=path)  

# so we have truth information
ma.matchMCTruth(list_name = "B0:sig", path = path)


# reconstruct rest of event (tag side)
ma.buildRestOfEvent('B0:sig', path=path)
ma.appendROEMask('B0:generic', 'roe_mask', *roe_mask, path=path)
ma.buildContinuumSuppression('B+:feiHadronic', 'fei_mask', path=path)
# Required selections on tag candidates
ma.applyCuts('B+:feiHadronic', 'Mbc > 5.27 and -0.15 < deltaE < 0.1 and cosTBTO(fei_mask) < 0.9', path=path)
# Best candidate selection
ma.rankByHighest('B+:feiHadronic', 'extraInfo(SignalProbability)', outputVariable='sigProb_rank', path=path)
ma.cutAndCopyList('B+:BestCandidate', 'B+:feiHadronic', 'sigProb_rank == 1', path=path)


# reconstruct upsilon(4S)
ma.reconstructDecay(  # [S70]
    "Upsilon(4S):opposite_cp -> B0:feiHadronic anti-B0:signal", cut="", path=path
)
ma.reconstructDecay(
    decayString="Upsilon(4S):same_cp -> B0:feiHadronic B0:signal",
    cut="",
    path=path,
)
# Combine the two Upsilon(4S) lists to one. Note: Duplicates are removed.
ma.copyLists(
    outputListName="Upsilon(4S)",
    inputListNames=["Upsilon(4S):opposite_cp", "Upsilon(4S):same_cp"],
    path=path,
)  # [E70]

# use collections to save variables
# variations on variables
cms_kinematics = vu.create_aliases(vc.kinematics, "useCMSFrame({variable})", "CMS")
pidvars = [f"{p}NN" for p in vc.pid[0:6]] + vc.pid
skim_vars = [f"skim_{key}" for key in skim_list]

# collecting variables
fsp_vars = vc.mc_variables + vc.kinematics + pidvars + vc.track + vc.track_hists + ["isSignal"]
d_vars = vc.mc_truth + vc.kinematics + vc.inv_mass
b_vars = vc.mc_truth + \
    vc.deltae_mbc + \
    vu.create_aliases_for_selected(
        fsp_vars, 
        f"B0 -> [Dstr- -> [antiD0 -> ^K+ ^pi-] ^pi- ] ^{mode}+",
        prefix = ["K_D0", "pi_D0", "pi_Dstr", f"{mode}_B0"]) +\
    vu.create_aliases_for_selected(list_of_variables=d_vars,
                                   decay_string=f'B0 -> [^Dstr- -> ^antiD0 pi+] {mode}+') + \
    vu.create_aliases(list_of_variables=['decayModeID'],
                      wrapper='daughter(0,extraInfo({variable}))',
                      prefix="D")



# TODO: fox-wolfram moments 
global_vars = vc.event_kinematics, vc.event_level_tracking, vc.event_shape

# beginning of collecting everything into one variable
varlist = global_vars

# for final state particles
varlist += 

# sanity check here: 
vm.printAliases()

# TODO: VariablesToNtuple