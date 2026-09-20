# Reference analyses — curated summaries for the agent

Condensed, factual summaries of the published analyses this framework's
selections follow. The agent reads this file at the planning stage
(`read_references` tool); cite the papers, not this file.

## Semileptonic / semitauonic B decays

**Waheed et al. [Belle], PRD 100, 052007 (2019)** — untagged
B0 → D\*⁻ℓ⁺ν, |V_cb|.
- Variables: m(Kπ) window around m(D0); Δm = m(D\*)−m(D0) (very narrow,
  slow-pion signature); cos θ_BY for the B–D\*ℓ pairing; Fox–Wolfram R2
  against continuum.
- e and μ analyzed separately and averaged; electron-specific radiative
  effects treated separately.
- Backgrounds split into: fake D\* (Δm sideband), continuum (off-resonance
  data), uncorrelated D\*–ℓ combinations, D\*\* feed-down; each normalized
  in a control region.
- Note structure: per-cut motivation with distributions before the cut,
  cutflow, background composition table, control-region fits, full
  systematics table (tracking ~0.3%/track, lepton ID ~1–2%, N_BB/f00
  ~1–2%, sub-decay BFs <1%).

**BaBar (Lees et al.), PRD 88, 072012 (2013)** — hadronic-tag
B → D(\*)τν / R(D(\*)).
- Full hadronic tag reconstruction; signal separated in (m²_miss, p\*_ℓ)
  with m²_miss the primary discriminant; extra ECL energy (E_extra) as a
  consistency variable — the conceptual ancestor of our E_ROE cut.
- D\*\*ℓν feed-down controlled with a dedicated D(\*)π⁰ℓ control sample.

**Caria et al. [Belle], PRL 124, 161803 (2020)** — semileptonic-tag
R(D(\*)).
- e and μ signal leptons as simultaneous categories sharing the signal
  strength in the fit.
- Signal extraction: 2D fit; backgrounds from MC shapes with data-driven
  normalizations.

**Belle II, PRD 110, 072020 (2024)** — hadronic-tag R(D\*).
- Fit categories per lepton flavor; systematics dominated by MC statistics
  of backgrounds, D\*\* modeling, and PID.

## Rare b → sℓℓ decays

**Wei et al. [Belle], PRL 103, 171801 (2009)** — B → K(\*)ℓℓ BF and A_FB.
- Selection: Mbc > 5.27 GeV and mode/flavor-dependent ΔE windows,
  wider on the low side for electrons (bremsstrahlung); K\* mass window
  around 0.896 GeV.
- Charmonium vetoes in m(ℓℓ), asymmetric and wider for ee (approximately
  −0.25/+0.08 GeV around m(J/ψ) for ee vs −0.10/+0.08 for μμ; similar
  around ψ(2S)).
- Vetoed J/ψ K(\*) events are the control channel: shapes, efficiencies,
  and PID calibrated there.
- Combinatorial background: fit of the Mbc distribution with an ARGUS
  shape; signal as a Gaussian-like peak.

**BaBar (Lees et al.), PRD 86, 032012 (2012)** — B → K(\*)ℓℓ.
- Similar structure; multivariate continuum suppression; charmonium
  vetoes with radiative-tail treatment for electrons.

## Wei et al. (Belle), PRL 103, 171801 (2009) — B -> K* l+ l-

First statistically significant B -> K*(892) l+ l- measurement.
Reconstruction: K* mass window around 0.896 GeV; beam-constrained mass
Mbc > 5.27 GeV and an energy-difference Delta E window, asymmetric and
wider on the low side for electrons (bremsstrahlung). Charmonium
backgrounds B -> J/psi(psi(2S)) K* removed with asymmetric vetoes in the
dilepton mass, again wider on the low side for e+e-; the vetoed
J/psi K* sample serves as the control channel for efficiencies and PID.
Dominant remaining backgrounds: continuum qqbar and generic BBbar
combinatorics, fit with an ARGUS shape in Mbc and a linear Delta E.

## Belle II, arXiv:2206.05946 — B -> K*(892) l+ l- with 189 fb^-1

Same selection strategy as Wei et al. with explicit veto windows:
J/psi excluded for M(mu+mu-) in [2.946, 3.176] GeV and M(e+e-) in
[2.846, 3.176] GeV (psi(2S) vetoed similarly at its mass). Signal
extracted from a 2D unbinned Mbc-Delta E fit (ARGUS + linear for
combinatorial background); about 40-80 signal candidates per channel at
189 fb^-1. Continuum suppressed with event-shape variables.

## Conventions for a publication-grade analysis note

- Every section opens with a short paragraph saying what the section
  establishes and why it matters, before any table or plot.
- Every cut: state the background it targets, show the distribution that
  motivates it (with the cut indicated), and the scan that fixed its value.
- Cutflow table with per-stage and cumulative efficiencies and binomial
  uncertainties.
- Background section: composition table, and for each component either a
  control region (with yield and purity) or an explicit statement of how
  data would constrain it.
- Results: the extraction formula with every input defined and sourced;
  central value, statistical uncertainty, and the validation of the
  statistical method (toys/pulls where a fit is used).
- Discussion: limitations ordered by importance, each with the concrete
  path to removing it; systematics outlook with magnitudes borrowed from
  the published analyses above.
- Figures referenced from the text by file name; numbers in tables, not
  prose.
