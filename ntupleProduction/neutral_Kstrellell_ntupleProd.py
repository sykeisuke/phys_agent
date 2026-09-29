import basf2 as b2
import vertex 
import modularAnalysis as ma
import variables.collections as vc 
from variables import variables as vm
import variables.utils as vu 
from variables.MCGenTopo import mc_gen_topo
import sys 
import vertex
import argparse 
# Check the skim output
from skim.WGs import fei, semileptonic

if len(sys.argv) != 2:
    sys.exit("Usage: Kstrellell_ntupleProd.py <e/mu>")

mode = sys.argv[1]
if mode not in ["e", "mu"]:
    sys.exit(f"Expecting either e or mu. Saw {mode} Try again")

"""
Let's try to write this python file in a format 
that can be used by agents or batch systems. 

So components of the code should be modular to assist with this. 
"""

# run 1
b2.conditions.prepend_globaltag(ma.getAnalysisGlobaltag()) #needed for FEI 
b2.conditions.prepend_globaltag("release-08-00-09")
b2.conditions.prepend_globaltag('neutrals_2024')


# dummy name for input, can overwrite in basf2 using -i option on command line
rootInputName = "B0_Dstlnu_mdst.root" # contains both e and mu

# dummy name for output, can overwrite in basf2 using -o option on command line
rootOutputName = f"D0_Dst{mode}nu_ntuple.root"

# create path
path = b2.create_path()

# read in input
HOME=".."
inputPath = f"{HOME}/data/"
ma.inputMdstList(filelist = [f"{inputPath}/{rootInputName}"], path = path)

# start with final state particles 
# TODO: we need to have some minor cuts for purity
# TODO: Look at b2help-recommendation (https://belle2.pages.desy.de/performance/recommendations/)

# for when we want to see how our selection does w/ existing skims
# TODO: Find best skim, couldn't find a good dedicated skim 
# if not, should create one for future... 
skim_list = {
    "BtoXll_LFV": ewp.BtoXll_LFV(udstOutput = False), # charged??
    "BtoXll": ewp.BtoXll(udstOutput = False), #charged??
    "TDCPV_ccs": tdcpv.TDCPV_ccs(udstOutput = False), #closest, but mass cuts...
    "TDCPV_inclusiveJpsi": tdcpv.TDCPV_inclusiveJpsi(udstOutput = False),
    "BtoHadTracks": btocharmless.BtoHadTracks(udstOutput = False),
    "CharmoniumPsi": quarkonium.CharmoniumPsi(udstOutput = False)
}
for key, value in skim_list.items():
    value(path=path)
    vm.addAlias(f"skim_{key}", value.flag)



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


slow_pion_cut = " and ".join([
    "[dr < 2]",
    "[abs(dz) < 4]",
    "[thetaInCDCAcceptance==1]"
])
# so I am reconstructing B0 -> D* e nu 
# maybe easier to keep e and µ channels separate
# where D* -> D0bar (-> K pi) pi
# start with final state particles and build up from there

# signal side final state particles
ma.fillParticleList("e+:sig", f"{track_cuts}", path=path)
ma.fillParticleList("mu+:sig", f"{track_cuts}", path=path)
ma.fillParticleList("K+:Kstr", f"{track_cuts}", path=path)
ma.fillParticleList("pi+:Kstr", f"{track_cuts}", path=path) 
ma.fillParticleList("pi0:Kstr", f"{slow_pion_cut}", path=path) 
ma.fillParticleList("pi+:slow", f"{track_cuts}", path=path) # slow pion
#TODO: do slow pion efficiency corrections at some point
#TODO: do photon energy corrections as well 
#TODO: Do we need Bremsstrahlung corrections? 

# Do I need to do photon corrections or is this built in? 

# reconstruct Kstr
# K+pi-
ma.reconstructDecay("K*0:Kpi -> K+:Kstr pi-:Kstr, "", path=path)
# K-short slow pion, where Kshort -> pipi



# We want to apply cut on event shape. For this, we are creating events shape object
# First, create a list of good tracks (using the pion mass hypothesis)
# and good gammas with very minimal cuts
ma.fillParticleList(decayString='pi+:goodtracks',
                    cut=f'{track_selection}',
                    path=path)
ma.fillParticleList(decayString='gamma:goodclusters',
                    cut='E > 0.1 and abs(clusterTiming) < 200',
                    path=path)

# Second, create event shape
ma.buildEventShape(inputListNames=['pi+:goodtracks', 'gamma:goodclusters'],
                   allMoments=True,
                   foxWolfram=True,
                   harmonicMoments=True,
                   cleoCones=True,
                   thrust=True,
                   collisionAxis=True,
                   jets=True,
                   sphericity=True,
                   checkForDuplicates=False,
                   path=path)

# optional: cut on event levels if desired

if mode == "e":
    # STEP 1: Reconstruct lepton pair 
    ma.reconstructDecay(
        "J/psi -> e+:sig e-:sig", "", path=path)  
if mode == "mu":
    
    ma.reconstructDecay(
        "J/psi -> mu+:sig mu-:sig", "", path=path)  
# TODO: do treeFit on the J/psi (w/ no mass constraints)
# NOTE: J/psi here is a placeholder for the lepton pair 
# our signal will actually not come from J/psi, maybe need to label more carefully
vertex.TreeFit("J/psi:sig", conf_level = 0.0, 
                updateAllDaughters=False , path=path)

ma.reconstructDecay("B+:sig -> K*+:all J/psi:sig", "", path=path)

# TODO: do we want to do another TreeFit? 




# so we have truth information
ma.matchMCTruth(list_name = "B+:sig", path = path)
# hadronic FEI recommended cuts for REO
ecl_selection = "[[[clusterReg==1] and [E>0.080]] or [[clusterReg==2] and [E > 0.03]] or [[clusterReg==3] and [E > 0.06]]] "
ecl_selection += "and [clusterNHits > 1.5] and [0.2967 < clusterTheta < 2.6180] and [abs(clusterTiming) < 200]"
roe_mask = (track_selection, ecl_selection)

# reconstruct rest of event (tag side)
# TODO: inputParticlelists should be corrected/calibrated FSPs. Update in future 
ma.buildRestOfEvent('B+:sig', inputParticlelists = None ,path=path)
ma.appendROEMask('B+:sig', 'roe_mask', *roe_mask, path=path)


# use collections to save variables
# variations on variables
cms_kinematics = vu.create_aliases(vc.kinematics, "useCMSFrame({variable})", "CMS")
pidvars = vc.pid #[f"{p}NN" for p in vc.pid[0:6]] + vc.pid 
#PID variables not available in release/08-02, might need light release
skim_vars = [f"skim_{key}" for key in skim_list]

event_vars = ['nTracks','L1Trigger','HighLevelTrigger','nExtraCDCHits','nExtraCDCSegments',
              'beamE', 'beamPx', 'beamPy', 'beamPz', 'Ecms'] + vc.event_kinematics + vc.event_shape

#TODO: Do we need MC Kinematics? 
# collecting variables
fsp_vars = vc.mc_variables + vc.kinematics + pidvars + vc.track + vc.track_hits + ["isSignal"]
d_vars = vc.mc_truth + vc.kinematics + vc.inv_mass + ['foxWolframR2']
b_vars = vc.mc_truth + vc.vertex + vc.kinematics + vc.inv_mass + \
    vc.deltae_mbc  + \
    vu.create_aliases_for_selected(
        fsp_vars, 
        f"B0 -> [D*- -> [anti-D0 -> ^K+ ^pi-] ^pi- ] ^{mode}+", #TODO: FIX ME ROBBIE (and below)
        prefix = ["K_D0", "pi_D0", "pi_Dstr", f"{mode}_B0"]) +\
    vu.create_aliases_for_selected(list_of_variables=d_vars,
                                   decay_string=f'B0 -> [^D*- -> ^anti-D0 pi+] {mode}+') + \
    vu.create_aliases(list_of_variables=['decayModeID'],
                      wrapper='daughter(0,extraInfo({variable}))',
                      prefix="D")

# add some rest of event information
roe_kinematics = ["roeE()", "roeM()", "roeP()", "roeMbc()", "roeDeltae()", "roeEextra()"]
roe_multiplicities = [
    "nROE_Charged()",
    "nROE_Photons()",
    "nROE_NeutralHadrons()",
]
b_vars += roe_kinematics + roe_multiplicities + \
            vc.event_kinematics+ vc.event_level_tracking+ vc.event_shape


# TODO: fox-wolfram moments 
global_vars = 

# beginning of collecting everything into one variable
varlist = global_vars


# sanity check here: 
vm.printAliases()

outputPath = f"{HOME}/data"
# VariablesToNtuple
ma.variablesToNtuple(
    "B0:sig",
    variables=b_vars,
    filename=f"{outputPath}/rootOutputName",
    treename="ntuple",
    path=path,
)
b2.process(path)
print(b2.statistics)
sys.exit("completed!")