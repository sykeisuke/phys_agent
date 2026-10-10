# agent/ — the physics-analysis agent skeleton

This package is the beginning of the AI-agent framework shown in the main
README figure: an LLM drives the local pipeline (EvtGen → fast sim →
ntuples → plots) through typed tools, with a **student-approval gate**
between Plan and Execute.

## Setup

```bash
source scripts/env.sh
pip install anthropic
export ANTHROPIC_API_KEY=...   # or `ant auth login`
```

## Run

```bash
python -m agent "Compare m2_miss between B0 -> D* tau nu and B0 -> D* mu nu with 5000 events each"
```

The agent will print a plan and wait for `y/N` before touching the pipeline.

### Review modes

The approval gate between Plan and Execute has two modes
(`--review human|ai`, default `human`):

- **human** — the student reads the plan and answers y/N; rejection
  feedback goes back to the agent as a tool result.
- **ai** — a second LLM instance reviews the plan against a fixed checklist
  (samples/seeds stated, cut & count, follows a named existing analysis,
  deliverables defined) and replies APPROVE / REVISE. Start every new
  workflow in human mode; switch to ai review once the workflow is
  established and trusted.

## Structure

| File | Role |
|---|---|
| `runner.py` | agent loop (Anthropic tool runner), system prompt with the Plan→Execute→Report contract and the analysis policy |
| `tools.py` | typed tools: generation (`list_decay_modes`, `generate_mc`, `generate_continuum`, `make_ntuple`), ntuples (`list_branches`, `query_ntuple`, `plot_variable`, `plot_stacked`, `scan_cut`, `fit_templates`), systematics (`apply_systematics`), notes |
| `__main__.py` | CLI entry point |
| `../systematics/*.json` | published systematic-uncertainty tables read by `apply_systematics` (e.g. Belle II arXiv:2206.05946 Table I) |
| `../tests/test_offline.py` | offline tests, no API calls: `python tests/test_offline.py` |

Design choices worth knowing:

- The SDK **tool runner** supplies the agentic loop; we only define tools.
- The approval gate is *inside* the `request_approval` tool — the model
  cannot skip it because the system prompt forbids running other tools
  first, and the student's rejection text is fed back as the tool result.
- Tool file access is confined to `generation/dec/`, `data/`, `plots/`.
  Ntuples may sit in plain subdirectories of `data/`
  (e.g. `data/kekcc/` for the Belle II full-MC samples copied from KEKCC).
- `query_ntuple` / `plot_variable` evaluate cut strings with numpy in a
  restricted namespace.
- Both ntuple formats are read: the fast-sim tree `events` and the basf2
  `VariablesToNtuple` tree `ntuple` (basf2 variable names such as `Mbc`,
  `deltaE`, `B_rank`, `isSignal`; use `list_branches` to see them).
- Only text crosses the network: the task, the tool definitions and the
  short strings the tools return. Plot tools return a file path, never an
  image; ntuples never leave the machine.
- Cost: the agent loop uses **prompt caching**, so the system prompt, tool
  definitions and history resent each turn are billed as cache reads. The
  end-of-run `[usage]` line counts agent turns *and* reviewer calls,
  including cache writes and reads and web searches, at list prices.
- Systematics: `apply_systematics` attaches the published table's entries
  (PID, K_S, pi0, tracking, N_BB, ...) to a result. Entries marked
  `mc_evaluable` (MC statistics, cross feed, PDF shape) can be replaced by
  values the agent evaluates itself. Entries marked `placeholder` (the
  published MVA selection) are flagged in the output.

## Student roadmap (hardening the skeleton)

1. Structured reports: make the final report a typed object
   (`output_config.format`) and save it under `docs/notes/`.
1. Luminosity weighting in `scan_cut`: the FoM currently uses raw MC
   counts; weight S and B by cross section × BF × luminosity / N_generated
   so working points are optimized for a real dataset size.
2. Add a `measure_bf` tool wrapping `analysis/measure_bf_dsttaunu.py`
   generalized to any mode.
3. Cost/limit guards: cap total generated events per session; log every
   tool call to a session file.
4. Conversation persistence: save/restore `messages` so an analysis can
   continue across sessions.
5. Evaluate the agent: build a small eval set of tasks with known answers
   (e.g. the closure test) and track the success rate as the prompt evolves.
