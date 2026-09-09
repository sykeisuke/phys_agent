#!/bin/bash
# Compile the EvtGen driver against the physagent conda env.
set -e
cd "$(dirname "$0")"
: "${CONDA_PREFIX:?run 'source ../scripts/env.sh' first}"
mkdir -p bin
${CXX:-clang++} -std=c++17 -O2 src/generate.cc -o bin/generate \
    -DEVTGEN_HEPMC3 -DEVTGEN_EXTERNAL -DEVTGEN_PYTHIA -DEVTGEN_PHOTOS -DEVTGEN_TAUOLA \
    -I"$CONDA_PREFIX/include" \
    -L"$CONDA_PREFIX/lib" \
    -lEvtGen -lEvtGenExternal -lHepMC3 \
    -Wl,-rpath,"$CONDA_PREFIX/lib"
echo "built bin/generate"
