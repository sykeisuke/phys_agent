# Recipe: search (upper limit or discovery significance)

Result: an expected and observed upper limit on B(mode) at 90% or 95%
CL, or the expected significance for an assumed BF, with the selection
chosen without looking at the signal region.

| Field | Default |
|---|---|
| 1 Goal | expected limit (CLs or Bayesian, stated) at a given luminosity; for MC-only studies the expected limit and the expected significance for the benchmark BF |
| 2 Samples | signal MC at a benchmark BF; all background MC classes; no data, or data with the signal region blinded |
| 3 Selection mode | Mode 2 with the Punzi FoM; Mode 1 only when reproducing a published search |
| 4 Backgrounds | every class modelled by MC or by a sideband; peaking backgrounds identified by truth matching and listed one by one; the sideband-to-signal-region extrapolation shown |
| 5 Extraction | counting in the signal region, or a binned fit of the discriminating variable with the background from the sideband; limit with `pyhf` (CLs); the expected limit from the background-only Asimov dataset |
| 6 Systematics | background normalization and shape (dominant), signal efficiency; placeholders from the published search |
| 7 Validation | the signal region is defined before any yield in it is looked at (blinding documented); expected limit stable against the FoM choice; the published expected limit reproduced within its stated uncertainty when applicable |

## Figure of merit

| Name | Formula | Use |
|---|---|---|
| `punzi` (default) | ε / (a/2 + √B), a = 3 (limit) or 5 (discovery) | independent of the assumed signal BF |
| `s_sqrt_sb` | S/√(S+B) | only when a benchmark BF is given |
| `expected_limit` | the median expected upper limit at each cut value | the most faithful |

Note content: the blinding statement, the sideband figures with the
extrapolation, the peaking-background table, the expected limit (and
its ±1σ band) as the result table.
