# Recipe: cutflow reproduction (framework validation)

Result: a cut-by-cut comparison of the framework with a human reference
script on the same samples. Nothing is optimized; the deliverable is the
agreement.

| Field | Default |
|---|---|
| 1 Goal | reproduce the reference selection and report, per stage and channel, the counts and efficiencies next to the reference values |
| 2 Samples | exactly the files the reference ran on (from `CONTEXT.md`); all copies summed |
| 3 Selection mode | Mode 1, from a reference selection file under `docs/selections/`; cuts applied in the file's order; the best-candidate rule and the signal box as the file states them |
| 4 Backgrounds | the reference's generic samples through the same chain; no estimation beyond counting |
| 5 Extraction | none ("Not applicable" in the note); counts only |
| 6 Systematics | none; efficiency table with binomial uncertainties |
| 7 Validation | every stage within the stated tolerance (default: identical counts; otherwise within 1% relative); each remaining difference explained (best-candidate timing, truth-matching definition, release) |

Counting conventions are taken from the reference and written in the
note: events vs candidates at each stage; best candidate chosen among
the candidates passing the cuts (not a stored rank computed before them).
The best candidate is chosen among all candidates passing the cuts,
without any truth condition in the selection; the signal box and the
truth match are applied afterwards to that one chosen candidate
(`post_selection`). A truth condition placed before the choice counts
events with any truth-matched candidate and overestimates the last stage.

Note content: the cutflow table with reference values side by side, the
distributions of each cut variable with the cut lines, the control
sample through the same chain, and in the discussion what the
comparison can and cannot establish.
