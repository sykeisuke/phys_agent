# Physics Analysis Agent — B → D\*τν Sensitivity Study

An undergraduate research project on the semileptonic B-meson decay
**B → D\*(→ Dπ) τν**, carried out together with an AI agent.
Instead of official Belle II samples, we **run EvtGen locally on a laptop
(macOS, Apple Silicon) to produce our own MC**, and study the sensitivity of an
R(D\*) measurement at the generator level plus a simple detector smearing.

---

## 1. Physics background

The semitauonic decay B → D\*τν is compared with the light-lepton modes
B → D\*ℓν (ℓ = e, μ) through the ratio

$$R(D^*) = \frac{\mathcal{B}(B \to D^* \tau \nu)}{\mathcal{B}(B \to D^* \ell \nu)}$$

which is precisely predicted in the Standard Model (~0.25). Measured values
have long sat above the SM prediction, making this a well-known hint of
**lepton-flavor-universality violation** (charged Higgs or leptoquark
contributions).

The decay is a tree-level b → c transition (W emission):

![Feynman diagram of B → D* tau nu](docs/figures/feynman_b2dsttaunu.svg)

Because the τ decays promptly and produces multiple neutrinos, **the τ mode
has large missing energy**. The discriminating variables are:

| Variable | Definition | Feature |
|---|---|---|
| m²_miss | (p_B − p_D\* − p_ℓ)² | ℓν modes peak at 0; τ modes spread to positive values |
| p\*_ℓ | lepton momentum in the B rest frame | secondary leptons from τ are soft |
| q² | (p_B − p_D\*)² | τ modes sit at high q² due to the mass threshold |

---

## 2. AI-agent workflow

This repository doubles as a testbed for an "AI for Physics" agent.
The agent advances the analysis in the loop below, with **user (student)
approval at each step**.

```mermaid
flowchart LR
    U(["👤 User<br/>(student)"]) -->|"e.g. Evaluate R(D*)<br/>sensitivity"| A(["🤖 AI Agent"])

    subgraph K["1 · What the AI can access"]
        direction TB
        K1["📚 Internal knowledge<br/>docs/ · CLAUDE.md · code"]
        K2["🛠 Analysis tools<br/>EvtGen · Python · uproot"]
    end

    subgraph W["2 · Analysis workflow"]
        direction TB
        P["📋 Plan<br/>understand goal, make plan"] --> E["⚙️ Execute<br/>generate MC, select events,<br/>estimate background"]
        E --> R["📈 Report<br/>plots, results, summary"]
    end

    A --> W
    K -.-> A

    R --> D{"3 · OK to<br/>proceed?"}
    D -->|YES · approve| N["4 · Final output<br/>analysis note (Markdown/LaTeX)<br/>plots · tables · conclusions"]
    D -->|NO · feedback| P
```

Instructions and conventions for the agent are collected in
[CLAUDE.md](CLAUDE.md) (the *Internal Knowledge* box in the figure).

---

## 3. Repository layout

```
phys_agent/
├── README.md               # this file (overall instructions)
├── CLAUDE.md               # AI-agent conventions and physics conventions
├── docs/
│   └── figures/            # Feynman diagrams and report figures
├── generation/             # MC generation (EvtGen)
│   ├── dec/                # user decay files
│   │   ├── B0_Dsttaunu.dec   # signal:        B0 → D*∓ τ± ν
│   │   └── B0_Dstmunu.dec    # normalization: B0 → D*∓ μ± ν
│   ├── src/generate.cc     # EvtGen driver (HepMC3 output)
│   └── build.sh            # build script
├── scripts/
│   └── env.sh              # conda environment activation
├── analysis/
│   └── plot_m2miss.py      # truth-level m²_miss / p*_ℓ / q² distributions
├── fastsim/                # simple detector smearing (Phase 2)
│   ├── smear.py            # detector model (resolution, acceptance, efficiency)
│   └── apply_fastsim.py    # apply smearing + compare with truth
├── data/                   # generated MC (not tracked by git)
└── plots/                  # output plots
```

---

## 4. Setup

We use EvtGen from conda-forge (osx-arm64 supported). **No full detector
simulation (basf2/Geant4) is needed.**

```bash
conda create -y -n physagent -c conda-forge evtgen pyhepmc uproot awkward numpy matplotlib-base cxx-compiler
```

Then, at the start of every session:

```bash
source scripts/env.sh
```

---

## 5. MC generation

Generate Υ(4S) → B0 B̄0 and force one B into the signal decay (the standard
`B0sig` alias approach). The other B decays generically according to the
DECAY.DEC shipped with EvtGen. The Υ(4S) is given a Belle II-like boost
(E_HER = 7, E_LER = 4 GeV, approximately pz ≈ 3 GeV).

```bash
bash generation/build.sh             # compile (first time only)
./generation/bin/generate generation/dec/B0_Dsttaunu.dec 5000 data/signal_taunu.hepmc 1 generation/dec/tau_native.dec
./generation/bin/generate generation/dec/B0_Dstmunu.dec  5000 data/norm_munu.hepmc   2 generation/dec/tau_native.dec
```

> **Note**: The conda-forge osx-arm64 build of Tauola++ crashes at
> initialization (`STOP IN APKMAS`), so we do not use Tauola; τ decays are
> described with EvtGen native models
> ([tau_native.dec](generation/dec/tau_native.dec), taken from
> DECAY_2010.DEC). The driver sets up only Photos and Pythia by hand.

Decay chains (forced in v1 to keep the reconstruction simple):

- **Signal**: B0 → D\*⁻ τ⁺ ν_τ,  D\*⁻ → D̄0 π⁻,  D̄0 → K⁺ π⁻,  τ⁺ → μ⁺ ν ν̄
- **Norm**: B0 → D\*⁻ μ⁺ ν_μ,  same D\* chain
- Form factor: ISGW2 in v1 (to be updated to BGL/CLN later)

## 6. Analysis (Phase 1: truth level)

```bash
python analysis/plot_m2miss.py data/signal_taunu.hepmc data/norm_munu.hepmc
```

Produces signal vs normalization comparison plots of m²_miss, p\*_ℓ, and q²
in `plots/`. The first milestone is to confirm that the ℓν mode peaks at
m²_miss = 0 while the τν mode develops a broad positive tail.

First results (5000 events / mode, truth level):

| | |
|---|---|
| ![m2miss](docs/figures/m2miss.png) | ![p*_lep](docs/figures/plep_star.png) |

The μν mode peaks sharply at m²_miss = 0, while the τν mode is broad and
positive because of the three neutrinos. In p\*_ℓ the secondary muon from the
τ is clearly softer.

## 7. Fast simulation (Phase 2: detector smearing)

Instead of a full detector simulation, the simple detector model in
`fastsim/smear.py` smears the charged tracks (K, π, slow π, μ):

| Effect | Model |
|---|---|
| Momentum resolution | σ_p/p = 0.5% (Gaussian; direction unchanged, E recomputed from the true mass) |
| Acceptance | 17° < θ_lab < 150° (Belle II CDC-like) |
| Tracking efficiency | 95% per track, flat in p and θ |

The D\* is reconstructed as the sum of the three smeared tracks (K, π,
slow π), and p_B is taken from truth (a stand-in for the beam / B_tag
constraint until Phase 3). Events in which any of the four tracks is lost
are discarded as reconstruction failures.

```bash
python fastsim/apply_fastsim.py data/signal_taunu.hepmc data/norm_munu.hepmc 42
```

Results (5000 events / mode, seed 42):

| Mode | Reconstruction efficiency | Breakdown (approx.) |
|---|---|---|
| B → D\*τν (signal) | 59.2% | acceptance × (0.95)⁴ ≈ 0.73 × 0.81 |
| B → D\*μν (norm.) | 61.3% | same |

| | |
|---|---|
| ![m2miss fastsim vs truth](docs/figures/m2miss_fastsim_vs_truth.png) | ![m2miss peak zoom](docs/figures/m2miss_peak_zoom.png) |

The μν-mode m²_miss peak, delta-like at truth level, broadens to
σ ≈ 0.07 GeV² after smearing. That is still orders of magnitude narrower
than the broad τν distribution (several GeV²), so the discriminating power
of m²_miss largely survives. p\*_ℓ and q² are essentially unchanged by the
0.5% momentum resolution, since their widths are physics-dominated and far
larger than the resolution.

## 8. Roadmap

- [x] **Phase 1**: local EvtGen generation + truth-level discriminating variables
- [x] **Phase 2**: fast sim (momentum resolution, acceptance, efficiency smearing)
- [ ] **Phase 3**: D\* reconstruction + missing 4-momentum from the ROE → template fit for the R(D\*) statistical sensitivity
- [ ] **Phase 4**: additional background modes (B → D\*\*ℓν, generic BB̄), discussion of systematics
- [ ] **Final**: automated analysis note (Markdown/LaTeX)

---

*Keisuke Yoshihara (kyoshiha@hawaii.edu) — undergraduate research training project, UH Mānoa*
