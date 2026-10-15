# Recipe: ratio of branching fractions (R(D*), R(D), R(K*), lepton-universality ratios)

Result: R = B(numerator mode) / B(denominator mode), with the
uncertainties that do not cancel, per channel and combined.

| Field | Default |
|---|---|
| 1 Goal | R = (N_num/ε_num) / (N_den/ε_den); the two modes share as much of the selection as possible so that tracking, PID of common particles, N_BB̄ and sub-decay BFs cancel |
| 2 Samples | from `CONTEXT.md`: numerator and denominator signal MC, the backgrounds of each (for R(D*): D**ℓν, misreconstructed D*, continuum), plus the tagging samples when a tag is used |
| 3 Selection mode | Mode 1 when a reference exists; Mode 2 optimizes only the cuts that separate numerator from denominator (e.g. m²_miss, lepton momentum), with the common selection frozen |
| 4 Backgrounds | the modes that feed from one category into the other are listed explicitly with their MC; cross-feed matrix shown; a control region per dominant background (D**ℓν enriched, sideband) |
| 5 Extraction | simultaneous fit of numerator and denominator in the discriminating variable(s) (m²_miss, E_ℓ, or the 2D plane) with cross-feed templates; the ratio is a fit parameter; Asimov closure then pseudo-data |
| 6 Systematics | only the non-cancelling ones: form factors of signal and backgrounds, D** composition, MC statistics of templates, lepton-ID differences between channels |
| 7 Validation | cross-feed and efficiencies consistent with the published analysis; the fitted R unbiased on pseudo-data; the published R inside the reported interval when the published yields are injected |

Figure of merit for Mode 2: expected uncertainty on R from the Asimov
fit (`asimov`); `s_sqrt_sb` only for a first scan.

Note content: the cross-feed matrix, the fit projections per channel,
the efficiency ratio ε_num/ε_den with its uncertainty, the systematics
table marked "cancels / does not cancel".
