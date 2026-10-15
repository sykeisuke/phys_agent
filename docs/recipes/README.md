# Analysis recipes

A recipe is the generalized strategy for one *kind* of measurement. It
turns a one-line task ("measure the branching fraction of B → K*ℓℓ")
into a complete specification by listing every decision the analysis
needs, with a default for each. The agent reads the recipe at the PLAN
stage, fills the fields from the task text, the sample context and the
reference digest, and presents the filled specification as its plan.
Only fields the task overrides need to be written in the task.

| Recipe | Result | Typical modes |
|---|---|---|
| [bf_measurement.md](bf_measurement.md) | a branching fraction with uncertainties | B → K*ℓℓ, B → D*ℓν |
| [ratio_measurement.md](ratio_measurement.md) | a ratio of branching fractions | R(D*), R(D), R(K*) |
| [search.md](search.md) | an upper limit or discovery significance | B → K*νν̄, LFV modes |
| [cutflow_reproduction.md](cutflow_reproduction.md) | a cut-by-cut comparison with a human reference | validation of the framework |

## The specification (common to all recipes)

Every recipe fills the same seven fields. Defaults are per recipe.

1. **Goal** — decay mode (B0 convention), the quantity, the result form.
2. **Samples** — where they are (directory under `data/`), what each is
   (signal, normalization, control, generic BB̄, continuum), events
   generated per file and per channel, luminosity weights. Taken from
   the sample context file (below); never guessed. If a weight or a
   generated count is missing, the note says so and reports raw counts.
3. **Selection mode** —
   *Mode 1, follow the reference*: every cut comes from a reference
   selection file (`docs/selections/*.yaml`) or the reference digest;
   nothing is re-optimized; the deliverable is the agreement with the
   reference.
   *Mode 2, optimize*: the agent chooses the cut values by scans with a
   stated figure of merit; each cut is compared with the published value
   and justified; the scans are shown.
4. **Background strategy** — for each background class: modelled by MC
   (which sample), constrained by a control region (which), or not
   modelled (stated as a limitation). Vetoes and continuum suppression
   belong here.
5. **Extraction** — counting with the formula written out, or a template
   fit (variable, binning, channels, templates, constraints) with its
   validation (closure, Asimov, toys).
6. **Systematics** — which sources, from where (published value /
   evaluated here / placeholder / not evaluated).
7. **Validation criterion** — what "done" means for this run, e.g.
   "cutflow within 1% of the reference at every stage" or "FoM scans
   shown and the chosen cuts within the published windows".

## Sample context file

Each sample directory may carry a `CONTEXT.md` next to the ntuples
(`data/<dir>/CONTEXT.md`). `list_samples` returns it together with the
file listing, so the facts travel with the samples and are never typed
into a task. Suggested content:

```
# Samples in data/kekcc  (INTERNAL — Belle II official MC)
release / global tags / beam background:
events generated per file: 5000; per lepton channel: 2500
samples: <name>: <process>, role (signal/control/generic), weight or "unknown"
branch naming: e files e1_B0_*, mu files mu1_B0_*; charged channel B_* ...
truth matching: isSignal == 1
multiple candidates: yes; event id __event__/__run__; B_rank computed before cuts
known caveats: ...
```

Directories of official or private material are git-ignored, so the
context file can state facts that must not be published. The note's
materials header (public / INTERNAL) follows the context file.

## Reference selection file (Mode 1)

A YAML list of cuts in the order they are applied, with the variables
written as ntuple expressions and the physics name used in the note:

```yaml
reference: ntupleProduction/ntuple_plots.py   # what is reproduced
paper: arXiv:2206.05946
channels: {B0_ee: "...", B0_mumu: "...", ...}  # per-channel branch substitutions
cuts:
  - name: K* mass window
    expr: "(Kstr_M > 0.796) & (Kstr_M < 0.996)"
    targets: combinatorial Kπ
best_candidate: "abs(deltaE)"      # lowest value wins, after the cuts
signal_box: "(Mbc > 5.27) & (Mbc < 5.29) & (abs(deltaE) < 0.05)"
```

See [`docs/selections/kstll_reference_ntuple_plots.yaml`](../selections/kstll_reference_ntuple_plots.yaml).

## Writing a task

The task names the recipe and the goal, plus only the fields that
differ from the recipe defaults:

```
Recipe: bf_measurement. Measure B(B0 -> K*0 l+ l-) on the samples in
data/kekcc. Selection mode 1 with docs/selections/kstll_reference_ntuple_plots.yaml.
```

Everything else (tool usage, call budgets, note structure) is framework
knowledge and is never written in a task.
