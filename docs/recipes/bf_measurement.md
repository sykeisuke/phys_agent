# Recipe: branching-fraction measurement

Result: B(signal mode) with statistical and systematic uncertainties,
per channel and combined; comparison with the published value.

| Field | Default |
|---|---|
| 1 Goal | B(mode) = N_sig / (ε · N_BB̄ · f · B(sub-decays)) or relative to a normalization mode when one is available (then most systematics cancel; prefer this) |
| 2 Samples | from `CONTEXT.md`: signal MC (efficiency), normalization or control MC, generic BB̄ and continuum MC (backgrounds). Raw counts if weights are unknown |
| 3 Selection mode | Mode 1 when a reference selection file exists for the mode; otherwise Mode 2 with FoM `syst` (below) |
| 4 Backgrounds | charmonium/resonant feed-down: vetoes in m(ℓℓ) and a control sample; combinatorial BB̄: generic MC, M_bc sideband as control; continuum: MC plus one event-shape cut; what is absent is listed as a limitation |
| 5 Extraction | template fit of M_bc (or ΔE) per channel with signal and background templates from *independent* samples; closure on the Asimov dataset, then pseudo-data drawn from the MC; counting formula as cross-check |
| 6 Systematics | published values for PID, tracking, background shape, K* fraction as placeholders; MC-statistics evaluated here; the table carries a source column |
| 7 Validation | Mode 1: cutflow agrees with the reference within the stated tolerance at every stage and the normalized yield is consistent with the published one. Mode 2: every cut compared with the published value and justified; FoM scans shown; the efficiency and the yield within the expected range |

## Figure of merit for Mode 2

The quantity to minimize is the expected relative uncertainty on the
branching fraction, not a discovery significance.

| Name | Formula | Use |
|---|---|---|
| `s_sqrt_sb` | S/√(S+B) | statistics only; same optimum as minimizing √(S+B)/S |
| `syst` (default) | S/√(S+B+(σ_b·B)²) | with a relative background-model uncertainty σ_b from the published systematics |
| `asimov` | 1/σ_μ from the Asimov template fit at each cut value | uses the shape; the most faithful, the slowest |

The note states the FoM used, the assumed S (from the published BF and
the luminosity) and σ_b, and gives in one line how the optimum moves
under the other FoM.

## Note content specific to this recipe

Cutflow per channel; composition of the signal region; control-region
purities; post-fit figures; the extraction formula with every input;
efficiency table; systematics table with sources; the comparison table
with the published result.
