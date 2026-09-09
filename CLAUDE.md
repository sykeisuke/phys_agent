# CLAUDE.md — Physics Analysis Agent instructions

Repository for an undergraduate B → D\*τν sensitivity study. The agent must follow the conventions below.

## Workflow (required)

1. **Plan**: When given an analysis task, first present a short plan to the user (samples to generate, selections, quantities to evaluate) and get approval.
2. **Execute**: Run only after approval. Any change to MC generation or analysis code must be re-run and verified.
3. **Report**: Report results as plots + a short Markdown summary. Put numbers in tables.

## Environment

- conda environment `physagent` (/opt/anaconda3/envs/physagent). Run `source scripts/env.sh` before executing anything.
- EvtGen 2.2.3 (conda-forge, osx-arm64). DECAY.DEC / evt.pdl live in `$CONDA_PREFIX/share/EvtGen/`.
- No full detector simulation. Detector effects are emulated with the smearing in `fastsim/`.

## Physics conventions

- Decay modes are written in the B0 convention: signal = B0 → D\*⁻ τ⁺ ν_τ (charge conjugates implied).
- Belle II-like boost: Υ(4S) with pz ≈ +3 GeV (HER − LER), already set in the C++ driver.
- Units are GeV (natural units). m²_miss is in GeV².
- Form factor: v1 uses ISGW2. When updating to BGL/CLN, update the dec files and README together.
- Fix random seeds via command-line arguments for reproducibility.

## Code conventions

- Do not commit generated files (data/*.hepmc, plots/*.png) — already in .gitignore. Final plots for reports may be copied to docs/figures/.
- When adding a dec file, update the generation command list in the README.
- Python uses pyhepmc + numpy + matplotlib. No ROOT C++ installation (to keep the student environment simple); ntuples are written and read as .root files with **uproot**.

## Working with students

- Explanations are in English, at the undergraduate level. Lead with intuition (helicity suppression, missing mass) before equations.
