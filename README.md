# Physics Analysis Agent

A framework for doing particle-physics analyses **together with an AI
agent**. The agent is not tied to one measurement: it is aimed at **any
analysis that fits the pipeline below** — and it is best suited (at least
at first) to **relatively simple analyses, such as branching-fraction
measurements**, where the workflow is well-defined: generate MC, simulate
the detector response, build ntuples, optimize a selection, count events.

```
EvtGen MC generation  →  fast detector simulation  →  ROOT ntuples (uproot)
                      →  selection optimization    →  result (e.g. BF)
```

Everything runs **locally on a laptop** (macOS, Apple Silicon) — no
experiment framework, no full detector simulation, no ROOT C++ installation.
The pipeline is **mode-agnostic**: adding a new decay mode is a matter of
adding an EvtGen dec file. Two complete demonstrations (a missing-energy
mode and a fully reconstructed rare decay) are collected in
[docs/demonstrations.md](docs/demonstrations.md).

---

## 1. AI-agent workflow

The agent advances an analysis in the loop below, with **user approval
at each step**.

![AI agent workflow](docs/figures/agent_workflow.svg)

Instructions and conventions for the agent are collected in
[CLAUDE.md](CLAUDE.md) (the *Knowledge* item in the figure).

The implementation lives in [agent/](agent/README.md): an LLM drives the
pipeline through typed tools, with the approval gate implemented as a tool
the model must call before anything else.

### Running the agent

One-time setup (on top of the conda environment of section 3):

```bash
pip install anthropic
export ANTHROPIC_API_KEY=sk-ant-...   # from https://console.anthropic.com (usage-based billing)
```

Then give it a task in plain language:

```bash
python -m agent "Using the existing ntuples signal_taunu.root, norm_lnu.root and \
bkg_dststlnu.root, apply the standard D* selection, use scan_cut to find the best \
m2miss threshold, and report the signal selection efficiency."
```

The agent first prints its **plan** and stops at the approval gate:

```text
=== PROPOSED PLAN ===
- Use existing ntuples only (no new MC): signal_taunu.root, norm_lnu.root, bkg_dststlnu.root
- Apply the standard D* selection: |m_d0 - 1.8648| < 0.02, |delta_m - 0.1454| < 0.0025
- Scan m2miss thresholds with scan_cut (FoM = S/sqrt(S+B)) and pick the working point
- Report yields, the optimal cut, the signal efficiency, and an overlay plot
=====================
Approve this plan? [y/N]
```

After a `y` it executes the tools (each call is echoed) and ends with a
Markdown report in the terminal:

```text
[tool] query_ntuple({'root_file': 'signal_taunu.root', 'selection': '(abs(m_d0 - 1.8648) < 0.02) & ...'})
[tool] scan_cut({'signal_file': 'signal_taunu.root', 'background_files': [...], 'variable': 'm2miss', ...})
[tool] plot_variable({'root_files': [...], 'variable': 'm2miss', 'output_name': 'm2miss_compare.png', ...})

## Report
**Selections used**: |m_d0 − 1.8648| < 0.02 GeV, |delta_m − 0.1454| < 0.0025 GeV, m2miss > 1.2 GeV²
| m2miss > (GeV²) | S | B | S/√(S+B) |
| 1.2 | 2522 | 1407 | 40.2 (best) |
**Signal selection efficiency**: 85.3 % (per candidate)
**Plot written**: plots/m2miss_compare.png
**Next steps to consider**: luminosity weighting; p_lep_star as a second variable ...
```

What it can do on its own: generate EvtGen/Pythia8 samples (capped at
2 × 10⁶ events per call), run the fast sim and ntuple production, query and
scan the ntuples, and write plots under `plots/`. File access is confined
to `generation/dec/`, `data/`, and `plots/`. What it never does: skip the
plan approval (rejections, with your typed feedback, are fed back and it
replans), or touch anything outside the repository.

Options: `--model claude-sonnet-5` (fast/cheap, the default is
`claude-opus-5`) and `--review ai`, which replaces the interactive y/N by a
second LLM reviewing the plan against a fixed checklist — useful once a
workflow is established. A typical task costs a few tens of cents of API
usage with the default model, less with Sonnet.

---

## 2. Repository layout

```
phys_agent/
├── README.md               # this file: concept and usage
├── CLAUDE.md               # AI-agent conventions and physics conventions
├── agent/                  # the AI agent (see section 1 / agent/README.md)
│   ├── runner.py           # Plan -> review -> Execute -> Report -> Note loop
│   ├── tools.py            # typed pipeline tools exposed to the LLM
│   └── __main__.py         # CLI: python -m agent "<task>"
├── generation/             # MC generation
│   ├── dec/                # EvtGen decay files, one per mode (section 4)
│   ├── src/generate.cc     # EvtGen driver (HepMC3 output)
│   ├── generate_continuum.py   # Pythia8 continuum -> ntuple, one pass
│   ├── basf2/              # basf2 steering templates (untested here)
│   └── build.sh            # build script
├── fastsim/                # parametric detector response (section 5)
│   ├── smear.py            # tracks, photons, lepton ID + fake rates
│   ├── make_ntuple.py      # D*-chain candidates -> flat ROOT ntuple
│   ├── make_ntuple_exclusive.py # any forced exclusive mode (lnu / ll)
│   └── apply_fastsim.py    # truth-vs-smeared comparison plots
├── analysis/
│   ├── plot_m2miss.py      # truth-level plots
│   ├── measure_bf_dsttaunu.py  # counting BF measurement
│   ├── fit_m2miss.py       # pyhf template fit (simultaneous e/mu channels)
│   ├── note_plots.py       # figures + CR purities + toy study for the note
│   ├── sensitivity_ds.py   # charged-B modes: yields at 1/ab
│   └── sensitivity_kstll.py    # K*ll selection, vetoes, yields
├── docs/
│   ├── demonstrations.md   # the two end-to-end demonstrations
│   ├── notes/              # published analysis notes (PDF)
│   ├── basf2.md            # basf2 variable mapping and migration path
│   └── figures/            # report figures
├── scripts/env.sh          # conda environment activation
├── notes/                  # agent-written notes + review log (not tracked)
├── data/                   # generated MC and ntuples (not tracked)
└── plots/                  # output plots (not tracked)
```

---

## 3. Setup

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

## 4. MC generation

The driver generates Υ(4S) → BB̄ with a Belle II-like boost
(E_HER = 7, E_LER = 4 GeV, approximately pz ≈ 3 GeV). One B is forced into
the decay chain of interest via the standard `sig` alias approach in the dec
file; the other B decays generically according to the DECAY.DEC shipped with
EvtGen.

```bash
bash generation/build.sh             # compile (first time only)
./generation/bin/generate <dec file> <nEvents> <out.hepmc> <seed> generation/dec/tau_native.dec
```

Available modes (each dec file forces a fully reconstructable chain; add a
dec file to add a mode):

| dec file | Mode | Model |
|---|---|---|
| `B0_Dsttaunu.dec` | B0 → D\*⁻τ⁺ν, τ → ℓνν (ℓ = e, μ) | ISGW2 |
| `B0_Dstlnu.dec` | B0 → D\*⁻ℓ⁺ν (ℓ = e, μ) | ISGW2 |
| `B0_Kstll.dec` | B0 → K\*0ℓ⁺ℓ⁻ (b → sℓℓ; ee and μμ) | BTOSLLBALL |
| `generic_bbbar.dec` | generic Υ(4S) → BB̄ (nothing forced) | DECAY.DEC |

(A few further mode files live in `generation/dec/`.) Example:

```bash
./generation/bin/generate generation/dec/B0_Dsttaunu.dec 5000 data/signal_taunu.hepmc 1 generation/dec/tau_native.dec
./generation/bin/generate generation/dec/B0_Dstlnu.dec   5000 data/norm_lnu.hepmc     2 generation/dec/tau_native.dec
./generation/bin/generate generation/dec/B0_Kstll.dec   10000 data/sig_kstll.hepmc   32 generation/dec/tau_native.dec
```

Generation is fast (~2000 events/s) and HepMC ascii files take ~6 KB/event,
so samples are **regenerated on demand from fixed seeds** rather than stored
or committed. Forced-mode samples give signal and background **shapes**,
with absolute normalization applied at analysis time.

### Continuum background

Continuum e⁺e⁻ → qq̄ (u, d, s, c) is generated with **Pythia8** (already in
the conda environment) directly into ntuples — Pythia → fast sim → ROOT in
one pass, no HepMC intermediate:

```bash
python generation/generate_continuum.py 800000 data/continuum_0.root 300
```

σ(qq̄) ≈ 2.6 nb vs σ(BB̄) ≈ 1.1 nb, so a luminosity-matched dataset needs
~2.4 continuum events per BB̄ event; ~14 % of continuum events contain a
true D\* (from cc̄). Generation runs at ~7000 events/s. The printout reports
the cross section and N_generated for the luminosity weight.

> **Note**: The conda-forge osx-arm64 build of Tauola++ crashes at
> initialization (`STOP IN APKMAS`), so we do not use Tauola; τ decays are
> described with EvtGen native models
> ([tau_native.dec](generation/dec/tau_native.dec), taken from
> DECAY_2010.DEC). The driver sets up only Photos and Pythia by hand.

---

## 5. Fast detector simulation

Instead of a full detector simulation, the simple Belle II-like detector
model in `fastsim/smear.py` is applied to every charged track:

| Effect | Model |
|---|---|
| Momentum resolution | σ_p/p = 0.5% (Gaussian; direction unchanged, E recomputed from the true mass) |
| Acceptance | 17° < θ_lab < 150° (Belle II CDC-like) |
| Tracking efficiency | 95% per track, flat in p and θ |
| Muon identification | ε_μ = 90%; fake rates π→μ = 2%, K→μ = 1% (constant, v1) |
| Electron identification | ε_e = 95%; fake rates π/K→e = 0.5% (no bremsstrahlung modeling yet) |
| Mass hypothesis | identified leptons get the e/μ mass hypothesis — misID'd hadrons peak in shifted positions |

Events in which any signal-chain track is lost are discarded as
reconstruction failures. The detector model is deliberately minimal and
lives in one dataclass — refining it (p/θ-dependent resolution, particle ID,
neutrals) is a natural extension.

---

## 6. Ntuple production

`fastsim/make_ntuple.py` runs the fast simulation and writes one row per
reconstructed candidate to a ROOT file with **uproot** (pure Python — no
ROOT C++ installation needed):

```bash
python fastsim/make_ntuple.py <in.hepmc> <out.root> <mode_id> <seed>
```

Since v2 the reconstruction is **fully beam-constrained** — nothing uses the
true B momentum, so BB̄ and continuum are treated identically. A candidate
is a true D\*± with 3 charged tracks plus the highest-p\* charge-correlated
muon in the event; kinematic variables are computed in the e⁺e⁻ CM frame
with p_B = (√s/2, **0**) (the ~0.34 GeV B momentum is neglected, which
smears m²_miss to an RMS of ≈ 0.7 GeV² — the physical cost of not tagging).

Branches (smeared unless noted): `m2miss`, `plep_star`, `q2`, `m_d0`,
`delta_m`, `cos_by` (cosine between the B and the D\*ℓ system, the basf2
`cosThetaBetweenParticleAndNominalB`), `r2` (Fox-Wolfram H₂/H₀, continuum
suppression), `p_lep_lab`, `costh_lep_lab`, `p_dst_lab`,
`m2miss_true`, `plep_star_true`, `q2_true` (NaN without a true B ancestor),
`true_mode` (1 = D\*τν, 2 = D\*μν, 0 = other B, 3 = continuum),
`mode_id`, `event`.

### Rest-of-event (ROE) tag

Every detected particle outside the signal candidate — smeared charged
tracks plus ECL-like photons (σ_E/E = 2 %/√E ⊕ 1 %, E > 50 MeV; K_L,
neutrons and neutrinos are invisible) — forms the ROE, giving four more
branches: `e_tag_cm`, `m_tag`, `n_roe`, `q_roe`, and `m2miss_roe`.

Two instructive findings, both physical:
- **The ROE direction is useless at the Υ(4S)** (`m2miss_roe`): the true B
  momentum is only 0.34 GeV/c, so undetected particles dominate the tag
  direction (median error ≈ 58°). This is exactly why real analyses use
  the cos θ_BY cone or full tag reconstruction (FEI).
- **The ROE energy is powerful**: for a correct signal candidate the ROE is
  just the tag B, while a wrongly paired muon drags signal-side particles
  into the ROE and pushes `e_tag_cm` up. The cut `e_tag_cm < 4.0 GeV`
  improves S/B in the signal region by **×4** (0.055 → 0.22).

Read them back with:

```python
import uproot
events = uproot.open("data/signal_taunu.root")["events"].arrays(library="np")
```

`mode_id` is a per-sample label chosen on the command line, so ntuples from
different samples can be concatenated and still identified. The candidate
finder in `make_ntuple.py` targets D\* chains; `make_ntuple_exclusive.py`
is a truth-seeded, mode-agnostic producer for any forced exclusive mode
(B → hadrons + μν, or fully charged B → hadrons + μ⁺μ⁻), adding the
full-reconstruction variables `mbc`, `delta_e`, and `m_ll`.

---

## 7. Analysis pattern: a branching-fraction measurement

Every BF measurement follows the same steps, all starting from the ntuples:

1. **Samples**: signal mode, normalization/control modes, dominant
   backgrounds (each a dec file + one `make_ntuple.py` run).
2. **Selection**: choose cuts on the ntuple variables and optimize a figure
   of merit (e.g. S/√(S+B)).
3. **Count and correct**: count events in the signal region, correct for the
   reconstruction efficiency (from the same ntuples), and convert to a BF
   using N_BB and the known sub-mode branching fractions.
4. **Report**: plots + a short note with the numbers in tables.

The agent prepares samples and infrastructure and can carry out steps 2–4
itself — or leave them to the user, depending on the review mode.

---

## 8. Demonstrations

Two complete analyses exercise the pipeline end to end — the missing-energy
mode B0 → D\*τν (truth level → fast sim → ntuples → counting and a pyhf
template fit, with closure tests on a luminosity-matched pseudo-dataset)
and the fully reconstructed rare decay B0 → K\*0ℓ⁺ℓ⁻ (Mbc/ΔE, charmonium
vetoes). Results, plots, and the commands to reproduce them:
**[docs/demonstrations.md](docs/demonstrations.md)**.

The agent's final products are **analysis notes** (Plan → Execute → Report
→ Note): after a full analysis it writes a structured note — Introduction /
Samples / Selection optimization / Background estimation / Results /
Discussion / Conclusion — via its `save_note` tool, with every number taken
from the session's tool results. Two complete notes are published in
**[docs/notes/](docs/notes/)**.

---

## License

This project is licensed under the [GNU GPL v3](LICENSE). The τ decay table
[tau_native.dec](generation/dec/tau_native.dec) is derived from DECAY_2010.DEC
shipped with [EvtGen](https://evtgen.hepforge.org/), which is itself GPL-3.0.

---

*Keisuke Yoshihara (kyoshiha@hawaii.edu) — UH Mānoa*
