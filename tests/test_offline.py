"""Offline tests: no API calls, no MC generation. Run with
`python -m pytest tests/` (or `python tests/test_offline.py`)."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent import runner, tools  # noqa: E402

TABLE = "belle2_kstll_2206.05946.json"


def _call(tool, **kw):
    return tool.call(kw)


def test_systematics_kst0_mumu_total():
    out = _call(tools.apply_systematics, table=TABLE, mode="B0_Kst0_Kpi_mumu",
                value=1.19e-6, stat=0.31e-6)
    # quadrature of the published entries for this mode (upper ends):
    up = np.sqrt(0.4**2 + 2.5**2 + 1.9**2 + 1.2**2 + 1.7**2 + 0.5**2
                 + 1.0**2 + 1.0**2 + 1.2**2 + 2.9**2)
    dn = np.sqrt(0.4**2 + 2.5**2 + 0.8**2 + 1.2**2 + 1.7**2 + 0.5**2
                 + 1.0**2 + 1.0**2 + 1.2**2 + 2.9**2)
    assert f"+{up:.2g}%" in out and f"-{dn:.2g}%" in out, out
    assert "Tracking | +1.2" in out          # 0.3% x 4 tracks
    assert "MVA selection" in out and "placeholder" in out.lower()


def test_systematics_tracking_rule_and_modes():
    out = _call(tools.apply_systematics, table=TABLE, mode="Bp_Kstp_KSpi_ee",
                value=1.0, stat=0.1)
    assert "Tracking | +1.5" in out          # 5 tracks incl. K_S daughters
    assert "K_S identification" in out and "Electron identification" in out
    assert "Kaon identification" not in out
    out = _call(tools.apply_systematics, table=TABLE, mode="nope",
                value=1.0, stat=0.1)
    assert out.startswith("error: unknown mode")


def test_systematics_mc_evaluated_override():
    out = _call(tools.apply_systematics, table=TABLE, mode="B0_Kst0_Kpi_ee",
                value=1.0, stat=0.1, evaluated={"pdf_shape": 0.3})
    assert "evaluated on MC" in out
    bad = _call(tools.apply_systematics, table=TABLE, mode="B0_Kst0_Kpi_ee",
                value=1.0, stat=0.1, evaluated={"n_bb": 0.1})
    assert bad.startswith("error:")          # global entries stay published


def test_tree_autodetect_subdir_and_empty_selection():
    import uproot
    with tempfile.TemporaryDirectory() as d:
        old = tools.DATA_DIR
        tools.DATA_DIR = Path(d)
        try:
            (Path(d) / "kekcc").mkdir()
            with uproot.recreate(Path(d) / "kekcc" / "b2.root") as f:
                f["ntuple"] = {"Mbc": np.array([5.27, 5.21, 5.28]),
                               "B_rank": np.array([1, 2, 1])}
            out = _call(tools.query_ntuple, root_file="kekcc/b2.root")
            assert "total: 3" in out and "pass: 3" in out, out
            out = _call(tools.query_ntuple, root_file="kekcc/b2.root",
                        selection="(Mbc > 5.26) & (B_rank == 1)")
            assert "pass: 2" in out, out
            assert "Mbc" in _call(tools.list_branches,
                                  root_file="kekcc/b2.root")
            for bad in ("../x.root", "/etc/x.root", "kekcc//b2.root",
                        "kekcc/b2.txt"):
                try:
                    tools._data_path(bad)
                except ValueError:
                    continue
                raise AssertionError(f"accepted {bad!r}")
        finally:
            tools.DATA_DIR = old


def test_usage_cost_counts_cache_and_reviewer():
    u = runner.Usage()
    u.add("claude-sonnet-5", SimpleNamespace(
        input_tokens=1_000_000, output_tokens=100_000,
        cache_creation_input_tokens=1_000_000,
        cache_read_input_tokens=10_000_000, server_tool_use=None))
    u.add("claude-sonnet-5", SimpleNamespace(   # a reviewer call
        input_tokens=0, output_tokens=0, cache_creation_input_tokens=0,
        cache_read_input_tokens=0,
        server_tool_use=SimpleNamespace(web_search_requests=2)))
    # 1M x $2 + 1M x $2.5 (write) + 10M x $0.20 (read) + 0.1M x $10 + 2 x $0.01
    assert abs(u.cost() - (2 + 2.5 + 2 + 1 + 0.02)) < 1e-9
    assert "2 calls" in u.report(5)


def test_note_structure_check():
    from agent.tools import _check_note_structure, _NOTE_SECTIONS
    def note(drop=None, swap=False):
        titles = [t for _, t in _NOTE_SECTIONS]
        if swap:
            titles[7], titles[8] = titles[8], titles[7]
        out = "## Abstract\nx\n"
        for t in titles:
            out += f"## {t}\n\n"
            out += "text\n\n" if t == drop else "**Table 1.** t\n\n| a |\n|---|\n| 1 |\n\n"
        return out
    assert _check_note_structure(note()) == []
    bad = _check_note_structure(note(drop="3 Event selection and reconstruction"))
    assert bad and "neither a table nor a figure" in bad[0], bad
    assert "not in the template order" in _check_note_structure(note(swap=True))[0]
    assert any("Abstract" in p for p in _check_note_structure("## 1 Introduction\n"))


def test_runner_note_tool_enforces_template():
    from agent.runner import make_note_tool
    tool = make_note_tool("human", client=None, model="x")
    r = tool.call({"name": "zz_test.md", "content": "## 1 Introduction\nx\n"})
    assert "REJECTED" in r and "Abstract" in r, r


def test_note_register_and_overfull():
    from agent.tools import _check_note_structure, _overfull_boxes
    import tempfile, pathlib
    secs = ["1 Introduction", "2 Detector model and samples",
            "3 Event selection and reconstruction",
            "4 Background estimation and suppression",
            "5 Signal yield extraction",
            "6 Efficiency corrections and systematic uncertainties",
            "7 Results and summary", "8 Discussion"]
    body = "".join(f"## {t}\n\n**Table 1.** t\n\n| a |\n|---|\n| 1 |\n\n" for t in secs)
    tail = "## 9 Analysis provenance\n`query_ntuple` on data/kekcc/a.root, isSignal\n\n## 10 References\n1. x\n"
    ok = "## Abstract\nB0 -> K*0 e+e- signal MC, M_bc.\n" + body + tail
    assert _check_note_structure(ok) == []
    bad = ok.replace("| 1 |", "| `Kstr_M` from kekcc/B0_x_1.root via query_ntuple |", 1)
    probs = _check_note_structure(bad)
    assert len(probs) == 1 and "paper register" in probs[0] and "`Kstr_M`" in probs[0], probs
    # an image embed's path is not jargon
    assert _check_note_structure(ok.replace("| 1 |", "| 1 |\n\n![M_bc after cuts](plots/mbc.png)", 1)) == []
    log = pathlib.Path(tempfile.mkdtemp()) / "x.log"
    log.write_text("Overfull \\hbox (53.9pt too wide) in alignment at lines 93--110\n"
                   "Overfull \\hbox (2.0pt too wide) in paragraph at lines 5--6\n")
    assert _overfull_boxes(log) == ["54pt at lines 93--110"], _overfull_boxes(log)


def test_recipe_and_selection_tools():
    from agent.tools import read_recipe, read_selection
    assert "seven fields" in read_recipe.call({"name": ""}).lower() or "specification" in read_recipe.call({"name": ""})
    assert "Figure of merit" in read_recipe.call({"name": "bf_measurement"})
    assert read_recipe.call({"name": "nope"}).startswith("error")
    assert read_recipe.call({"name": "../x"}).startswith("error")
    sel = read_selection.call({"name": "kstll_reference_ntuple_plots"})
    assert "best_candidate" in sel and "reference_cutflow_percent" in sel
    assert read_selection.call({"name": "nope"}).startswith("error")


def test_scan_cut_figures_of_merit():
    from agent.tools import scan_cut
    common = dict(signal_file="signal_taunu.root",
                  background_files=["norm_lnu.root", "bkg_dststlnu.root"],
                  variable="m2miss", thresholds=[1.5],
                  base_selection="abs(m_d0 - 1.8648) < 0.02")
    base = scan_cut.call(common)
    assert "RAW MC counts" in base and "S/sqrt(S+B)=" in base
    w = scan_cut.call({**common, "fom": "syst", "sigma_b": 0.2,
                       "signal_weight": 0.1, "background_weights": [2.0, 1.0]})
    assert "expected yields" in w and "syst=" in w and "S=220.3" in w, w
    assert "punzi=" in scan_cut.call({**common, "fom": "punzi"})
    a = scan_cut.call({**common, "fom": "asimov", "fit_variable": "m2miss",
                       "fit_range": [-1, 8], "n_bins": 10})
    assert "asimov=" in a and "Asimov fit of m2miss" in a, a
    assert scan_cut.call({**common, "fom": "bogus"}).startswith("error")
    assert scan_cut.call({**common, "fom": "asimov", "fit_variable": "Mbc"}).startswith("error")


def test_reference_selection_resolves_per_channel():
    import yaml
    from agent.tools import REPO
    d = yaml.safe_load((REPO / "docs/selections/kstll_reference_ntuple_plots.yaml").read_text())
    assert d["truth_match"].startswith("("), "truth_match must be parenthesized"
    for ch, sub in d["channels"].items():
        for c in d["cuts"]:
            e = c["expr"]
            if isinstance(e, dict):
                e = e.get(sub["LEP"]) or e.get(sub["B"])
            assert e, (ch, c["name"])
            e.format(**sub)                      # all placeholders resolve
    pion = next(c for c in d["cuts"] if c["name"] == "pion ID")["expr"]
    assert "decayModeID" not in pion["B0"] and "decayModeID" in pion["B"]


def test_caption_placement_checks():
    from agent.tools import _check_latex_captions, _check_table_captions
    good = ("\\begin{table}\\caption{x}\\begin{tabular}{l}a\\end{tabular}\\end{table}"
            "\\begin{figure}\\includegraphics{a.png}\\caption{y}\\end{figure}")
    assert _check_latex_captions(good) == []
    bad = ("\\begin{table}\\begin{tabular}{l}a\\end{tabular}\\caption{x}\\end{table}"
           "\\begin{figure}\\caption{y}\\includegraphics{a.png}\\end{figure}"
           "\\begin{figure}\\includegraphics{b.png}\\end{figure}")
    probs = _check_latex_captions(bad)
    assert any("table" in p and "BEFORE" in p for p in probs), probs
    assert any("figure" in p and "AFTER" in p for p in probs), probs
    assert any("no \\caption" in p for p in probs), probs
    ok_md = ["**Table 1.** Samples.", "", "| a | b |", "|---|---|", "| 1 | 2 |"]
    assert _check_table_captions(ok_md) == []
    bad_md = ["Some text.", "", "| a | b |", "|---|---|", "| 1 | 2 |"]
    assert "caption line" in _check_table_captions(bad_md)[0]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
