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
# [RS] the skims used below live in these modules; they were never imported
from skim.WGs import ewp, tdcpv, btocharmless, quarkonium

if len(sys.argv) != 2:
    sys.exit("Usage: Kstrellell_ntupleProd.py <e/mu>")

mode = sys.argv[1]
if mode not in ["e", "mu"]:
    sys.exit(f"Expecting either e or mu. Saw {mode} Try again")

"""
Let's try to write this python file in a format
that can be used by agents or batch systems.

So components of the code should be modular to assist with this.

[RS] Neutral channel: B0 -> K*0(-> K+ pi-) l+ l-, l = e or mu.
     Changes relative to Tommy's sketch are marked with [RS].
     Reference analysis: Belle II, arXiv:2206.05946.
"""

# run 1
b2.conditions.prepend_globaltag(ma.getAnalysisGlobaltag()) #needed for FEI
b2.conditions.prepend_globaltag("release-08-00-09")
b2.conditions.prepend_globaltag('neutrals_2024')

# dummy name for input, can overwrite in basf2 using -i option on command line
rootInputName = "B0_Kstll_mdst.root" # [RS] was B0_Dstlnu_mdst.root; contains both e and mu

# dummy name for output, can overwrite in basf2 using -o option on command line
rootOutputName = f"B0_Kst{mode}{mode}_ntuple.root" # [RS] was D0_Dst{mode}nu_ntuple.root

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
    # [RS] TDCPV_inclusiveJpsi does not exist in release-08-01-10 (only
    # TDCPV_qqs, TDCPV_ccs, TDCPV_dilepton), so it would crash; removed.
    # "TDCPV_inclusiveJpsi": tdcpv.TDCPV_inclusiveJpsi(udstOutput = False),
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

# [RS] particle-ID requirements from the paper (arXiv:2206.05946, Sec. 3).
# Without them e+:sig / mu+:sig / K+ / pi+ contain EVERY track (the list name
# only sets the mass hypothesis), and K pi l l combinatorics explode.
# Loosen these if you want to study the cuts offline.
pid_cuts = {
    "e":  "electronID > 0.9 and p > 0.4",
    "mu": "muonID > 0.9 and p > 0.8",
    "K":  "binaryPID(321, 211) > 0.6",   # P(K/pi) > 0.6
    "pi": "binaryPID(211, 321) > 0.6",   # P(pi/K) > 0.6
}

# so I am reconstructing B0 -> K*0 l l   [RS] (comment said D* e nu)
# maybe easier to keep e and µ channels separate
# where K*0 -> K+ pi-
# start with final state particles and build up from there

# signal side final state particles
# [RS] only the lepton flavour of this job is loaded, with PID cuts
if mode == "e":
    ma.fillParticleList("e+:uncorrected", f"{track_cuts} and {pid_cuts['e']}", path=path)
    # [RS] bremsstrahlung recovery (paper: photons near the electron are added
    # back). Photon energy thresholds per ECL region are the paper's.
    ma.fillParticleList("gamma:bremsinput",
                        "[clusterReg == 1 and E > 0.075] or [clusterReg == 2 and E > 0.05] "
                        "or [clusterReg == 3 and E > 0.1]", path=path)
    ma.correctBrems("e+:sig", "e+:uncorrected", "gamma:bremsinput", path=path)
if mode == "mu":
    ma.fillParticleList("mu+:sig", f"{track_cuts} and {pid_cuts['mu']}", path=path)
ma.fillParticleList("K+:Kstr", f"{track_cuts} and {pid_cuts['K']}", path=path)
ma.fillParticleList("pi+:Kstr", f"{track_cuts} and {pid_cuts['pi']}", path=path)
# [RS] pi0 and slow-pion lists removed: the neutral K*0 -> K+ pi- needs neither
# (the pi0 line also could not work: fillParticleList cannot make pi0s)
#TODO: do slow pion efficiency corrections at some point
#TODO: do photon energy corrections as well
#TODO: Do we need Bremsstrahlung corrections?   [RS] yes -> correctBrems above

# Do I need to do photon corrections or is this built in?

# reconstruct Kstr
# K+pi-
ma.reconstructDecay("K*0:Kpi -> K+:Kstr pi-:Kstr", "0.396 < M < 1.396", dmID=1, path=path)



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
# [RS] needed for vc.event_kinematics (saved below); same call as in Dstlnu_ntupleProd.py
ma.buildEventKinematics(inputListNames=['pi+:goodtracks', 'gamma:goodclusters'], path=path)

# optional: cut on event levels if desired

# [RS] Build the B directly as B0 -> K*0 l+ l- (three daughters) instead of
# first making a "J/psi -> l l" placeholder. A J/psi particle whose MC match is
# really the B makes MCMatching set c_AddedWrongParticle, so isSignal = 0 for
# every true non-resonant signal event. m(ll) is computed from daughters 1, 2.
b_cut = "Mbc > 5.2 and abs(deltaE) < 0.3"
if mode == "e":
    # ?addbrems: isSignal ignores the photons added by correctBrems
    ma.reconstructDecay("B0:sig -> K*0:Kpi e+:sig e-:sig ?addbrems", b_cut, path=path)
if mode == "mu":
    ma.reconstructDecay("B0:sig -> K*0:Kpi mu+:sig mu-:sig", b_cut, path=path)

# [RS] vertex fit of the whole B (vertex.treeFit; "TreeFit" does not exist).
# conf_level = 0.0 drops candidates whose fit fails, as in Dstlnu_ntupleProd.py.
vertex.treeFit("B0:sig", conf_level = 0.0,
                updateAllDaughters=False , path=path)




# so we have truth information
ma.matchMCTruth(list_name = "B0:sig", path = path)   # [RS] was B+:sig
# hadronic FEI recommended cuts for REO
ecl_selection = "[[[clusterReg==1] and [E>0.080]] or [[clusterReg==2] and [E > 0.03]] or [[clusterReg==3] and [E > 0.06]]] "
ecl_selection += "and [clusterNHits > 1.5] and [0.2967 < clusterTheta < 2.6180] and [abs(clusterTiming) < 200]"
roe_mask = (track_selection, ecl_selection)

# reconstruct rest of event (tag side)
# TODO: inputParticlelists should be corrected/calibrated FSPs. Update in future
ma.buildRestOfEvent('B0:sig', inputParticlelists = None ,path=path)     # [RS] was B+:sig
ma.appendROEMask('B0:sig', 'roe_mask', *roe_mask, path=path)            # [RS] was B+:sig
# [RS] continuum-suppression variables (paper's BDT inputs: cosTBTO, thrustBm,
#      CLEO cones, KSFW moments); the same call is commented out in Dstlnu
ma.buildContinuumSuppression('B0:sig', 'roe_mask', path=path)
# [RS] tag-side vertex, for DeltaZ (B-vertex separation, another BDT input)
vertex.TagV('B0:sig', MCassociation='breco', confidenceLevel=-1,
            maskName='roe_mask', path=path)
# [RS] rank candidates by |deltaE| (paper's best-candidate choice); all are kept
ma.rankByLowest('B0:sig', 'abs(deltaE)', outputVariable='absDeltaE_rank', path=path)


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
# [RS] K* variables (replaces the D-meson d_vars); foxWolframR2 dropped here
#      because it is an event-level variable already in vc.event_shape
kst_vars = vc.mc_truth + vc.kinematics + vc.inv_mass
b_vars = vc.mc_truth + vc.vertex + vc.kinematics + vc.inv_mass + \
    vc.deltae_mbc  + \
    vu.create_aliases_for_selected(
        fsp_vars,
        f"B0 -> [K*0 -> ^K+ ^pi-] ^{mode}+ ^{mode}-",   # [RS] was the D* chain
        # [RS] daughter 1 / 2 = l+ / l- for B0 but l- / l+ for anti-B0,
        #      hence "lep1"/"lep2"; use the charge branch when the sign matters
        prefix = ["K_Kstr", "pi_Kstr", f"{mode}1_B0", f"{mode}2_B0"]) +\
    vu.create_aliases_for_selected(list_of_variables=kst_vars,
                                   decay_string=f'B0 -> ^K*0 {mode}+ {mode}-',
                                   prefix = ["Kstr"]) + \
    vu.create_aliases(list_of_variables=['decayModeID'],
                      wrapper='daughter(0,extraInfo({variable}))',
                      prefix="Kstr")

# add some rest of event information
roe_kinematics = ["roeE()", "roeM()", "roeP()", "roeMbc()", "roeDeltae()", "roeEextra()"]
roe_multiplicities = [
    "nROE_Charged()",
    "nROE_Photons()",
    "nROE_NeutralHadrons()",
]
b_vars += roe_kinematics + roe_multiplicities


# TODO: fox-wolfram moments
# [RS] completed: event-level variables (vc.event_kinematics and vc.event_shape
#      are already inside event_vars, so they are not added twice)
#      nExtraCDCHits / nExtraCDCSegments are in both lists -> keep one copy
global_vars = event_vars + [v for v in vc.event_level_tracking if v not in event_vars]

# [RS] K*ll-specific quantities
vm.addAlias("m_ll", "daughterInvM(1, 2)")                                  # dilepton mass, for the J/psi / psi(2S) vetoes
vm.addAlias("q2", "formula(daughterInvM(1, 2) * daughterInvM(1, 2))")     # q^2 = m(ll)^2
vm.addAlias("dz_ll", "abs(daughterDiffOf(1, 2, dz))")                      # BDT input: z-separation of the leptons
vm.addAlias("B_rank", "extraInfo(absDeltaE_rank)")                         # 1 = best candidate
# (B vertex probability, another BDT input, is chiProb, already saved via vc.vertex)
cs_vars = ["R2", "cosTBTO", "cosTBz", "thrustBm", "thrustOm", "DeltaZ",
           "useCMSFrame(cosTheta)", "roeE(roe_mask)"] + \
          [f"CleoConeCS({i})" for i in range(1, 10)]
kstll_vars = ["m_ll", "q2", "dz_ll", "B_rank"] + cs_vars

# beginning of collecting everything into one variable
varlist = b_vars + global_vars + skim_vars + kstll_vars   # [RS] everything that is written


# sanity check here:
vm.printAliases()

outputPath = f"{HOME}/data"
# VariablesToNtuple
ma.variablesToNtuple(
    "B0:sig",
    variables=varlist,                                # [RS] was b_vars only
    filename=f"{outputPath}/{rootOutputName}",       # [RS] braces were missing
    treename="ntuple",
    path=path,
)
b2.process(path)
print(b2.statistics)
sys.exit("completed!")
