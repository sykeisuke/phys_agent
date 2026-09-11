# basf2 integration

[basf2](https://github.com/belle2/basf2) (the Belle II Analysis Software
Framework) is **publicly available under LGPL-3.0**. This project does not
depend on it — everything here runs on a laptop — but basf2 serves two
purposes for us:

1. **Authoritative variable definitions.** Our ntuple branches are aligned
   with the basf2 `VariableManager` names/definitions (table below), so an
   analysis developed on fast-sim ntuples migrates to basf2 by renaming
   branches, not by rederiving physics.
2. **Upgrade path.** The same agent tools can later drive basf2 generation
   and reconstruction (steering-file template below) — first standalone on
   public software, eventually inside a real Belle II analysis.

## Practicalities

- basf2 targets Linux (cvmfs installations at KEK / on the grid; building
  from source needs the `tools`/`externals`/`versioning` repos). On macOS
  the realistic route is a Linux container or an SSH session to KEKCC —
  a Belle II member on the team can simply use cvmfs.
- Only public pieces are used here. **No Belle II internal MC, data, or
  global tags enter this repository or the first paper.**

## Variable mapping (fastsim ntuple ↔ basf2)

| Our branch | basf2 variable | Definition |
|---|---|---|
| `m2miss` | `m2RecoilSignalSide` / `m2Recoil` of the Y = D\*ℓ system | (p_beam/2 − p_Y)² with the nominal B energy |
| `plep_star` | `useCMSFrame(p)` of the lepton | lepton momentum in the e⁺e⁻ CM frame |
| `q2` | `m2Recoil` of the D\* (untagged approximation) | (p_B − p_D\*)² with the beam-constrained B |
| `m_d0` | `daughter(0, daughter(0, M))`-style: `M` of the D0 | invariant mass of the K π pair |
| `delta_m` | `massDifference(0)` of the D\* | m(D\*) − m(D0) |
| `cos_by` | `cosThetaBetweenParticleAndNominalB` | cos of the B–Y angle from E_beam, m_B, m_Y |
| `r2` | `foxWolframR2` (after `buildEventShape`) | Fox-Wolfram H₂/H₀ of the event |
| `p_lep_lab`, `costh_lep_lab` | `p`, `cosTheta` | lab momentum / polar angle |
| `true_mode` | truth-matching (`isSignal`, `mcPDG` of the B) | MC origin label |

Conventions match on purpose: when the grad student produces the same
histograms from basf2 (generator-level or with the full simulation) the
comparison against `fastsim/` validates our detector model variable by
variable.

## Steering-file template (untested here — requires a basf2 environment)

`generation/basf2/dsttaunu_genlevel.py` mirrors the worked example at
generator level: EvtGen with our dec file → MC-truth reconstruction of
B0 → [D\*⁻ → [D̄0 → K⁺π⁻] π⁻] μ⁺ → `VariablesToNtuple` with the names
above. It uses only public basf2 APIs; run it inside any basf2 setup:

```bash
basf2 generation/basf2/dsttaunu_genlevel.py
```

Expected first check: `m2Recoil` from basf2 vs our `m2miss` on the same
decay file — shapes must agree at truth level before any smearing
comparison makes sense.
