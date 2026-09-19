#!/usr/bin/env python
"""Publication step for agent-written notes: make them self-contained.

Takes a Markdown note from notes/, finds every referenced figure
(plots/<name>.png — whether embedded with image syntax or merely named in
the text), copies the figures next to the published note, ensures each is
actually embedded (a bare textual mention gets an image line inserted
after its paragraph), and renders a PDF with pandoc.

This is a mechanical publication step: the note's text is not edited
beyond inserting image embeds for figures the note already references.

The PDF gets the standard front matter (title from the note's first
heading, author line, version/date, and the public-materials disclaimer);
an "## Abstract" section, when present, becomes a proper LaTeX abstract.

usage: python analysis/render_note.py notes/<note>.md docs/notes/ [version]
"""
import datetime
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

    # front matter for the PDF: title from the first heading, an optional
    # "## Abstract" section lifted into a LaTeX abstract, the author line,
    # a version/date, and the public-materials disclaimer.
    version = sys.argv[3] if len(sys.argv) > 3 else "v1.0"
    body = text
    title = src.stem.replace("_", " ")
    m = re.match(r"\s*#\s+(.+)\n", body)
    if m:
        title = m.group(1).strip()
        body = body[m.end():]
    abstract = ""
    am = re.search(r"##\s*Abstract\s*\n(.*?)(?=\n##\s)", body, re.S)
    if am:
        abstract = " ".join(am.group(1).split())
        body = body[:am.start()] + body[am.end():]
    date = f"{version} — {datetime.date.today():%B %d, %Y}"
    disclaimer = ("This study uses only publicly available tools and "
                  "publications. No Belle II internal materials — data, MC, "
                  "internal notes, or the software framework — are used. "
                  "Everything is open-source and runs on a laptop.")
    body_path = out_dir / (src.stem + "_body.md")
    body_path.write_text(body)
    pdf_out = out_dir / (src.stem + ".pdf")
    cmd = ["pandoc", body_path.name, "-s", "-o", pdf_out.name,
           "--pdf-engine=xelatex",
           "--metadata", f"title={title}",
           "--metadata", "author=K. Yoshihara (University of Hawai\u02bbi "
                         "at M\u0101noa)",
           "--metadata", "author=analysis performed and written by an LLM "
                         "agent (Claude) under human review",
           "--metadata", f"date={date}",
           "-V", "geometry:margin=1in", "-V", "fontsize=11pt",
           "-V", "mainfont=Arial Unicode MS", "-V", "monofont=Menlo",
           "-V", f"include-before=\\begin{{center}}\\fbox{{"
                 f"\\parbox{{0.9\\textwidth}}{{\\small {disclaimer}"
                 f"}}}}\\end{{center}}"]
    if abstract:
        cmd += ["--metadata", f"abstract={abstract}"]
    subprocess.run(cmd, check=True, cwd=out_dir)
    body_path.unlink()
    print(f"published {md_out} (+{len(figures)} figures) and {pdf_out}")


if __name__ == "__main__":
    main()
