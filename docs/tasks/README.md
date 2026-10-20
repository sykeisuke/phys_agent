# Task archive

The task is the **first user message** of an agent run: `python -m agent
"<task>"` puts the string verbatim after the fixed system prompt in
`agent/runner.py`, and everything else in the run (tool calls, reviewer
verdicts) follows from it. The wording of the task decides the result
and the cost, so every task text that was actually run is kept here,
unedited, with the outcome. Reuse them as starting points.

Run a task file with the launcher (model is passed explicitly, the
`[usage]` line is printed at the end):

```bash
scripts/run_task.sh docs/tasks/2026-10-14_kstll_frozen_cutflow.txt
```

| Date | Task file | Materials | Outcome |
|---|---|---|---|
| 2026-10-12 | [kstll_official_mc_neutral](2026-10-12_kstll_official_mc_neutral.txt) | Belle II official MC ntuples (INTERNAL) | Free selection on the neutral channel; note accepted. The agent re-derived cuts, so retention numbers drifted between runs — motivated the frozen-selection task. 31 turns, killed once by a wall-clock limit (scan_cut misused as a multi-file counter). |
| 2026-10-19 | [kstll_frozen_cutflow_rerun](2026-10-19_kstll_frozen_cutflow_rerun.txt) | same | The 10-15 task plus one sentence fixing the box-stage counting (best candidate chosen without a truth condition; box and truth via post_selection). Run 2026-10-20: box stage now exact in both B+ channels (1010, 1513), but both B0 channels +0.9/+1.0 pp high because the selection file's pion-ID expression `(Kstr_decayModeID == 1) \| ...` bypassed the cut in the neutral channel, where decayModeID is always 1 (a bug in the YAML, applied faithfully by the agent). YAML fixed with per-channel expressions and verified offline (2241/3302/1010/1513). 32 turns, 112 tool calls, $4.69 (two referee revisions, five plot_stacked errors from passing a ratio expression as `variable`). To be rerun. |
| 2026-10-15 | [kstll_frozen_cutflow_recipe](2026-10-15_kstll_frozen_cutflow_recipe.txt) | same | Recipe form of the 2026-10-14 task (4 lines instead of 5,000 characters): recipe, selection file, samples; the rest from the recipe defaults and `data/kekcc/CONTEXT.md`. Plan approved at the first review; stages 1-4 identical to the reference, but the box stage came out +0.5 to +1.6 pp high because the agent put isSignal == 1 into the selection before choosing the best candidate (counts events with any truth-matched candidate). The note wrongly blamed tie-breaking/B_rank. 30 turns, 85 tool calls, $3.01. |
| 2026-10-14 | [kstll_frozen_cutflow](2026-10-14_kstll_frozen_cutflow.txt) | Belle II official MC ntuples (INTERNAL) | Frozen reference selection (ntupleProduction/ntuple_plots.py). Cutflow reproduced the reference exactly in all 4 channels. 28 turns, 113 tool calls, $2.19 (Sonnet 5, caching). Note had branch names in the body and an oversized table — led to the register rule in `docs/note_template.md`. |

Earlier runs (D*taunu note, K*ll v1/v2 on fast-simulation samples) were
started from task strings typed on the command line that were not kept;
their content can be read off the Analysis provenance sections of the
notes under `docs/notes/`.

Lessons for writing a task (all learned the expensive way):

- Name the tools to use for each quantity and say which NOT to use
  (e.g. `query_ntuple` with `root_files`, not `scan_cut`, for counting).
- Give a tool-call budget and say "no scans, no re-optimisation" when
  the selection is frozen.
- State the normalisation (generated events per file and channel) or
  say explicitly that it is unknown and must not be guessed.
- Say which header the note must carry (public materials or INTERNAL).
- Keep single-valued arguments single (a selection is one string, not a
  list).
