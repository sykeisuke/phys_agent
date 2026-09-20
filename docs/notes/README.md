# Analysis notes

**The deliverables are the agent-written PDFs in this directory** —
if you only read two files, read the D*taunu note and the K*ll v2 note:

| Note | Content |
|---|---|
| [dsttaunu_note_agent.pdf](dsttaunu_note_agent.pdf) | B(B0 -> D*taunu) on the luminosity-matched pseudo-dataset: per-variable selection with stacked figures and scans, cutflow, background composition with control regions, counting + simultaneous e/mu pyhf fit, statistical-only sensitivity projection with a literature-sourced systematic floor |
| [kstll_note_agent_v2.pdf](kstll_note_agent_v2.pdf) | B0 -> K*0 l+l- sensitivity **v2**: adds combinatorial generic-BBbar and continuum background (new combinatorial candidate builder), R2 continuum suppression, psi(2S) veto, and an Mbc template fit with luminosity projection; **typeset and compiled by the agent itself** (first run of the TYPESET stage — [md](kstll_note_agent_v2.md), [tex](kstll_note_agent_v2.tex)) |

These notes were produced end to end by the framework
(Plan -> review -> Execute -> Report -> Note): every number comes from a
tool result of the session, and in AI-review mode the note is refereed
before it is accepted. The agent's accepted Markdown source of each note
sits next to its PDF ([dsttaunu](dsttaunu_note_agent.md),
[kstll v2](kstll_note_agent_v2.md)); all referenced figures are bundled under
`figures/`, and all numbers are reproducible from the fixed seeds listed
inside each note.

**Provenance of the PDFs.** Both are typeset LaTeX versions of the
agent's accepted Markdown notes (the `.tex` sources live next to the
PDFs); the text and every number are the agent's, unedited. The K*ll v2
LaTeX was produced and compiled by the agent itself through the
workflow's TYPESET stage (`save_note_latex`, which runs after the
Markdown note passes the AI referee); the D*taunu LaTeX was typeset by
hand from the agent's Markdown before that stage existed. The only
mechanical edits on publication are figure-path rewrites and, for v2, a
re-render of the stacked figures with merged sample labels.
`analysis/render_note.py` remains as the quick mechanical
Markdown-to-PDF fallback.
