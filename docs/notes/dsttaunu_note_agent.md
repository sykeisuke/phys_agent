# Measurement of BF(B0 → D*⁻τ⁺ν) on a Belle II–like pseudo-dataset

## 1. Introduction

Semitauonic B decays B → D*τν are sensitive probes of lepton-flavor universality and of
new physics coupling preferentially to the third generation, quantified by the ratio
R(D*) = BF(B→D*τν)/BF(B→D*ℓν). This note performs a self-contained sensitivity study
of the *absolute* branching fraction BF(B0 → D*⁻τ⁺ν) on a fast-simulated
Upsilon(4S) → BBbar + continuum pseudo-dataset, following the reconstruction strategy of
the published *untagged* semileptonic B → D*ℓν analyses:

- **Waheed et al. [Belle], PRD 100, 052007 (2019)** — D0 mass window, narrow Δm
  (slow-pion) window, Fox–Wolfram R2 for continuum suppression, e/μ channels treated
  separately and combined.
- **BaBar, PRD 88, 072012 (2013)** — m²_miss as the primary discriminant between
  single-neutrino (D*ℓν) and multi-neutrino (D*τν) final states.
- **Caria et al. [Belle], PRL 124, 161803 (2020)** and **Belle II, PRD 110, 072020
  (2024)** — simultaneous e/μ template fit sharing one signal strength.

The measurement is performed both as a cut-and-count and as a binned template fit in
m²_miss, and the two are compared to expose the limitations of a pure MC-truth-based
background subtraction in this framework.

## 2. Data samples and analysis tools

**Framework.** This study uses the agent's standard chain: EvtGen decay files are
turned into HepMC events, passed through a fast detector simulation that emulates
tracking, calorimetry and PID smearing, and reduced to flat ROOT ntuples with one row
per reconstructed (D* + lepton) candidate. Continuum e+e⁻→qqbar is generated directly
into the ntuple format with Pythia8. No new MC was generated for this note; all
samples below already existed in `data/`.

| Sample | Process / generator | Events | Seeds | Role |
|---|---|---|---|---|
| signal_taunu.root | B0→D*⁻(D0π)τ⁺ν, τ→ℓνν, EvtGen, forced chain | 5000 | 1 / 42 | pure-signal cutflow & efficiency |
| norm_lnu.root | B0→D*⁻(D0π)ℓ⁺ν, EvtGen, forced chain | 5000 | 2 / 43 | D*ℓν shape reference |
| bkg_dststlnu.root | B0→D**ℓν feed-down, EvtGen, forced chain | 5000 | 3 / 44 | D** shape reference |
| generic_0..4.root | generic Upsilon(4S)→BBbar, EvtGen (natural BFs) | 5×200 000 | — | pseudo-dataset (w = 1.0 each) |
| continuum_0..2.root | e+e⁻→qqbar, Pythia8 | 3×800 000 | — | pseudo-dataset (w = 0.995 each) |

The **pseudo-dataset** ("data") is the union `generic_0..4.root + continuum_0..2.root`
(~0.9 fb⁻¹), carrying `true_mode` (1 = D*τν, 2 = D*ℓν, 0 = other B, 3 = continuum) so
that truth-based composition studies are possible; this plays the role that a Δm/m_D0
sideband or off-resonance data would play in a real analysis. The generic sample
contains **N_B0 = 965 840** true B0 decays, of which **N(true D*τν) = 14 319**
(generator BF = 1.483%, the closure target of this exercise). The relevant sub-decay
branching product is

B_sub = B(D*→D0π)·B(D0→Kπ)·B(τ→ℓνν, ℓ=e,μ) = 0.677 × 0.0389 × 0.331 = **0.008717**.

The 0.995 relative weight applied to the three continuum files (vs. 1.0 for the
generic-BBbar files) is the cross-section/generated-luminosity normalization factor
already fixed when these pseudo-dataset files were produced in the earlier session
that this note builds on; it is reused unchanged throughout §4, §5 and the new §5.4
projection below.

## 3. Event selection

All cuts are applied in a fixed order (cut & count, one variable at a time), each
motivated by the background it removes and fixed with a distribution or a scan on top
of the preceding cuts.

### 3.1 Preselection: D0 mass and Δm windows

Following Waheed et al., a genuine D0 candidate and a genuine slow pion from D*→D0π
are required:
- |m(Kπ) − 1.8648| < 0.020 GeV (`plots/presel_m_d0.png`)
- |Δm − 0.1454| < 0.0025 GeV (`plots/presel_delta_m.png`)

These reject random Kπ combinations and remove the fake slow-pion background; on
signal_taunu.root this combination keeps 2672/2801 = 95.4% of reconstructed candidates.
(A dedicated Δm-sideband study, see §4, found essentially zero candidates outside a
~10 MeV band around the nominal Δm — this fast simulation does not model random
slow-pion combinatorics, so a genuine "fake-D*" Δm sideband is not available; see the
Discussion.)

### 3.2 Continuum suppression: R2

The Fox–Wolfram ratio R2 separates jetty continuum events (large R2) from the more
isotropic BBbar topology (`plots/presel_r2.png`). A scan of R2 < threshold
(signal = signal_taunu.root, background = generic+continuum) gives:

| R2 cut | S | B | S/√(S+B) |
|---|---|---|---|
| <0.2 | 2033 | 4051 | 26.1 |
| <0.3 | 2482 | 5063 | 28.6 |
| **<0.4** | **2613** | **5671** | **28.7** |
| <0.5 | 2661 | 6108 | 28.4 |
| <0.7 | 2672 | 6516 | 27.9 |

The figure of merit is flat around 0.3–0.45; **R2 < 0.4** is adopted, keeping 97.8% of
the surviving signal.

### 3.3 Wrong-pairing / generic-BBbar rejection: e_tag_cm

`e_tag_cm`, the CM energy of the rest-of-event ("tag") side, clusters near the beam
energy (~5.29 GeV) for correctly identified events and develops a high-side tail for
wrong D*–lepton pairings and generic BBbar combinatorics (`plots/presel_e_tag_cm.png`).
Scanning e_tag_cm < threshold:

| e_tag_cm cut | S | B | S/√(S+B) |
|---|---|---|---|
| <4.5 | 1861 | 2295 | 28.9 |
| <5.0 | 2261 | 3057 | 31.0 |
| <5.2 | 2362 | 3389 | 31.2 |
| **<5.4** | **2605** | **3780** | **32.6** |
| <5.6 | 2611 | 4054 | 32.0 |
| <6.0 | 2613 | 4539 | 30.9 |

The maximum is at **e_tag_cm < 5.4 GeV**, retaining 99.7% of the signal surviving the
previous cuts while rejecting a substantial wrong-pairing/generic tail.

### 3.4 Signal region: m²_miss

m²_miss is the primary τν vs ℓν discriminant (BaBar): the two extra neutrinos in the
τ decay push m²_miss to higher values than the single-neutrino D*ℓν decays
(`plots/presel_m2miss.png`, cut line at 1.0 GeV²). Scanning m2miss > threshold on top
of all preceding cuts:

| m²_miss cut (GeV²) | S | B | S/√(S+B) |
|---|---|---|---|
| >0.0 | 2483 | 2143 | 36.5 |
| >0.5 | 2428 | 1634 | 38.1 |
| >0.75 | 2380 | 1437 | 38.5 |
| **>1.0** | **2321** | **1294** | **38.6** |
| >1.25 | 2236 | 1200 | 38.2 |
| >1.5 | 2146 | 1132 | 37.5 |

**m²_miss > 1.0 GeV²** is adopted as the signal region (SR).

### 3.5 Cutflow (signal_taunu.root, N_generated = 5000)

| Stage | N | cumulative eff. | stage eff. |
|---|---:|---:|---:|
| Generated | 5000 | 100.00% | — |
| Candidate reconstructed | 2801 | 56.02 ± 0.70% | 56.02% |
| + D0 mass window | 2672 | 53.44 ± 0.71% | 95.39% |
| + Δm window | 2672 | 53.44 ± 0.71% | 100.00% |
| + R2 < 0.4 | 2613 | 52.26 ± 0.71% | 97.79% |
| + e_tag_cm < 5.4 | 2605 | 52.10 ± 0.71% | 99.69% |
| + m²_miss > 1.0 (SR, final) | 2321 | **46.42 ± 0.71%** | 89.10% |

The dominant loss is candidate reconstruction (~44%, geometric/kinematic acceptance of
the fast simulation); the analysis cuts on top of that are efficient (89% overall for
the four discriminating cuts combined), as intended by choosing the working points from
the flat region of each scan.

## 4. Background estimation

**Composition of the pseudo-dataset in the SR** (full selection, weighted:
generic ×1.0, continuum ×0.995), obtained by summing `query_ntuple` results over the 8
dataset files and illustrated in `plots/sr_composition_q2.png`:

| Component | Weighted yield | Fraction |
|---|---:|---:|
| D*τν (true_mode=1) | 99.0 | 7.7% |
| D*ℓν (true_mode=2) | 176.0 | 13.6% |
| other B (incl. D**ℓν feed-down) | 952.0 | 73.6% |
| continuum | 66.7 | 5.2% |
| **Total** | **1293.7** | 100% |

The signal region purity is only ~8%; the dominant background is generic BBbar
(other-B), reflecting that a hard cut-and-count on an untagged sample cannot separate
D*τν from the far more copious hadronic/semileptonic BBbar background as cleanly as a
tagged analysis.

**Control regions**, each defined by inverting one selection variable and evaluated
with `plot_stacked`:

| CR | Selection | Weighted N | Dominant component | Purity |
|---|---|---:|---|---:|
| Continuum-enriched | presel + R2 > 0.5 | 426.9 | continuum | 97.7% (`plots/cr_continuum_m2miss.png`) |
| Normalization-enriched | presel+R2+e_tag_cm + −1<m²_miss<0.5 | 1369.6 | D*ℓν | 80.8% (`plots/cr_norm_plep_star.png`) |
| Wrong-pairing/generic-enriched | presel+R2 + e_tag_cm ≥ 5.4 | 1889.4 | other B | 78.5% (`plots/cr_generic_m2miss.png`) |

These three regions validate, respectively, the R2 cut (continuum control, 97.7%
pure), the m²_miss cut (normalization control, 80.8% D*ℓν — the expected companion
mode), and the e_tag_cm cut (wrong-pairing/generic control, 78.5% other-B). In a real
analysis these would be used to calibrate data/MC scale factors for each background
component instead of the truth-level subtraction used below.

## 5. Results

### 5.1 Cut-and-count

BF(B0→D*τν) = (N_obs^SR − N_bkg,truth^SR) / (N_B0 · B_sub · ε_sig)

with all inputs from the tool outputs above:

- N_obs^SR = 1293.665 (weighted SR yield, §4)
- N_bkg,truth^SR = 1194.665 (all `true_mode ≠ 1` weighted yield, MC-truth subtraction)
- N_B0 = 965 840 (given)
- B_sub = 0.008717 (given)
- ε_sig = 2321/5000 = 0.4642 (cutflow, §3.5)

giving N_sig = 99.0 and

**BF_counting = 2.53% ± 0.25% (stat, from √N_sig)**, i.e. a closure ratio of
**1.71×** relative to the 1.483% generator truth. Note that this √N_sig uncertainty
reflects only the statistical fluctuation of the truth-tagged signal count; it treats
N_bkg,truth as an exactly-known, noise-free subtraction, which is specific to this
truth-level closure test and is not available in a real measurement (see §6.1) — a
real analysis would add in quadrature the statistical (and systematic) uncertainty of
the background estimate itself, which is not attempted here.

### 5.2 Template fit

`fit_templates` was run on the same pseudo-dataset (presel + R2<0.4 + e_tag_cm<5.4,
*without* the m²_miss cut, which is instead the fit variable), with
`signal_selection = (true_mode==1) & (|lep_true_pid| ∈ {11,13})`, simultaneous e/μ fit
(`plots/fit_m2miss_taunu.png`):

| Channel | μ | BF = μ × 1.483% |
|---|---:|---:|
| simultaneous e+μ | 1.000 ± 0.491 | **1.48% ± 0.73%** |
| e-only | 1.000 ± 0.618 | 1.48% ± 0.92% |
| μ-only | 1.000 ± 0.800 | 1.48% ± 1.19% |

No independent goodness-of-fit check (χ²/ndof, pull study, or a train/test split of
the MC into independent template-building and fitting subsamples) was performed; the
exact μ = 1.000 in every channel is expected by construction (§5.3, §6.2) and is not
by itself evidence that the fit machinery is unbiased on data with independently
mis-modeled backgrounds.

### 5.3 Counting vs. fit

| Method | BF | Closure (BF/1.483%) |
|---|---|---:|
| Cut & count | 2.53% ± 0.25% | 1.71 |
| Template fit (e+μ) | 1.48% ± 0.73% | **1.00** |

The template fit closes essentially perfectly, while the single-cut counting method
overshoots by 71%. Both use the *same* truth flag (`true_mode==1`) to define signal;
the difference is that the fit compares the full m²_miss *shape* (24 bins across
[−2,8] GeV²) of the S and B templates simultaneously, while the cut-and-count freezes
a single hard boundary at m²_miss > 1.0 GeV². A plausible explanation is that
`true_mode` labels the *generator-level decay class present in the event* rather than
a candidate-by-candidate truth match, so a subset of true-D*τν-tagged rows in the
generic sample corresponds to imperfectly paired candidates (e.g. the correct D*
combined with a lepton from the companion B) that happen to satisfy the SR cuts; these
would inflate the single-bin counting result but be correctly absorbed into the
S-template shape used by the fit. This explanation has **not been verified
quantitatively** here (e.g. with an explicit count of mis-paired vs. correctly-paired
true-signal rows) and should be treated as a hypothesis; regardless of its exact
origin, this comparison is a closure test of the extraction method on truth-labeled
MC, not an independent cross-check (see §6).

### 5.4 Sensitivity projection

To gauge how the template-fit precision of §5.2 would evolve with more integrated
luminosity, `fit_templates` was re-run with `lumi_projection=true` on **exactly** the
§5.2 preselection and fit configuration — same files and weights (`generic_0..4.root`
×1.0, `continuum_0..2.root`×0.995), same selection
(`|m_d0−1.8648|<0.020 & |Δm−0.1454|<0.0025 & R2<0.4 & e_tag_cm<5.4`, no m²_miss cut),
same `signal_selection = (true_mode==1) & (|lep_true_pid|∈{11,13})`, same fit variable
m²_miss over 24 bins in [−2,8] GeV², simultaneous e/μ fit. As a stability check, the
nominal-luminosity (0.000906 ab⁻¹) output of this re-run reproduces §5.2 exactly
(μ = 1.000 ± 0.491 combined, ± 0.618 e-only, ± 0.800 μ-only), confirming the fit is
deterministic and the projection starts from the same fit configuration (subject to
the same self-closure caveat of §5.2/§6.2 — this reproduction is not an independent
fit-quality check).

The tool then computes the **statistical-only Asimov** expected precision on μ at
several benchmark luminosities, keeping the background *shapes* fixed to their nominal
MC prediction (i.e. no template-shape or background-normalization uncertainty is
propagated — only Poisson counting statistics of signal and background in each
m²_miss bin). Converting the relative precision on μ into an absolute precision on
BF via BF = μ × 1.483% (generator truth, §2):

| Integrated luminosity | Rel. precision on μ (=BF) | Projected BF uncertainty (stat only) |
|---|---:|---:|
| 0.000906 ab⁻¹ (this dataset) | 49.1% | 1.48% ± 0.73% |
| 0.1 ab⁻¹ | 3.2% | 1.483% ± 0.047% |
| 0.36 ab⁻¹ | 1.7% | 1.483% ± 0.025% |
| 1 ab⁻¹ | 1.0% | 1.483% ± 0.015% |
| 5 ab⁻¹ | 0.5% | 1.483% ± 0.007% |
| 50 ab⁻¹ | 0.2% | 1.483% ± 0.003% |

(figure: `plots/projection_fit_m2miss_taunu_projection.png`; post-fit reproduction:
`plots/fit_m2miss_taunu_projection.png`).

**This projection is statistical-only and should not be read as a realistic forecast
below the sub-percent level.** Several caveats apply, consistent with §6:

1. Background *shapes* are frozen to the nominal MC templates at every luminosity
   point; no MC-statistics or shape-systematic uncertainty on the background templates
   is propagated, even though a real background prediction (with its own finite
   control-sample size) would carry an uncertainty that does not shrink simply as
   1/√L.
2. The fit machinery underlying this projection has itself only been shown to close
   on truth-labeled MC (§5.2, §6.2); no independent train/test validation of the fit
   has been performed, so the projected *shape* of the precision curve (not just its
   normalization) inherits that limitation.
3. No experimental or physics-modeling systematic uncertainty is included at all. In a
   real measurement of this type, systematics such as N_BB̄/f+−,00, tracking and
   lepton-ID efficiency, and D-meson sub-decay branching fractions do not shrink with
   luminosity and eventually dominate: the Belle II untagged B→Dℓν branching-fraction
   measurement quotes systematic contributions of order 1.9% (N_BB̄, f+−/f00), 0.9–1.2%
   (tracking), 0.8–1.7% (D-meson branching fractions) and 1.2–3.1% (lepton ID), summing
   in quadrature to a few percent [Belle II, arXiv:2210.13143]; the Belle II hadronic-tag
   R(D*) analysis separately reports ≈2.1% from hadronic-B-decay modeling and ≈2.0% from
   fit-template PDF-shape systematics [Adachi et al., PRD 110, 072020 (2024),
   arXiv:2401.02840]. Taking these together as representative of an untagged D*τν
   measurement with a similar reconstruction strategy, **a realistic projection would
   flatten at a systematic floor of roughly 3%** once the statistical uncertainty drops
   below that level (i.e. above ≈0.3–1 ab⁻¹ in the table), rather than continuing to
   improve as 1/√L out to 50 ab⁻¹ as the purely statistical numbers above suggest.

## 6. Discussion — limitations

1. **MC-truth background subtraction.** Both the counting and the fit define signal
   through the `true_mode`/`lep_true_pid` truth flags of the same simulation sample
   being measured. A real measurement instead constrains each background component in
   data: continuum from off-resonance data or the R2-sideband analog of
   `cr_continuum_m2miss.png`, D*ℓν feed-down/normalization from the low-m²_miss control
   region, and generic BBbar from a wrong-pairing/e_tag_cm-sideband analog, all fit
   simultaneously with the signal region. As noted in §5.1, the quoted cut-and-count
   uncertainty does not include the (unknown, in a real analysis) statistical and
   systematic uncertainty of this background estimate.
2. **Template self-closure.** The fit_templates result (μ = 1.000 in every channel) is
   a closure test: the "data" and the S/B templates are built from the same truth
   labels in the same simulation, so perfect closure is expected by construction and
   does not demonstrate the method's accuracy on independent data. An unbiased test
   would fit pseudo-experiments drawn from an independent MC sample or use toys with
   the templates fixed from a training sample and floating on a statistically
   independent test sample; no such χ²/ndof or pull/toy validation has been performed
   in this note (§5.2), and the §5.4 luminosity projection inherits this same
   limitation.
3. **No systematic uncertainties evaluated.** Following the published analyses, a
   full measurement would include: tracking efficiency (~0.3%/track), lepton PID
   (~1–2%), N_BB̄ and f00/f+− (~1–2%), sub-decay branching fractions B_sub (<1%,
   from PDG uncertainties on B(D*→D0π), B(D0→Kπ), B(τ→ℓνν)), D** feed-down modeling
   (shape and normalization), and MC statistics of the background templates
   themselves (the generic sample used here has O(10²) surviving BBbar events per SR
   bin — a real analysis needs correspondingly larger background MC). The §5.4
   projection quantifies concretely why this matters: the purely statistical precision
   would fall below 1% already around 1 ab⁻¹, well before the ~50 ab⁻¹ full Belle II
   dataset, at which point these systematics (not luminosity) set the ultimate
   precision of the measurement, flattening around a ~3% floor rather than continuing
   to shrink as 1/√L.
4. **No fake-D* combinatorial background is modeled** in this fast simulation: a
   dedicated Δm-sideband scan (§3.1) found zero candidates outside a narrow band
   around the true Δm, so the classic "fake D*" control region of Waheed et al. could
   not be reproduced here; a full detector simulation would populate this sideband
   and it should be added as a fourth control region.
5. **Single-variable, cut-based continuum/wrong-pairing suppression.** The published
   analyses at this level of purity often add cos θ_BY consistency and/or a
   multivariate continuum-suppression classifier; per the analysis policy of this
   framework, a simple one-variable-at-a-time cut & count was used instead to keep
   systematics tractable, at the cost of a lower SR purity (7.7%) than a tagged
   analysis would achieve.
6. **Statistical precision.** With ε_sig ≈ 46% and the modest generic+continuum
   sample size (~0.9 fb⁻¹-equivalent), the SR contains only 99 truth-signal events;
   the fit uncertainty (±0.73% absolute, ~49% relative) is stat-dominated and would
   shrink with the full Belle II dataset, as quantified by the statistical-only
   projection of §5.4 — subject to the systematic floor discussed there.

## 7. Conclusion

Using only the existing pseudo-dataset (no new MC generated), a full cut-and-count and
template-fit measurement of BF(B0→D*⁻τ⁺ν) was carried out, following the D0 mass/Δm
preselection, R2 continuum suppression and m²_miss discriminant of the Belle/BaBar
semileptonic-B analyses. The selection was optimized stage by stage with scans
(R2 < 0.4, e_tag_cm < 5.4 GeV, m²_miss > 1.0 GeV²), reaching a final signal efficiency
of 46.4% and a signal-region purity of 7.7%, cross-checked with three background
control regions (continuum 97.7% pure, D*ℓν-normalization 80.8% pure,
generic-BBbar/wrong-pairing 78.5% pure). The naive truth-subtracted cut-and-count gives
BF = 2.53% ± 0.25%, overshooting the 1.483% generator truth by a factor 1.71, plausibly
because of imperfect event-level (rather than candidate-level) truth tagging (not
quantitatively verified here); the simultaneous e/μ template fit in m²_miss recovers
the generator truth exactly (BF = 1.48% ± 0.73%), demonstrating that shape information
is useful to control this bias, while also being explicitly flagged as a closure test
rather than an independent validation, since no train/test or pull-study check of the
fit has been performed. A statistical-only luminosity projection of the template fit
(§5.4) shows the precision would improve from ±0.73% at the current ~0.9 fb⁻¹-
equivalent dataset to the sub-0.1%-level by 1 ab⁻¹ if only Poisson statistics
mattered; in practice, based on the systematic-uncertainty breakdowns of published
Belle II untagged semileptonic and hadronic-tag R(D*) analyses, the real measurement
would flatten at a systematic floor of roughly 3%, and this — not luminosity — would
set the ultimate precision. A real measurement would replace the truth-based
background subtraction with data control regions, add the systematic uncertainties
listed above, and validate the fit with independent toy studies.


---
## Referee comments (unresolved)

## Checklist Review

**Every section opens with context before tables/plots** — MOSTLY PASS. Sections 1, 2, 3 (and subsections 3.1–3.4), 4, 5.2, 5.4 all lead with explanatory text. However §3.5 and §5.3 drop straight into a table with only a header line, and §6 jumps straight into a numbered list with no framing sentence.

**Every cut names its target background and shows a scan/distribution** — PASS. D0-mass/Δm cuts are tied to fake-D*/combinatoric rejection with referenced distributions; R2, e_tag_cm and m²_miss each have an explicit S/B/figure-of-merit scan table with the targeted background stated.

**Cutflow table with per-stage efficiencies** — PASS. §3.5 gives cumulative and stage efficiencies with uncertainties.

**Background composition and control regions** — PASS. §4 gives a truth-based composition table and three well-motivated inverted-cut control regions with purities and figure references.

**Extraction formula fully defined; fits validated** — FAIL on the validation half. All symbols in the counting formula (§5.1) are defined. However, the template fit is explicitly stated to have no χ²/ndof, pull study, or train/test check, and the μ=1.000 closure is candidly (and correctly) flagged as circular. The note deserves credit for honesty, but per the checklist item as stated, this is not satisfied.

**Figures referenced by file name** — PASS. Consistently done throughout (`plots/presel_*.png`, `plots/fit_*.png`, `plots/cr_*.png`, etc.).

**Limitations/systematics outlook ordered and concrete** — PASS. §6 is a well-ordered, quantitative list, and §5.4's systematic-floor argument cites concrete numbers from two Belle II papers.

**Specific publications cited** — PASS. Waheed et al., PRD 100, 052007 (2019); BaBar, PRD 88, 072012 (2013); Caria et al., PRL 124, 161803 (2020); Adachi et al. [Belle II], PRD 110, 072020 (2024); Belle II, arXiv:2210.13143 — all with author/journal/year.

## CONCERNS

1. **Unvalidated fit used as the headline result.** The template fit that "recovers the generator truth exactly" is the note's central positive result, yet no χ²/ndof, residual/pull plot, or independent train/test split is shown. A referee cannot distinguish genuine shape-based bias correction from an artifact of using the same truth labels to build data and templates. This needs at minimum a toy-MC pull study or an independent-sample cross-check before the 1.00 closure claim is asserted with any confidence.
2. **The 1.71× counting-vs-truth discrepancy is not diagnosed, only speculated about.** The explanation ("event-level vs. candidate-level truth tagging") is plausible but explicitly un-verified. Given this discrepancy is the paper's most physically interesting finding, a quantitative check (e.g., histogram of true_mode==1 candidates split by correct/incorrect D*–lepton pairing) is a reasonable ask rather than an optional extra.
3. **Statistical treatment of N_bkg,truth in the counting method is inconsistent with the fit's uncertainty.** The counting result quotes only √N_sig, ignoring background-subtraction uncertainty entirely, while acknowledging this in prose. Since both numbers are being compared side-by-side in a summary table (§5.3, §7), the asymmetric rigor is a bit misleading to a skimming reader—worth a caveat directly in the table caption, not just body text.
4. **Formatting: §3.5 and §5.3 tables lack any lead-in sentence**, and §6 opens directly on a numbered list with no scene-setting sentence about scope/method of the limitations discussion.
5. **B_sub and N_B0 are stated as "given"** without a pointer to where/how they were computed (presumably from a separate truth-count query) — a one-line provenance note would remove ambiguity.

## VERDICT

REVISE: Add a genuine fit-validation step (pull study, χ²/ndof, or independent train/test template check) before presenting μ=1.000 as a closure success; perform or at least attempt the quantitative check of the mis-pairing hypothesis explaining the 1.71× counting discrepancy; add brief lead-in sentences to §3.5, §5.3 and §6; and note the provenance of N_B0/B_sub inputs.