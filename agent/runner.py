"""The agent loop: Plan -> (student approval) -> Execute -> Report.

Uses the Anthropic SDK tool runner, which drives the model -> tool ->
model cycle automatically; the human-in-the-loop gate lives inside the
request_approval tool, mirroring the workflow figure in the README.
"""
from __future__ import annotations

import anthropic
from anthropic import beta_tool

from .tools import ANALYSIS_TOOLS

MODEL = "claude-opus-5"

SYSTEM_PROMPT = """\
You are a physics-analysis agent for a Belle II-like sensitivity-study
framework (EvtGen generation -> fast detector simulation -> ROOT ntuples).
You work together with a student. Follow this loop strictly:

1. PLAN: when given an analysis task, first summarize a short plan
   (samples to generate with event counts and seeds, the selection,
   the quantities to evaluate) and submit it with the request_approval
   tool. Do not generate MC or run any other tool before approval.
2. EXECUTE: after approval, run the pipeline tools. Fix seeds for
   reproducibility. If a tool fails, diagnose and retry with a fix.
3. REPORT: finish with a short Markdown report: what was done, the
   numbers in a table, which plots were written, and what the student
   should look at next.

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


@beta_tool
def request_approval(plan: str) -> str:
    """Present the analysis plan to the student and wait for approval.
    Must be called once, before any MC generation or analysis tool.

    Args:
        plan: the plan as a short Markdown bullet list.
    """
    print("\n=== PROPOSED PLAN ===\n" + plan + "\n=====================")
    answer = input("Approve this plan? [y/N] ").strip().lower()
    if answer in ("y", "yes"):
        return "approved — proceed"
    reason = input("Feedback for the agent: ").strip()
    return f"rejected — revise the plan. Student feedback: {reason}"


def run(task: str, model: str = MODEL, max_turns: int = 30) -> None:
    """Run one analysis task through the Plan -> Execute -> Report loop."""
    client = anthropic.Anthropic()
    runner = client.beta.messages.tool_runner(
        model=model,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        tools=[request_approval, *ANALYSIS_TOOLS],
        messages=[{"role": "user", "content": task}],
        # Server-side fallback: if a safety classifier declines a request,
        # it is retried on a fallback model instead of failing outright.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    for turn, message in enumerate(runner):
        for block in message.content:
            if block.type == "text" and block.text.strip():
                print(block.text)
            elif block.type == "tool_use":
                print(f"[tool] {block.name}({block.input})")
        if turn >= max_turns:
            print("!! max_turns reached — stopping the agent loop")
            break
