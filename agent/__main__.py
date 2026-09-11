"""CLI entry point.

usage:
    python -m agent "Compare m2_miss between B0 -> D* tau nu and B0 -> D* mu nu"

Requires the anthropic package (pip install anthropic) and an API
credential (ANTHROPIC_API_KEY, or a profile from `ant auth login`).
"""
import argparse

from .runner import MODEL, run


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="python -m agent",
        description="Run one analysis task through the physics agent.")
    ap.add_argument("task", help="the analysis task, in plain language")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--review", choices=["human", "ai"], default="human",
                    help="approval gate: 'human' (student answers y/N) or "
                         "'ai' (a second LLM reviews the plan)")
    args = ap.parse_args()
    run(args.task, model=args.model, review=args.review)


if __name__ == "__main__":
    main()
