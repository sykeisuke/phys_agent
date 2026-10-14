# Analysis note template

Every analysis note written by the agent follows the section skeleton of a
Belle II physics paper (modelled on arXiv:2206.05946), extended by the
sections that only make sense for an agent-produced study. The top-level
sections are FIXED — same titles, same order, numbered 1–11. A section
that does not apply to a given study is kept with a one-sentence
statement of why ("Not applicable: ..."); it is never omitted. Subsections
inside a section are free.

Unlike a journal paper, the note must be self-explanatory for a referee
who has not seen the tool outputs: every section from 3 to 8 contains at
least one table or one figure (Markdown image embed with a full
descriptive caption as the alt text), and every number in the note comes
from a tool result of the session.

## Abstract (before section 1)
A self-contained quantitative summary: samples, selection, the result
with its uncertainty, the main limitation.

## 1 Introduction
Physics motivation; the published analyses whose strategy is followed
(cited by authors, journal, arXiv); what this study does and explicitly
does not do (e.g. MC-only, no systematics).

## 2 Detector model and samples
Required: a samples table (process, generator/model or MC campaign and
software release, events generated, seeds or production tag, luminosity
weight and how it was derived). Fast simulation: the detector parameters
used. Official samples: campaign, release, global tags. Data: dataset,
luminosity, run range. State whether multiple candidates per event occur.

## 3 Event selection and reconstruction
Required: the candidate definition; a table of ALL selection criteria
(variable, cut value, the background each targets, source: published /
scanned / frozen reference); one stacked figure per discriminating
variable with the cut indicated; the best-candidate rule and the
candidate multiplicity; a cutflow table with per-stage and cumulative
efficiencies (binomial uncertainties), per channel.

## 4 Background estimation and suppression
Required: a composition table of the signal region (truth-split or
per sample, raw counts and weighted yields with MC-statistics
uncertainties); for each control region a table row (selection, yield,
purity) and a figure; the vetoes (e.g. charmonium) shown on the relevant
distribution. State what is not modelled (continuum, specific modes).

## 5 Signal yield extraction
Required: the method stated explicitly — the counting formula with every
input defined, and/or the fit model (fit variable, binning, channels,
signal/background templates, constraints) — a post-fit figure per
channel, and a results table (yields or signal strength per channel and
combined, with uncertainties). State the validation performed (closure,
toys, pulls) or its absence.

## 6 Efficiency corrections and systematic uncertainties
Required: an efficiency table (per channel; what it is relative to); a
systematics table with a source column for every entry (published value
/ evaluated here / placeholder / not evaluated). If no systematics are
evaluated, say so and give the expected dominant sources with magnitudes
from the published analyses.

## 7 Results and summary
Required: the final result table (central values, statistical and
systematic uncertainties, per channel and combined); a comparison table
with the published or reference values where any like-for-like
comparison exists (and a clear statement when none does); luminosity
projection figure if performed.

## 8 Discussion
Limitations ordered by their impact on the result, each with the concrete
step that would remove it; what a real measurement would add.

## 9 Analysis provenance
Agent-specific, always present: the materials statement (public-only
materials, or INTERNAL — Belle II official samples/data used); the tools
called for each key step with the arguments that fix the result
(selections, binning, weights, seeds); the reference scripts or notes
compared against; the review outcomes (plan revisions, referee verdict);
how to reproduce the numbers from the repository.

## 10 References
Numbered list; every citation in the text appears here (authors,
journal/arXiv, year).

## Appendix: referee comments (framework-appended)
Unresolved referee comments are appended by the framework after section
10; do not write this section yourself.
