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
| `tools.py` | typed tools: `list_decay_modes`, `generate_mc`, `make_ntuple`, `query_ntuple`, `plot_variable` |
| `__main__.py` | CLI entry point |

Design choices worth knowing:

- The SDK **tool runner** supplies the agentic loop; we only define tools.
- The approval gate is *inside* the `request_approval` tool — the model
  cannot skip it because the system prompt forbids running other tools
  first, and the student's rejection text is fed back as the tool result.
- Tool file access is confined to `generation/dec/`, `data/`, `plots/`.
- `query_ntuple` / `plot_variable` evaluate cut strings with numpy in a
  restricted namespace.

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
