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


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
