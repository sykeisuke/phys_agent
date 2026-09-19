# Analysis notes

Two kinds of notes live here, and the distinction matters:

- **Agent-written notes** are produced end to end by the framework
  (Plan -> review -> Execute -> Report -> Note): every number comes from a
  tool result of the session, and in AI-review mode the note is refereed
  before it is accepted. These are the framework's actual deliverables.
- **Hand-written reference notes** were authored by a human (with LLM
  assistance) as the quality standard the agent-written notes are measured
  against.

| File | Author | Content |
|---|---|---|
| [dsttaunu_note_agent.pdf](dsttaunu_note_agent.pdf) ([md](dsttaunu_note_agent.md)) | **agent-written** | B(B0 -> D*taunu) on the luminosity-matched pseudo-dataset: per-variable selection with stacked figures and scans, cutflow, background composition with control regions, counting + simultaneous e/mu pyhf fit, statistical-only sensitivity projection with a literature-sourced systematic floor |
| [dsttaunu_bf_note.pdf](dsttaunu_bf_note.pdf) | hand-written reference | same measurement, human-written version kept as the quality benchmark (adds toy validation) |
| [kstll_note_agent.pdf](kstll_note_agent.pdf) ([md](kstll_note_agent.md)) | **agent-written** | B0 -> K*0 l+l- sensitivity: K*/Mbc/deltaE selection with scans, per-flavor charmonium vetoes, cutflow, yields at 1/ab; citations retrieved by the agent via web search |
| [kstll_sensitivity_note.pdf](kstll_sensitivity_note.pdf) | hand-written reference | earlier human-written version of the K*ll study, kept for comparison |

All figures referenced by the agent notes are bundled under `figures/`,
and the PDFs are rendered from the Markdown with `analysis/render_note.py`
(a mechanical publication step; the text is the agent's, unedited).
All numbers are reproducible from the fixed seeds listed inside each note.
