"""The agent loop: Plan -> (student approval) -> Execute -> Report.

Uses the Anthropic SDK tool runner, which drives the model -> tool ->
model cycle automatically; the human-in-the-loop gate lives inside the
request_approval tool, mirroring the workflow figure in the README.
"""
from __future__ import annotations

import anthropic
from anthropic import beta_tool

from .tools import ANALYSIS_TOOLS, NOTES_DIR, _safe_name

MODEL = "claude-opus-5"

SYSTEM_PROMPT = """\
You are a physics-analysis agent for a Belle II-like sensitivity-study
framework (EvtGen generation -> fast detector simulation -> ROOT ntuples).
You work together with a student. Follow this loop strictly:

1. PLAN: first call read_references; when the mode at hand is not covered
   there (or you need concrete numbers such as measured branching
   fractions or published selection windows), use web_search to consult
   the literature (arXiv, journals, PDG) before designing the selection.
   Then summarize a short plan
   (samples to generate with event counts and seeds, the selection,
   the quantities to evaluate) and submit it with the request_approval
   tool. Do not generate MC or run any other tool before approval.
2. EXECUTE: after approval, run the pipeline tools. Fix seeds for
   reproducibility. If a tool fails, diagnose and retry with a fix.
3. REPORT: give a short Markdown report in the conversation: what was
   done, the numbers in a table, which plots were written.
4. NOTE: for a full analysis (one that produced a physics result, not a
   quick check), finish by writing a complete analysis note with the
   save_note tool, structured as: Introduction (motivation, citing the
   analyses followed) / Samples (table: process, generator+model, events,
   seeds) / Selection optimization (variables, scans, chosen cuts) /
   Background estimation (composition, method) / Results (cut & count and
   any fits, with uncertainties) / Discussion (limitations, systematics
   not yet evaluated) / Conclusion. Quality bar (a physicist should be
   able to referee it): give a cutflow table with per-stage efficiencies;
   motivate every cut by naming the background it removes and show the
   scan that fixed its value; where a control region exists, quote its
   yield and purity; embed every plot you produced with Markdown image syntax (![caption](plots/<name>.png)) at the point where it is discussed — a bare filename mention is not enough; state
   what is NOT modeled and how a real analysis would handle it; cite the
   published analyses you followed. Every number in the note must come
   from a tool result of this session.

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
- samples: event counts and seeds stated and reasonable (<= 2M events)?
- selection: cut & count with named variables (no NN/BDT)?
- precedent: does it say which published analysis the variables follow?
- deliverables: efficiencies, yields, and plots specified?
CONCERNS: anything risky or missing (or "none").
VERDICT: exactly one final line, either "APPROVE" or
"REVISE: <specific, actionable feedback>".
"""


def make_approval_tool(review: str, client, model: str):
    """Build the approval gate for the chosen review mode.

    'human' (default): the student answers y/N on the terminal.
    'ai'  : a second LLM instance reviews the plan against the checklist —
            use once the workflow is established and trusted.
    """
    state = {"revisions": 0}

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


def make_note_tool(review: str, client, model: str):
    """save_note, with an AI referee in front of it when review == 'ai'."""
    state = {"revisions": 0}

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
        if review == "ai":
            verdict = client.messages.create(
                model=model, max_tokens=8192, system=NOTE_REVIEWER_PROMPT,
                messages=[{"role": "user", "content": content}])
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

# USD per million tokens (input, output) — for the end-of-run cost report
PRICES = {"claude-opus-5": (5, 25), "claude-sonnet-5": (2, 10),
          "claude-haiku-4-5": (1, 5)}


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
    approval = make_approval_tool(review, client, model)
    note_tool = make_note_tool(review, client, model)
    analysis_tools = [t for t in ANALYSIS_TOOLS if t.name != "save_note"]
    tools = [approval, note_tool, WEB_SEARCH_TOOL, *analysis_tools]

    messages = [{"role": "user", "content": task}]
    turns = 0
    restarts = 0
    tok_in = tok_out = 0
    while True:
        runner = client.beta.messages.tool_runner(
            model=model,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            tools=tools,
            messages=messages,
            # Server-side fallback: a safety-classifier decline is retried
            # on a fallback model instead of failing outright.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        last = None
        for message in runner:
            last = message
            turns += 1
            if message.usage:
                tok_in += message.usage.input_tokens
                tok_out += message.usage.output_tokens
            for block in message.content:
                if block.type == "text" and block.text.strip():
                    print(block.text)
                elif block.type == "tool_use":
                    print(f"[tool] {block.name}({block.input})")
                elif block.type == "server_tool_use":
                    print(f"[web] {block.name}({block.input})")
            # mirror the history: the runner keeps its own copy internally
            messages.append({"role": "assistant", "content": message.content})
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
    pin, pout = PRICES.get(model, (5, 25))
    cost = tok_in / 1e6 * pin + tok_out / 1e6 * pout
    print(f"[usage] {turns} API turns, {tok_in:,} in / {tok_out:,} out "
          f"tokens ~= ${cost:.2f} ({model}; reviewer calls excluded)")
