#!/usr/bin/env python
"""Publication step for agent-written notes: make them self-contained.

Takes a Markdown note from notes/, finds every referenced figure
(plots/<name>.png — whether embedded with image syntax or merely named in
the text), copies the figures next to the published note, ensures each is
actually embedded (a bare textual mention gets an image line inserted
after its paragraph), and renders a PDF with pandoc.

This is a mechanical publication step: the note's text is not edited
beyond inserting image embeds for figures the note already references.

usage: python analysis/render_note.py notes/<note>.md docs/notes/
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PLOTS = REPO / "plots"
FIG_RE = re.compile(r"plots/([A-Za-z0-9_.-]+\.png)")


def main():
    src = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])
    fig_dir = out_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    text = src.read_text()
    figures = sorted(set(FIG_RE.findall(text)))
    missing = [f for f in figures if not (PLOTS / f).exists()]
    if missing:
        sys.exit(f"missing figures in plots/: {missing}")
    for f in figures:
        shutil.copy(PLOTS / f, fig_dir / f)

    # ensure every referenced figure is embedded exactly once
    lines = text.splitlines()
    out_lines = []
    embedded = {f for f in figures
                if re.search(rf"!\[[^\]]*\]\([^)]*{re.escape(f)}\)", text)}
    done = set(embedded)
    for line in lines:
        out_lines.append(line)
        if line.lstrip().startswith("!["):
            continue
        for f in FIG_RE.findall(line):
            if f not in done:
                out_lines.append("")
                out_lines.append(f"![{f}](figures/{f})")
                done.add(f)
    # rewrite plots/ paths inside existing image embeds to the local copy
    text = "\n".join(out_lines)
    text = re.sub(r"(!\[[^\]]*\]\()plots/", r"\1figures/", text)

    md_out = out_dir / src.name
    md_out.write_text(text)
    pdf_out = out_dir / (src.stem + ".pdf")
    subprocess.run(
        ["pandoc", md_out.name, "-o", pdf_out.name,
         "--pdf-engine=xelatex",  # notes contain unicode (superscripts, Greek)
         "-V", "geometry:margin=1in", "-V", "fontsize=11pt",
         # fonts with full symbol coverage (arrows, ≠, ∈) on macOS
         "-V", "mainfont=Arial Unicode MS", "-V", "monofont=Menlo"],
        check=True, cwd=out_dir)
    print(f"published {md_out} (+{len(figures)} figures) and {pdf_out}")


if __name__ == "__main__":
    main()
