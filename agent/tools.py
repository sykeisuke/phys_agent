"""Analysis tools exposed to the LLM agent.

Each function wraps one step of the local pipeline (EvtGen generation,
fast sim + ntuple production, ntuple queries and plots). The @beta_tool
decorator turns the signature + docstring into a tool schema automatically.

All paths are confined to the repository (dec files under generation/dec/,
outputs under data/ and plots/), so the agent cannot touch anything else.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import numpy as np

from anthropic import beta_tool

REPO = Path(__file__).resolve().parents[1]
DEC_DIR = REPO / "generation" / "dec"
DATA_DIR = REPO / "data"
PLOT_DIR = REPO / "plots"
GENERATE_BIN = REPO / "generation" / "bin" / "generate"
MAX_EVENTS = 2_000_000

_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def _safe_name(name: str, suffix: str) -> str:
    """Allow only plain file names (no directories) with the right suffix."""
    if not _NAME_RE.match(name) or "/" in name or not name.endswith(suffix):
        raise ValueError(f"invalid file name {name!r} (expected *{suffix})")
    return name


@beta_tool
def list_decay_modes() -> str:
    """List the available EvtGen decay files (one per decay mode) with the
    description from their first comment line."""
    lines = []
    for dec in sorted(DEC_DIR.glob("*.dec")):
        first = dec.read_text().lstrip().splitlines()[0].lstrip("# ").strip()
        lines.append(f"{dec.name}: {first}")
    return "\n".join(lines)


@beta_tool
def generate_mc(dec_file: str, n_events: int, output_name: str, seed: int) -> str:
    """Generate Upsilon(4S) -> B Bbar Monte Carlo events with EvtGen.

    Args:
        dec_file: decay-file name from list_decay_modes, e.g. "B0_Dsttaunu.dec".
        n_events: number of events (1 to 2,000,000; ~2000 events/s, ~6 KB/event).
        output_name: output HepMC file name, e.g. "signal_taunu.hepmc" (written to data/).
        seed: random seed, fixed for reproducibility.
    """
    dec = DEC_DIR / _safe_name(dec_file, ".dec")
    if not dec.exists():
        return f"error: {dec_file} not found — call list_decay_modes first"
    if not 1 <= n_events <= MAX_EVENTS:
        return f"error: n_events must be within [1, {MAX_EVENTS}]"
    out = DATA_DIR / _safe_name(output_name, ".hepmc")
    DATA_DIR.mkdir(exist_ok=True)
    proc = subprocess.run(
        [str(GENERATE_BIN), str(dec), str(n_events), str(out), str(seed),
         str(DEC_DIR / "tau_native.dec")],
        capture_output=True, text=True, timeout=3600)
    if proc.returncode != 0:
        return f"generation failed:\n{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}"
    return proc.stdout.strip().splitlines()[-1]


@beta_tool
def make_ntuple(hepmc_file: str, output_name: str, mode_id: int, seed: int) -> str:
    """Run the fast detector simulation on a HepMC file and write a flat
    ROOT ntuple (one row per reconstructed D* + lepton candidate).

    Args:
        hepmc_file: input HepMC file name in data/, e.g. "signal_taunu.hepmc".
        output_name: output ROOT file name, e.g. "signal_taunu.root" (written to data/).
        mode_id: integer label stored in every row to identify this sample.
        seed: random seed for the detector smearing.
    """
    inp = DATA_DIR / _safe_name(hepmc_file, ".hepmc")
    if not inp.exists():
        return f"error: {hepmc_file} not found in data/"
    out = DATA_DIR / _safe_name(output_name, ".root")
    proc = subprocess.run(
        ["python", str(REPO / "fastsim" / "make_ntuple.py"),
         str(inp), str(out), str(mode_id), str(seed)],
        capture_output=True, text=True, timeout=3600)
    if proc.returncode != 0:
        return f"ntuple production failed:\n{proc.stderr[-2000:]}"
    return proc.stdout.strip()


def _load(root_file: str, columns=None):
    import uproot
    path = DATA_DIR / _safe_name(root_file, ".root")
    return uproot.open(path)["events"].arrays(columns, library="np")


def _apply_cut(arrays: dict, selection: str) -> np.ndarray:
    """Evaluate a numpy boolean expression over the ntuple branches.

    The namespace contains only the branch arrays plus abs/log/sqrt —
    no builtins — so the agent can express cuts like
    "(abs(m_d0 - 1.8648) < 0.02) & (m2miss > 1.5)".
    """
    ns = {"abs": np.abs, "log": np.log, "sqrt": np.sqrt, "__builtins__": {}}
    ns.update(arrays)
    mask = eval(selection, ns)  # noqa: S307 — restricted namespace, local tool
    return np.asarray(mask, dtype=bool)


@beta_tool
def query_ntuple(root_file: str, selection: str = "m2miss > -999") -> str:
    """Count ntuple candidates passing a selection, overall and per true_mode.

    Args:
        root_file: ROOT file name in data/, e.g. "signal_taunu.root".
        selection: numpy boolean expression over the branch names, e.g.
            "(abs(m_d0 - 1.8648) < 0.02) & (abs(delta_m - 0.14543) < 0.0025)".
            Available branches: m2miss, plep_star, q2, m_d0, delta_m,
            p_lep_lab, costh_lep_lab, p_dst_lab, m2miss_true, plep_star_true,
            q2_true, true_mode (1 = D* tau nu, 2 = D* mu nu, 0 = other),
            mode_id, event.
    """
    t = _load(root_file)
    mask = _apply_cut(t, selection)
    parts = [f"total: {len(mask)}", f"pass: {int(mask.sum())}"]
    for mode, label in [(1, "true D*taunu"), (2, "true D*munu"), (0, "true other")]:
        parts.append(f"{label}: {int((mask & (t['true_mode'] == mode)).sum())}")
    return ", ".join(parts)


@beta_tool
def plot_variable(root_files: list[str], variable: str, output_name: str,
                  selection: str = "m2miss > -999",
                  x_min: float = 0.0, x_max: float = 10.0, n_bins: int = 50) -> str:
    """Plot one ntuple variable for one or more samples (normalized overlay)
    and save it under plots/.

    Args:
        root_files: ROOT file names in data/, e.g. ["signal_taunu.root", "norm_munu.root"].
        variable: branch name to plot, e.g. "m2miss".
        output_name: output PNG name, e.g. "m2miss_compare.png".
        selection: numpy boolean expression applied before plotting.
        x_min: lower edge of the histogram.
        x_max: upper edge of the histogram.
        n_bins: number of bins.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    PLOT_DIR.mkdir(exist_ok=True)
    bins = np.linspace(x_min, x_max, n_bins + 1)
    fig, ax = plt.subplots(figsize=(6.4, 4.4))
    for rf in root_files:
        t = _load(rf)
        mask = _apply_cut(t, selection)
        ax.hist(t[variable][mask], bins=bins, histtype="step", lw=2,
                density=True, label=rf.replace(".root", ""))
    ax.set_xlabel(variable)
    ax.set_ylabel("normalized entries")
    ax.legend()
    fig.tight_layout()
    out = PLOT_DIR / _safe_name(output_name, ".png")
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return f"wrote {out.relative_to(REPO)}"


ANALYSIS_TOOLS = [list_decay_modes, generate_mc, make_ntuple, query_ntuple,
                  plot_variable]
