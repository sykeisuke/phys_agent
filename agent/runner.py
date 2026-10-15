"""The agent loop: Plan -> (student approval) -> Execute -> Report.

Uses the Anthropic SDK tool runner, which drives the model -> tool ->
model cycle automatically; the human-in-the-loop gate lives inside the
request_approval tool, mirroring the workflow figure in the README.
"""
from __future__ import annotations

import re

import anthropic
from anthropic import beta_tool

from .tools import (ANALYSIS_TOOLS, NOTES_DIR, _safe_name,
                    _check_note_structure)

MODEL = "claude-sonnet-5"

# List prices in USD per million tokens: (input, output, cache read).
# Cache writes (5-minute TTL) cost 1.25x input; web search is $10 per 1k.
PRICES = {
    "claude-fable-5-1": (10, 50, 0.25),
    "claude-opus-5-5": (4, 20, 0.20),
    "claude-opus-5": (5, 25, 0.50),
    "claude-sonnet-5-5": (2, 10, 0.20),
    "claude-sonnet-5": (2, 10, 0.20),
    "claude-haiku-4-5": (1, 5, 0.10),
}
WEB_SEARCH_USD = 0.01


class Usage:
    """Token and cost accounting for one run: agent turns AND reviewer
    calls, including prompt-cache writes and reads, priced per model."""

    def __init__(self) -> None:
        self.by_model: dict[str, dict[str, int]] = {}

    def add(self, model: str, u) -> None:
        if u is None:
            return
        d = self.by_model.setdefault(
            model, {"calls": 0, "inp": 0, "out": 0, "cw": 0, "cr": 0,
                    "web": 0})
        d["calls"] += 1
        d["inp"] += u.input_tokens or 0
        d["out"] += u.output_tokens or 0
        d["cw"] += getattr(u, "cache_creation_input_tokens", 0) or 0
        d["cr"] += getattr(u, "cache_read_input_tokens", 0) or 0
        stu = getattr(u, "server_tool_use", None)
        d["web"] += (getattr(stu, "web_search_requests", 0) or 0) if stu else 0

    def cost(self) -> float:
        total = 0.0
        for model, d in self.by_model.items():
            pin, pout, pcr = PRICES.get(model, (5, 25, 0.50))
            total += (d["inp"] * pin + d["cw"] * 1.25 * pin
                      + d["cr"] * pcr + d["out"] * pout) / 1e6
            total += d["web"] * WEB_SEARCH_USD
        return total

    def report(self, turns: int) -> str:
        lines = [f"[usage] {turns} agent turns, ~${self.cost():.2f} at list "
                 "prices (agent + reviewer calls, cache included)"]
        for model, d in self.by_model.items():
            lines.append(
                f"  {model}: {d['calls']} calls; tokens in {d['inp']:,}, "
                f"cache write {d['cw']:,}, cache read {d['cr']:,}, "
                f"out {d['out']:,}; {d['web']} web searches")
        return "\n".join(lines)

SYSTEM_PROMPT = """\
You are a physics-analysis agent for a Belle II-like analysis framework:
it can generate its own fast-simulation ntuples (EvtGen -> fast detector
simulation -> ROOT) and it can analyse ntuples produced elsewhere (e.g.
official basf2 ntuples copied under data/). You work together with a
student. Follow this loop strictly:

0. DISCOVER (ntuples you did not produce): call list_samples, then
   inspect_ntuple on one file per sample to learn the tree, the branch
   names (truth flags such as isSignal/mcErrors/mcPDG, kinematics,
   candidate rank, event identifiers) and the candidates-per-event
   multiplicity; electron and muon files may carry differently named
   lepton branches. Decide and state how multiple candidates per event
   are handled (e.g. a best-candidate rank cut). Sample normalisations
   (generated event counts, luminosity weights) that are not given to
   you must be requested from the student, never guessed; without them
   report raw counts and efficiencies only.
1. PLAN: call read_recipe (the task names a recipe: bf_measurement,
   ratio_measurement, search, cutflow_reproduction; if it does not,
   read the index and pick the one that fits the goal) and
   read_references; when the mode at hand is not covered there (or you
   need concrete numbers such as measured branching fractions or
   published selection windows), use web_search to consult the
   literature (arXiv, journals, PDG). Then fill the recipe's seven
   fields (goal; samples with counts and weights from the sample
   context, never guessed; selection mode 1 with read_selection or
   mode 2 with the figure of merit; background strategy per class;
   extraction; systematics; validation criterion), using the recipe
   defaults for everything the task does not override, and submit the
   filled specification as the plan with the request_approval tool.
   Do not generate MC or run any other tool before approval.
2. EXECUTE: after approval, run the pipeline tools. Fix seeds for
   reproducibility. If a tool fails, diagnose and retry with a fix.
3. REPORT: give a short Markdown report in the conversation: what was
   done, the numbers in a table, which plots were written.
4. NOTE: for a full analysis (one that produced a physics result, not a
   quick check), call read_note_template and write the complete analysis
   note with save_note, following the template EXACTLY: Abstract, then
   the ten fixed sections (1 Introduction, 2 Detector model and samples,
   3 Event selection and reconstruction, 4 Background estimation and
   suppression, 5 Signal yield extraction, 6 Efficiency corrections and
   systematic uncertainties, 7 Results and summary, 8 Discussion,
   9 Analysis provenance, 10 References). A section that does not apply
   is kept with one sentence saying why. Sections 2-7 each contain at
   least one table or figure; the template lists what each must contain
   (samples table, selection table, cutflow, composition and control
   regions, extraction method with post-fit figures, efficiency and
   systematics tables with a source column, result and comparison
   tables). Quality bar (a physicist should be able to referee it):
   motivate every cut by naming the background it removes and show the
   scan or distribution that fixed its value; embed every plot you
   produced with Markdown image syntax at the point where it is
   discussed, with a full descriptive caption as the alt text — what is
   shown, after which selection stage, and what the reader should notice
   (![The m2miss distribution after the D* windows, ...](plots/<name>.png));
   a bare filename is not acceptable; state what is NOT modeled and how a
   real analysis would handle it; cite the published analyses you
   followed. Every number in the note must come from a tool result of
   this session. State precisely which samples were used: if any Belle II
   official MC or data entered the analysis, the note must carry the
   header "INTERNAL — Belle II official samples used; not for public
   release" instead of the public-materials disclaimer, and must not
   claim to use only public materials. Register: the Abstract and
   sections 1-8 read like a journal paper — decays, physics symbols
   (M_bc, Delta E, m(ll)), "signal MC", "truth-matched"; no branch
   names, file names, paths, tool names or backtick code spans, and no
   narration of the session. Every such technical detail goes to
   section 9 (Analysis provenance), which maps the physics names to the
   exact branches, files, tool calls and arguments. Tables: short row
   labels, at most about six columns, definitions in the caption.
   save_note rejects a note whose structure or register deviates from
   the template; fix it and save again.
5. TYPESET: once save_note accepts the Markdown note, produce the final
   typeset version with save_note_latex: a complete LaTeX document with
   the title block (author lines, version/date, the public-materials
   disclaimer or the INTERNAL header, whichever applies), the abstract, a table of contents, booktabs tables,
   numbered figure floats with descriptive captions, and a References
   section (thebibliography) collecting every publication cited in the
   text, with \\cite commands at the in-text mentions. The LaTeX content
   must match the accepted Markdown note exactly (same ten sections in
   the same order). Every table must fit the text width: \\small or
   \\footnotesize for tables, short row labels with abbreviations
   defined in the caption, \\resizebox{\\textwidth}{!}{...} or
   tabularx for wide tables, p{} columns for long text. If compilation
   fails, or overfull boxes are reported, fix the LaTeX and call
   save_note_latex again (once for overfull boxes).

Analysis policy:
- Before designing a selection, check whether a published analysis of the
  same or a similar mode exists (Belle, Belle II, BaBar) and follow its
  choice of kinematic variables; state which analysis you are following.
- Prefer a simple cut & count over multivariate methods (NN/BDT): in this
  framework systematic uncertainties of a multivariate selection cannot be
  evaluated reliably. Use a multivariate method only if the student
  explicitly asks for one. Optimize cuts with the scan_cut tool, one
  variable at a time.
- Aim for fast turnaround with reasonable quality, not perfection: modest
  sample sizes and simple selections first, refinements only when the
  student asks.

Physics conventions (from CLAUDE.md): units are GeV; m2_miss in GeV^2;
decay modes in the B0 convention; explanations at the undergraduate
level, intuition before equations.
"""


REVIEWER_PROMPT = """\
You are a strict but constructive physics-analysis reviewer at a B factory.
You are shown an analysis PLAN produced by another agent. Write a short
structured review:

CHECKLIST (one line each, PASS/FAIL + one-sentence justification):
- recipe: the plan names its recipe and fills all seven fields (goal,
  samples, selection mode, background strategy, extraction, systematics,
  validation criterion); no "to be decided" fields?
- samples: counts, weights and seeds taken from the sample context or
  stated as unknown (nothing guessed); generation <= 2M events?
- selection: mode 1 (reference file named) or mode 2 (figure of merit
  named); cut & count with named variables (no NN/BDT)?
- precedent: does it say which published analysis the variables follow?
- deliverables: efficiencies, yields, plots and the validation criterion
  specified?
CONCERNS: anything risky or missing (or "none").
VERDICT: exactly one final line, either "APPROVE" or
"REVISE: <specific, actionable feedback>".
"""


def make_approval_tool(review: str, client, model: str,
                       usage: Usage | None = None):
    """Build the approval gate for the chosen review mode.

    'human' (default): the student answers y/N on the terminal.
    'ai'  : a second LLM instance reviews the plan against the checklist —
            use once the workflow is established and trusted.
    """
    state = {"revisions": 0}
    usage = usage or Usage()

    @beta_tool
    def request_approval(plan: str) -> str:
        """Present the analysis plan for review and wait for approval.
        Must be called once, before any MC generation or analysis tool.

        Args:
            plan: the plan as a short Markdown bullet list.
        """
        print("\n=== PROPOSED PLAN ===\n" + plan + "\n=====================")
        if review == "ai":
            verdict = client.messages.create(
                model=model, max_tokens=8192, system=REVIEWER_PROMPT,
                messages=[{"role": "user", "content": plan}])
            usage.add(getattr(verdict, "model", model), verdict.usage)
            text = "".join(b.text for b in verdict.content
                           if b.type == "text").strip()
            if not text:  # e.g. the reviewer spent the budget thinking
                return ("approved (reviewer returned no verdict text) — "
                        "proceed")
            print(f"[AI reviewer]\n{text}")
            # append the full review to a session log
            from datetime import datetime
            from .tools import NOTES_DIR
            NOTES_DIR.mkdir(exist_ok=True)
            with open(NOTES_DIR / "review_log.md", "a") as f:
                f.write(f"\n## Review {datetime.now():%Y-%m-%d %H:%M}\n\n"
                        f"### Plan\n{plan}\n\n### Review\n{text}\n")
            last = text.strip().splitlines()[-1].upper()
            if "APPROVE" in last and "REVISE" not in last:
                return "approved by the AI reviewer — proceed"
            state["revisions"] += 1
            if state["revisions"] >= 3:
                # stop the reviewer/author deadlock: approve with concerns
                return ("approved after 3 revisions — proceed now and "
                        "address the remaining reviewer concerns inside "
                        f"the analysis and the note itself:\n{text}")
            return f"rejected — revise the plan. Reviewer feedback: {text}"
        answer = input("Approve this plan? [y/N] ").strip().lower()
        if answer in ("y", "yes"):
            return "approved — proceed"
        reason = input("Feedback for the agent: ").strip()
        return f"rejected — revise the plan. Student feedback: {reason}"

    return request_approval


NOTE_REVIEWER_PROMPT = """\
You are refereeing a physics ANALYSIS NOTE (Markdown). Judge it as a peer
reviewer would. Checklist (PASS/FAIL + one sentence each):
- structure: Abstract followed by exactly the ten template sections in
  order (Introduction; Detector model and samples; Event selection and
  reconstruction; Background estimation and suppression; Signal yield
  extraction; Efficiency corrections and systematic uncertainties;
  Results and summary; Discussion; Analysis provenance; References),
  sections 2-7 each with at least one table or figure, and no section
  silently omitted (a non-applicable one says so in one sentence);
- register: Abstract and sections 1-8 read like a journal paper (decays,
  physics symbols, "signal MC"); no branch/file/tool names, code spans or
  session narration there — those belong in section 9 Analysis
  provenance, which must map physics names to branches/files/tool calls;
- tables fit a page: short labels, few columns, definitions in captions;
- every section opens with a short paragraph of context before tables/plots;
- every cut names the background it targets and shows the scan or
  distribution that fixed its value;
- a cutflow table with per-stage efficiencies exists;
- background composition and control regions (or the data strategy) given;
- the extraction formula has every input defined; fits are validated;
- figures are referenced by file name where claims rely on them;
- limitations and a systematics outlook are ordered and concrete;
- specific publications are cited (authors, journal).
CONCERNS: anything a referee would bounce.
VERDICT: one final line, "APPROVE" or "REVISE: <actionable feedback>".
"""


def make_note_tool(review: str, client, model: str,
                   usage: Usage | None = None):
    """save_note, with an AI referee in front of it when review == 'ai'."""
    state = {"revisions": 0}
    usage = usage or Usage()

    @beta_tool
    def save_note(name: str, content: str) -> str:
        """Save the final analysis note as a Markdown file under notes/.
        Call this once, as the last step of an analysis, with the full note.
        In AI-review mode the note is refereed first and may be returned
        for revision instead of being saved.

        Args:
            name: file name, e.g. "dsttaunu_bf_note.md".
            content: the complete note in Markdown.
        """
        # web_search results carry (cite index="..."> markup; drop the tags
        content = re.sub(r"\(?<?cite index=\"[^\"]*\">", "", content)
        content = content.replace("</cite>", "")
        # mechanical template check first (free; does not count as a
        # referee revision round)
        problems = _check_note_structure(content)
        if problems:
            return ("note REJECTED — it does not follow docs/note_template.md "
                    "(call read_note_template): " + "; ".join(problems)
                    + ". Fix the structure and call save_note again.")
        if review == "ai":
            verdict = client.messages.create(
                model=model, max_tokens=8192, system=NOTE_REVIEWER_PROMPT,
                messages=[{"role": "user", "content": content}])
            usage.add(getattr(verdict, "model", model), verdict.usage)
            text = "".join(b.text for b in verdict.content
                           if b.type == "text").strip()
            if not text:
                text = "APPROVE"  # no verdict text: do not block the save
            print(f"[AI note referee]\n{text}")
            from datetime import datetime
            NOTES_DIR.mkdir(exist_ok=True)
            with open(NOTES_DIR / "review_log.md", "a") as f:
                f.write(f"\n## Note review {datetime.now():%Y-%m-%d %H:%M} "
                        f"({name})\n\n{text}\n")
            last = text.strip().splitlines()[-1].upper()
            approved = "APPROVE" in last and "REVISE" not in last
            if not approved:
                state["revisions"] += 1
                if state["revisions"] < 2:
                    return ("note NOT saved — revise it and call save_note "
                            f"again. Referee feedback:\n{text}")
                # accept after one revision round; remaining concerns are
                # appended to the note as a referee-comments section
                content = content + "\n\n---\n## Referee comments " \
                    "(unresolved)\n\n" + text
        NOTES_DIR.mkdir(exist_ok=True)
        out = NOTES_DIR / _safe_name(name, ".md")
        out.write_text(content)
        return f"wrote notes/{out.name} ({len(content)} chars)"

    return save_note


WEB_SEARCH_TOOL = {
    "type": "web_search_20260209",
    "name": "web_search",
    "max_uses": 8,
}

def dry_run(task: str) -> None:
    """Exercise the tool plumbing WITHOUT any API call (no cost): runs a
    canned mini-sequence (read_references -> list_decay_modes ->
    query_ntuple on a standard file) and prints the results. Use this to
    test tool changes before spending API budget."""
    print(f"[dry-run] task (not sent anywhere): {task!r}")
    from .tools import list_decay_modes, query_ntuple, read_references
    print("[dry-run] read_references ->",
          read_references.call({})[:120].replace("\n", " "), "...")
    print("[dry-run] list_decay_modes ->",
          list_decay_modes.call({}).splitlines()[0], "...")
    try:
        print("[dry-run] query_ntuple ->",
              query_ntuple.call({"root_file": "signal_taunu.root"}))
    except Exception as e:
        print(f"[dry-run] query_ntuple failed: {e}")
    print("[dry-run] tool plumbing OK — no API call was made")


def run(task: str, model: str = MODEL, max_turns: int = 60,
        review: str = "human") -> None:
    """Run one analysis task through the Plan -> Execute -> Report loop.

    web_search is an Anthropic server-side tool: a long search turn can end
    with stop_reason "pause_turn", which the Python tool runner does not
    auto-resume — so the conversation is mirrored and the runner restarted
    with the paused turn appended (the pattern from the SDK docs).
    """
    client = anthropic.Anthropic()
    usage = Usage()
    approval = make_approval_tool(review, client, model, usage)
    note_tool = make_note_tool(review, client, model, usage)
    analysis_tools = [t for t in ANALYSIS_TOOLS if t.name != "save_note"]
    tools = [approval, note_tool, WEB_SEARCH_TOOL, *analysis_tools]

    messages = [{"role": "user", "content": task}]
    turns = 0
    restarts = 0
    try:
        while True:
            runner = client.beta.messages.tool_runner(
                model=model,
                max_tokens=32000,
                stream=True,  # >10-min requests require streaming (SDK guard)
                system=SYSTEM_PROMPT,
                tools=tools,
                messages=messages,
                # Prompt caching: every turn resends the system prompt, the
                # tool definitions and the whole history. Automatic caching
                # bills the repeated prefix as cheap cache reads instead of
                # full-price input.
                cache_control={"type": "ephemeral"},
                # Server-side fallback: a safety-classifier decline is
                # retried on a fallback model instead of failing outright.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
            last = None
            for item in runner:
                # with stream=True the runner yields message streams; the
                # loop body only needs the final message of each turn
                message = item.get_final_message() if hasattr(
                    item, "get_final_message") else item
                last = message
                turns += 1
                usage.add(getattr(message, "model", model), message.usage)
                for block in message.content:
                    if block.type == "text" and block.text.strip():
                        print(block.text)
                    elif block.type == "tool_use":
                        print(f"[tool] {block.name}({block.input})")
                    elif block.type == "server_tool_use":
                        print(f"[web] {block.name}({block.input})")
                # mirror the history: the runner keeps its own copy
                messages.append({"role": "assistant",
                                 "content": message.content})
                tool_response = runner.generate_tool_call_response()
                if tool_response is not None:
                    messages.append(tool_response)
                if turns >= max_turns:
                    print("!! max_turns reached — stopping the agent loop")
                    return
            if last is None or last.stop_reason != "pause_turn":
                break
            restarts += 1
            if restarts > 5:
                print("!! giving up: turn still paused after 5 restarts")
                break
    finally:
        # reported on every exit path, including max_turns and errors
        print(usage.report(turns))
