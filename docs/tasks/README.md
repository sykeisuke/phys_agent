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
