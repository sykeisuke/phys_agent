// EvtGen driver: generate Upsilon(4S) -> B Bbar events with a user decay
// file and write them out as HepMC3 ascii.
//
// usage: generate <user.dec> <nEvents> <out.hepmc> [seed]

#include <cmath>
#include <cstdlib>
#include <iostream>
#include <list>
#include <string>

#include "EvtGen/EvtGen.hh"
#include "EvtGenBase/EvtAbsRadCorr.hh"
#include "EvtGenBase/EvtDecayBase.hh"
#include "EvtGenBase/EvtHepMCEvent.hh"
#include "EvtGenBase/EvtMTRandomEngine.hh"
#include "EvtGenBase/EvtPDL.hh"
#include "EvtGenBase/EvtParticle.hh"
#include "EvtGenBase/EvtParticleFactory.hh"
#include "EvtGenExternal/EvtExternalGenFactory.hh"
#include "EvtGenExternal/EvtPHOTOS.hh"
#include "EvtGenExternal/EvtPythia.hh"

#include "HepMC3/WriterAscii.h"

int main(int argc, char** argv) {
    if (argc < 4) {
        std::cerr << "usage: " << argv[0]
                  << " <user.dec> <nEvents> <out.hepmc> [seed] [extra.dec ...]\n";
        return 1;
    }
    const std::string userDec = argv[1];
    const int nEvents = std::atoi(argv[2]);
    const std::string outFile = argv[3];
    const unsigned int seed = (argc > 4) ? std::atoi(argv[4]) : 12345;
    std::list<std::string> extraDecs;
    for (int i = 5; i < argc; ++i) extraDecs.push_back(argv[i]);

    const char* prefix = std::getenv("CONDA_PREFIX");
    if (!prefix) {
        std::cerr << "CONDA_PREFIX not set — run 'source scripts/env.sh' first\n";
        return 1;
    }
    const std::string decayFile = std::string(prefix) + "/share/EvtGen/DECAY.DEC";
    const std::string pdtFile = std::string(prefix) + "/share/EvtGen/evt.pdl";

    EvtMTRandomEngine randEng(seed);

    // Set up Photos and Pythia by hand instead of via EvtExternalGenList:
    // Tauola++ crashes at initialization in the conda-forge osx-arm64 build
    // (STOP IN APKMAS), and tau decays use native EvtGen models anyway
    // (dec/tau_native.dec), so the Tauola generator is never defined.
    EvtExternalGenFactory* extFactory = EvtExternalGenFactory::getInstance();
    extFactory->definePythiaGenerator(std::string(prefix) + "/share/Pythia8/xmldoc",
                                      false, true);
    extFactory->definePhotosGenerator("gamma", true);
    EvtAbsRadCorr* radCorr = new EvtPHOTOS();
    std::list<EvtDecayBase*> extraModels;
    extraModels.push_back(new EvtPythia());

    EvtGen evtgen(decayFile, pdtFile, &randEng, radCorr, &extraModels);
    evtgen.readUDecay(userDec.c_str());
    for (const auto& dec : extraDecs) evtgen.readUDecay(dec.c_str());

    // Upsilon(4S) with an approximate Belle II boost:
    // E_HER = 7 GeV (e-), E_LER = 4 GeV (e+), head-on approximation -> pz = 3 GeV
    const EvtId ups = EvtPDL::getId("Upsilon(4S)");
    const double mUps = EvtPDL::getMeanMass(ups);
    const double pz = 3.0;
    const double e = std::sqrt(mUps * mUps + pz * pz);

    HepMC3::WriterAscii writer(outFile);
    for (int i = 0; i < nEvents; ++i) {
        EvtVector4R pInit(e, 0.0, 0.0, pz);
        EvtParticle* parent = EvtParticleFactory::particleFactory(ups, pInit);
        evtgen.generateDecay(parent);

        EvtHepMCEvent hepmcEvent;
        hepmcEvent.constructEvent(parent);
        writer.write_event(*hepmcEvent.getEvent());

        parent->deleteTree();
        if ((i + 1) % 1000 == 0)
            std::cout << "generated " << (i + 1) << " / " << nEvents << "\n";
    }
    writer.close();
    std::cout << "wrote " << nEvents << " events to " << outFile << "\n";
    return 0;
}
