"""Analysis tools exposed to the LLM agent.

Each function wraps one step of the local pipeline (EvtGen generation,
fast sim + ntuple production, ntuple queries and plots). The @beta_tool
decorator turns the signature + docstring into a tool schema automatically.

All paths are confined to the repository (dec files under generation/dec/,
ntuples and outputs under data/ and plots/, read-only systematics tables
under systematics/), so the agent cannot touch anything else.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import numpy as np

from anthropic import beta_tool

REPO = Path(__file__).resolve().parents[1]
DEC_DIR = REPO / "generation" / "dec"
DATA_DIR = REPO / "data"
PLOT_DIR = REPO / "plots"
NOTES_DIR = REPO / "notes"
SYST_DIR = REPO / "systematics"
GENERATE_BIN = REPO / "generation" / "bin" / "generate"
MAX_EVENTS = 2_000_000

_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
_PATH_RE = re.compile(r"^[A-Za-z0-9_.\-/]+$")
_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _safe_name(name: str, suffix: str) -> str:
    """Allow only plain file names (no directories) with the right suffix."""
    if not _NAME_RE.match(name) or "/" in name or not name.endswith(suffix):
        raise ValueError(f"invalid file name {name!r} (expected *{suffix})")
    return name


def _data_path(root_file: str) -> Path:
    """Resolve an ntuple name to a file under data/ (subdirectories such
    as data/kekcc/x.root are allowed; escaping data/ is not)."""
    if (not _PATH_RE.match(root_file) or ".." in root_file or "//" in root_file
            or root_file.startswith("/") or not root_file.endswith(".root")):
        raise ValueError(f"invalid ntuple path {root_file!r}")
    # normalize without following symlinks (data/kekcc may be a link)
    path = Path(os.path.normpath(DATA_DIR / root_file))
    if DATA_DIR not in path.parents:
        raise ValueError(f"{root_file!r} is outside data/")
    return path


_TREE_CACHE: dict = {}
_TREE_NAME: dict = {}


def _tree(root_file: str):
    """The analysis TTree of a file: 'events' (this framework's producers),
    else 'ntuple' (basf2), else the only / first TTree in the file."""
    import uproot
    path = _data_path(root_file)
    key = str(path)
    if key not in _TREE_CACHE:
        f = uproot.open(path)
        trees = [k.split(";")[0] for k, cls in f.classnames().items()
                 if cls in ("TTree", "ROOT::RNTuple")]
        name = next((n for n in ("events", "ntuple") if n in trees),
                    trees[0] if trees else None)
        if name is None:
            raise ValueError(f"{root_file}: no TTree found")
        _TREE_CACHE[key] = f[name]
        _TREE_NAME[key] = name
    return _TREE_CACHE[key]


def _tree_name(root_file: str) -> str:
    _tree(root_file)
    return _TREE_NAME[str(_data_path(root_file))]


def _branches(root_file: str) -> list:
    return [k.split(";")[0] for k in _tree(root_file).keys()]


def _load(root_file: str, columns=None):
    """Read branches as numpy arrays; columns=None reads everything."""
    return _tree(root_file).arrays(columns, library="np")


def _load_for(root_file: str, *exprs: str):
    """Read only the branches named in the given expressions/variables
    (keeps 300-branch official ntuples fast and small in memory)."""
    have = set(_branches(root_file))
    names = set()
    for e in exprs:
        if e:
            names.update(_IDENT_RE.findall(e))
    cols = sorted(names & have)
    missing = sorted(n for n in names & set(_known_free_symbols(exprs)) if n not in have)
    if missing:
        raise KeyError(f"{root_file}: unknown branch(es) {missing}; "
                       f"call inspect_ntuple to list the available ones")
    if not cols:  # e.g. selection "1 == 1": keep one column for the length
        cols = [_branches(root_file)[0]]
    return _load(root_file, cols)


def _known_free_symbols(exprs):
    """Identifiers in expressions that are not functions/keywords."""
    skip = {"abs", "log", "sqrt", "and", "or", "not", "True", "False", "None"}
    out = []
    for e in exprs:
        if e:
            out.extend(n for n in _IDENT_RE.findall(e) if n not in skip)
    return out


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


@beta_tool
def generate_continuum(n_events: int, output_name: str, seed: int) -> str:
    """Generate continuum e+e- -> qq (u,d,s,c) background with Pythia8,
    directly into a ROOT ntuple (same branches as make_ntuple). The
    printout reports the cross section needed for luminosity weighting.

    Args:
        n_events: number of events (1 to 2,000,000; ~7000 events/s).
        output_name: output ROOT file name, e.g. "continuum_0.root" (written to data/).
        seed: random seed, fixed for reproducibility.
    """
    if not 1 <= n_events <= MAX_EVENTS:
        return f"error: n_events must be within [1, {MAX_EVENTS}]"
    out = DATA_DIR / _safe_name(output_name, ".root")
    DATA_DIR.mkdir(exist_ok=True)
    proc = subprocess.run(
        ["python", str(REPO / "generation" / "generate_continuum.py"),
         str(n_events), str(out), str(seed)],
        capture_output=True, text=True, timeout=3600)
    if proc.returncode != 0:
        return f"continuum generation failed:\n{proc.stderr[-2000:]}"
    return "\n".join(proc.stdout.strip().splitlines()[-2:])


def _apply_cut(arrays: dict, selection: str) -> np.ndarray:
    """Evaluate a numpy boolean expression over the ntuple branches.

    The namespace contains only the branch arrays plus abs/log/sqrt —
    no builtins — so the agent can express cuts like
    "(abs(m_d0 - 1.8648) < 0.02) & (m2miss > 1.5)". An empty selection
    keeps every row.
    """
    if not selection.strip():
        n = len(next(iter(arrays.values()))) if arrays else 0
        return np.ones(n, dtype=bool)
    ns = {"abs": np.abs, "log": np.log, "sqrt": np.sqrt, "__builtins__": {}}
    ns.update(arrays)
    if not selection or not selection.strip():
        selection = "True"  # empty selection = all rows
    # ratios such as kaonID/(kaonID+pionID) divide by zero on some rows;
    # the warning machinery would need __import__, which the sandboxed
    # namespace deliberately lacks, so silence numpy here
    with np.errstate(divide="ignore", invalid="ignore"):
        mask = np.asarray(eval(selection, ns), dtype=bool)  # noqa: S307 — restricted namespace
    if mask.ndim == 0:  # a constant selection such as "1 == 1"
        n = len(next(iter(arrays.values()))) if arrays else 0
        mask = np.full(n, bool(mask))
    return mask


@beta_tool
def list_branches(root_file: str, pattern: str = "") -> str:
    """List the branch names of an ntuple (optionally only those containing
    a substring). Use this before writing selections for an ntuple whose
    branches you have not seen, e.g. the Belle II full-MC ntuples.

    Args:
        root_file: ROOT file under data/, e.g.
            "kekcc/B0_Kstll_neutral_mu_ntuple_1.root".
        pattern: case-insensitive substring filter, e.g. "PID"; empty
            lists every branch.
    """
    t = _tree(root_file)
    names = [n for n in t.keys() if pattern.lower() in n.lower()]
    return (f"{t.num_entries} entries, {len(names)} branches"
            + (f" matching {pattern!r}" if pattern else "") + ": "
            + ", ".join(names))


def _event_key(t: dict, root_file: str):
    """A per-row event identifier (run*1e7 + event when both exist)."""
    names = _branches(root_file)
    ev = "__event__" if "__event__" in names else ("event" if "event" in names else None)
    if ev is None:
        return None
    if ev not in t:
        t.update(_load(root_file, [ev] + (["__run__"] if "__run__" in names else [])))
    key = t[ev].astype(np.int64)
    if "__run__" in t:
        key = key + t["__run__"].astype(np.int64) * 10**7
    return key


def _best_per_event(t: dict, mask: np.ndarray, best_by: str, key) -> np.ndarray:
    """Restrict mask to one candidate per event: the one with the LOWEST
    value of the expression best_by among the candidates passing mask."""
    if not best_by or key is None:
        return mask
    ns = {"abs": np.abs, "log": np.log, "sqrt": np.sqrt, "__builtins__": {}}
    ns.update(t)
    with np.errstate(divide="ignore", invalid="ignore"):
        score = np.asarray(eval(best_by, ns), dtype=float)  # noqa: S307 — restricted namespace
    idx = np.flatnonzero(mask)
    if len(idx) == 0:
        return mask
    order = np.lexsort((score[idx], key[idx]))
    idx = idx[order]
    first = np.r_[True, key[idx][1:] != key[idx][:-1]]
    out = np.zeros_like(mask)
    out[idx[first]] = True
    return out


@beta_tool
def query_ntuple(root_file: str = "", selection: str = "",
                 group_by: str = "", best_by: str = "",
                 post_selection: str = "",
                 root_files: list[str] | None = None) -> str:
    """Count ntuple candidates passing a selection, optionally broken down
    by the values of one branch (e.g. a truth label, a lepton flavor,
    a candidate rank). Call inspect_ntuple first for an unfamiliar file.

    Args:
        root_file: ROOT file under data/ (subdirectories allowed), e.g.
            "signal_taunu.root" or "kekcc/B0_Kstll_neutral_mu_ntuple_1.root".
            May be omitted when root_files is given.
        selection: numpy boolean expression over branch names, e.g.
            "(abs(m_d0 - 1.8648) < 0.02) & (Mbc > 5.27)". Functions
            available: abs, log, sqrt. An empty selection keeps all rows.
            This framework's own ntuples carry: m2miss, e_tag_cm, m_tag,
            q2, m_d0, delta_m, r2, plep_star, true_mode (1 = D* tau nu,
            2 = D* l nu, 0 = other B, 3 = continuum), lep_true_pid,
            lep_flavor (11 = e, 13 = mu), mode_id; exclusive ones add
            m_visible, mbc, delta_e, m_ll; combinatorial ones add
            ll_true_src. Official basf2 ntuples use their own names
            (Mbc, deltaE, isSignal, mcErrors, B_rank, __event__, ...).
        group_by: optional branch name; the count is then also reported
            per value of that branch (up to 12 most frequent values).
            For this framework's ntuples true_mode is used when present.
        best_by: optional expression; when given, only ONE candidate per
            event is kept among those passing the selection — the one
            with the lowest value, e.g. "abs(deltaE)" (the published
            best-candidate choice). Events are identified by the
            __event__/__run__ (or event) branches.
        post_selection: optional expression applied AFTER the
            best-candidate choice (e.g. a signal box "(Mbc > 5.27) &
            (abs(deltaE) < 0.05)", or a truth flag), so the best candidate
            is chosen among all candidates passing `selection` first.
        root_files: optional list of files (e.g. the 5 copies of one
            sample) to query together; counts are summed over the files
            (events are distinct per file). Use this instead of one call
            per file.
    When the file has an event identifier the result also reports the
    number of distinct EVENTS passing (candidates can repeat per event).
    """
    files = list(root_files) if root_files else [root_file]
    if not files or not files[0]:
        return "error: give root_file or a non-empty root_files list"
    total = passed = events = 0
    have_key = True
    grouped: dict = {}
    for rf in files:
        t = _load_for(rf, selection, group_by or "", best_by or "",
                      post_selection or "",
                      "true_mode" if "true_mode" in _branches(rf) else "")
        mask = _apply_cut(t, selection)
        key = _event_key(t, rf)
        mask = _best_per_event(t, mask, best_by, key)
        if post_selection:
            mask = mask & _apply_cut(t, post_selection)
        total += len(mask)
        passed += int(mask.sum())
        if key is None:
            have_key = False
        else:
            events += len(np.unique(key[mask]))
        gkey = group_by or ("true_mode" if "true_mode" in t else "")
        if gkey and gkey in t:
            vals = t[gkey][mask]
            if vals.dtype.kind == "f":
                n_nan = int(np.isnan(vals).sum())
                if n_nan:  # report undefined values instead of dropping them
                    grouped["nan"] = grouped.get("nan", 0) + n_nan
                vals = vals[~np.isnan(vals)]
            u, c = np.unique(vals, return_counts=True)
            for v, n in zip(u, c):
                grouped[float(v)] = grouped.get(float(v), 0) + int(n)
    parts = [f"files: {len(files)}"] if len(files) > 1 else []
    parts += [f"total: {total}", f"pass: {passed}"]
    if have_key:
        parts.append(f"events passing: {events}")
    key = group_by or ("true_mode" if grouped and not group_by else "")
    if grouped:
        labels = ({1: "true D*taunu", 2: "true D*lnu", 0: "true other B",
                   3: "continuum"} if key == "true_mode" else {})
        for v, n in sorted(grouped.items(), key=lambda kv: -kv[1])[:12]:
            if v == "nan":
                parts.append(f"{key}=undefined (NaN): {n}")
            else:
                parts.append(f"{labels.get(int(v), f'{key}={v:g}')}: {n}")
    return ", ".join(parts)
    # (legacy single-file path below is unreachable)
    t = _load_for(root_file, selection, group_by or "", best_by or "",
                  post_selection or "",
                  "true_mode" if "true_mode" in _branches(root_file) else "")
    mask = _apply_cut(t, selection)
    key = _event_key(t, root_file)
    mask = _best_per_event(t, mask, best_by, key)
    if post_selection:
        mask = mask & _apply_cut(t, post_selection)
    parts = [f"total: {len(mask)}", f"pass: {int(mask.sum())}"]
    if key is not None:
        parts.append(f"events passing: {len(np.unique(key[mask]))}")
    key = group_by or ("true_mode" if "true_mode" in t else "")
    if key and key in t:
        vals = t[key][mask]
        vals = vals[~np.isnan(vals)] if vals.dtype.kind == "f" else vals
        labels = ({1: "true D*taunu", 2: "true D*lnu", 0: "true other B",
                   3: "continuum"} if key == "true_mode" else {})
        u, c = np.unique(vals, return_counts=True)
        order = np.argsort(-c)[:12]
        for i in order:
            v = u[i]
            name = labels.get(int(v), f"{key}={v:g}" if isinstance(v, float) else f"{key}={v}")
            parts.append(f"{name}: {int(c[i])}")
    return ", ".join(parts)


@beta_tool
def list_samples(pattern: str = "") -> str:
    """List the ntuple files available under data/ (recursively), grouped
    by sample: files that differ only by a trailing _N index are reported
    as one group with the file count and total entries. Use this first
    when you did not produce the ntuples yourself.

    Args:
        pattern: optional substring filter on the path, e.g. "kekcc".
    """
    groups: dict = {}
    found = []
    for dirpath, _dirs, files in os.walk(DATA_DIR, followlinks=True):
        found += [Path(dirpath) / f for f in files if f.endswith(".root")]
    for path in sorted(found):
        rel = str(path.relative_to(DATA_DIR))
        if pattern and pattern not in rel:
            continue
        stem = re.sub(r"_\d+\.root$", ".root", rel)
        try:
            n = _tree(rel).num_entries
        except Exception as exc:  # unreadable file: still list it
            n = -1
        g = groups.setdefault(stem, [0, 0, []])
        g[0] += 1
        g[1] += max(n, 0)
        g[2].append(rel)
    if not groups:
        return "no ntuples found"
    lines = ["sample group (files) : total entries : example file"]
    for stem, (nf, ne, files) in groups.items():
        lines.append(f"{stem} ({nf}) : {ne} : {files[0]}")
    # sample context files travel with the samples (data/<dir>/CONTEXT.md)
    dirs = sorted({str(Path(f).parent) for g in groups.values() for f in g[2]})
    for d in dirs:
        ctx = DATA_DIR / d / "CONTEXT.md"
        if ctx.exists():
            lines.append(f"\n--- sample context data/{d}/CONTEXT.md "
                         "(authoritative facts; do not guess what it "
                         "does not state) ---\n" + ctx.read_text().strip())
    return "\n".join(lines)


@beta_tool
def inspect_ntuple(root_file: str, pattern: str = "",
                   max_branches: int = 80) -> str:
    """Describe an ntuple you did not produce: its tree, entries, candidates
    per event, and branch names (filtered by a substring). Call this
    before writing selections for an unfamiliar file.

    Args:
        root_file: ROOT file under data/ (subdirectories allowed).
        pattern: optional substring to filter branch names, e.g. "Mbc",
            "mc", "ID", "roe".
        max_branches: cap on the number of branch names returned.
    """
    tree = _tree(root_file)
    names = _branches(root_file)
    sel = [n for n in names if pattern in n] if pattern else names
    lines = [f"tree '{_tree_name(root_file)}': {tree.num_entries} entries, "
             f"{len(names)} branches"]
    ev_keys = [k for k in ("__event__", "event") if k in names]
    if ev_keys and tree.num_entries:
        cols = [ev_keys[0]] + (["__run__"] if "__run__" in names else [])
        a = _load(root_file, cols)
        ev = a[ev_keys[0]].astype(np.int64)
        if "__run__" in a:
            ev = ev + a["__run__"].astype(np.int64) * 10**7
        n_ev = len(np.unique(ev))
        lines.append(f"unique events: {n_ev} -> {tree.num_entries / max(n_ev, 1):.2f} "
                     f"candidates per event on average")
    lines.append(f"branches{' matching ' + repr(pattern) if pattern else ''} "
                 f"({len(sel)}{', first ' + str(max_branches) if len(sel) > max_branches else ''}):")
    lines.append(", ".join(sel[:max_branches]))
    return "\n".join(lines)


@beta_tool
def plot_variable(root_files: list[str], variable: str, output_name: str,
                  selection: str = "1 == 1",
                  selections: list[str] | None = None,
                  labels: list[str] | None = None,
                  x_min: float = 0.0, x_max: float = 10.0, n_bins: int = 50) -> str:
    """Plot one ntuple variable for one or more samples (normalized overlay)
    and save it under plots/.

    Args:
        root_files: ROOT file names in data/, e.g. ["signal_taunu.root", "norm_lnu.root"].
        variable: branch name to plot, e.g. "m2miss".
        output_name: output PNG name, e.g. "m2miss_compare.png".
        selection: numpy boolean expression applied to every file.
        selections: optional per-curve selections (same length as root_files);
            overrides `selection` and allows overlaying different cuts on the
            SAME file, e.g. the two lepton flavors.
        labels: optional per-curve legend labels (same length as root_files).
        x_min: lower edge of the histogram.
        x_max: upper edge of the histogram.
        n_bins: number of bins.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if selections is not None and len(selections) != len(root_files):
        return "error: selections must have the same length as root_files"
    if labels is not None and len(labels) != len(root_files):
        return "error: labels must have the same length as root_files"
    PLOT_DIR.mkdir(exist_ok=True)
    bins = np.linspace(x_min, x_max, n_bins + 1)
    fig, ax = plt.subplots(figsize=(6.4, 4.4))
    for i, rf in enumerate(root_files):
        cut = selections[i] if selections is not None else selection
        t = _load_for(rf, cut, variable)
        mask = _apply_cut(t, cut)
        label = labels[i] if labels is not None else rf.replace(".root", "")
        ax.hist(t[variable][mask], bins=bins, histtype="step", lw=2,
                density=True, label=label)
    ax.set_xlabel(variable)
    ax.set_ylabel("normalized entries")
    ax.legend()
    fig.tight_layout()
    out = PLOT_DIR / _safe_name(output_name, ".png")
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return f"wrote {out.relative_to(REPO)}"


@beta_tool
def scan_cut(signal_file: str, background_files: list[str], variable: str,
             thresholds: list[float], direction: str = ">",
             base_selection: str = "1 == 1", best_by: str = "",
             count_events: bool = False, fom: str = "s_sqrt_sb",
             signal_weight: float = 1.0,
             background_weights: list[float] | None = None,
             sigma_b: float = 0.0, punzi_a: float = 3.0,
             fit_variable: str = "", fit_range: list[float] | None = None,
             n_bins: int = 20) -> str:
    """Scan a one-dimensional cut and report S, B and a figure of merit at
    each threshold, so the best working point can be chosen (cut & count
    policy: optimize one variable at a time on top of a fixed base
    selection). S and B are expected yields when weights are given
    (raw MC counts otherwise — then the FoM depends on the MC sample
    sizes, say so). Figures of merit (see docs/recipes):
      s_sqrt_sb  S/sqrt(S+B): statistics only (BF measurement, benchmark S)
      syst       S/sqrt(S+B+(sigma_b*B)^2): with a relative background
                 systematic sigma_b (the default of the BF recipe)
      punzi      eff/(a/2+sqrt(B)), eff relative to the signal file before
                 any cut; independent of the assumed signal (searches)
      asimov     1/sigma_mu from an Asimov template fit of fit_variable
                 (background uncertainty = MC stat (+) sigma_b*B); the most
                 faithful and the slowest; single bin when fit_variable is
                 empty.
    S/sqrt(S+B) is always printed next to the chosen FoM so the note can
    state how the optimum moves.

    Args:
        signal_file: ROOT file under data/ treated as signal (S).
        background_files: ROOT files under data/ treated as background (B);
            several files of one sample are simply summed.
        variable: branch name to cut on, e.g. "m2miss".
        thresholds: cut values to test, e.g. [0.5, 1.0, 1.5, 2.0].
        direction: ">" keeps variable > threshold, "<" keeps variable < threshold.
        base_selection: numpy boolean expression applied before the scan.
        best_by: optional expression (e.g. "abs(deltaE)"): keep one
            candidate per event, the lowest, among those passing base
            selection AND the scanned cut.
        count_events: count distinct events instead of candidates.
        fom: "s_sqrt_sb" (default), "syst", "punzi" or "asimov".
        signal_weight: expected-yield weight of the signal file.
        background_weights: per-file weights of background_files (default 1).
        sigma_b: relative systematic uncertainty on B (syst, asimov).
        punzi_a: the a in eff/(a/2+sqrt(B)): 3 for a limit, 5 for discovery.
        fit_variable: for asimov, the branch to histogram, e.g. "Mbc".
        fit_range: for asimov, [lo, hi] of fit_variable.
        n_bins: for asimov, number of bins of fit_variable.
    """
    if direction not in (">", "<"):
        return 'error: direction must be ">" or "<"'
    if fom not in ("s_sqrt_sb", "syst", "punzi", "asimov"):
        return "error: fom must be s_sqrt_sb, syst, punzi or asimov"
    if fom == "asimov" and fit_variable and not fit_range:
        return "error: asimov with fit_variable needs fit_range [lo, hi]"
    bw = list(background_weights or [1.0] * len(background_files))
    if len(bw) != len(background_files):
        return "error: background_weights must match background_files"
    extra = [fit_variable] if fit_variable else []
    sig = _load_for(signal_file, base_selection, variable, best_by or "", *extra)
    bkgs = [_load_for(b, base_selection, variable, best_by or "", *extra)
            for b in background_files]
    sig_base = _apply_cut(sig, base_selection)
    bkg_base = [_apply_cut(b, base_selection) for b in bkgs]
    sig_key = _event_key(sig, signal_file)
    bkg_keys = [_event_key(t, b) for t, b in zip(bkgs, background_files)]
    n_sig_total = (len(np.unique(sig_key)) if count_events and sig_key is not None
                   else len(sig[variable]))
    unit = "events" if count_events else "candidates"
    weighted = signal_weight != 1.0 or any(w != 1.0 for w in bw)
    head = (f"threshold  S  B  S/sqrt(S+B)"
            + (f"  {fom}" if fom != "s_sqrt_sb" else "")
            + f"   (base: {base_selection}; counting {unit}; "
            + ("expected yields" if weighted else
               "RAW MC counts, no weights — FoM depends on sample sizes")
            + (f"; sigma_b={sigma_b}" if fom in ("syst", "asimov") else "")
            + (f"; a={punzi_a}, eff relative to {n_sig_total} signal {unit}"
               if fom == "punzi" else "")
            + (f"; Asimov fit of {fit_variable or 'one bin'}" if fom == "asimov"
               else "") + ")")
    lines = [head]
    for thr in thresholds:
        def keep_mask(t, base):
            var = t[variable]
            return base & (var > thr if direction == ">" else var < thr)

        def count(t, keep, key):
            if count_events and key is not None:
                return len(np.unique(key[keep]))
            return int(keep.sum())
        ks = _best_per_event(sig, keep_mask(sig, sig_base), best_by, sig_key)
        kb = [_best_per_event(t, keep_mask(t, m), best_by, k)
              for t, m, k in zip(bkgs, bkg_base, bkg_keys)]
        s_raw = count(sig, ks, sig_key)
        b_raw = [count(t, k, key) for t, k, key in zip(bkgs, kb, bkg_keys)]
        S = s_raw * signal_weight
        B = sum(n * w for n, w in zip(b_raw, bw))
        B_stat = np.sqrt(sum(n * w * w for n, w in zip(b_raw, bw)))
        base_fom = S / np.sqrt(S + B) if S + B > 0 else 0.0
        if fom == "syst":
            val = S / np.sqrt(S + B + (sigma_b * B) ** 2) if S + B > 0 else 0.0
        elif fom == "punzi":
            eff = s_raw / n_sig_total if n_sig_total else 0.0
            val = eff / (punzi_a / 2 + np.sqrt(B))
        elif fom == "asimov":
            if fit_variable:
                bins = np.linspace(fit_range[0], fit_range[1], n_bins + 1)
                Sh = np.histogram(sig[fit_variable][ks], bins)[0] * signal_weight
                Bh = np.zeros(n_bins)
                Bv = np.zeros(n_bins)
                for t, k, w in zip(bkgs, kb, bw):
                    h = np.histogram(t[fit_variable][k], bins)[0]
                    Bh += h * w
                    Bv += h * w * w
            else:
                Sh, Bh, Bv = (np.array([S]), np.array([B]),
                              np.array([B_stat ** 2]))
            sigma_mu = _asimov_sigma_mu(Sh, Bh, np.sqrt(Bv + (sigma_b * Bh) ** 2))
            val = 1.0 / sigma_mu if sigma_mu and np.isfinite(sigma_mu) else 0.0
        else:
            val = base_fom
        fmt = (lambda x: f"{x:.1f}") if weighted else (lambda x: f"{x:.0f}")
        line = (f"{variable} {direction} {thr}: S={fmt(S)} B={fmt(B)}"
                f" S/sqrt(S+B)={base_fom:.2f}")
        if fom != "s_sqrt_sb":
            line += f" {fom}={val:.3g}"
        lines.append(line)
    return "\n".join(lines)


def _asimov_sigma_mu(S, B, unc) -> float:
    """Expected uncertainty on the signal strength mu from an Asimov fit
    (data = S + B) of one channel with per-bin background uncertainties."""
    import pyhf
    pyhf.set_backend("numpy", "minuit")
    floor = 1e-6
    S = np.maximum(np.asarray(S, float), 0.0)
    B = np.maximum(np.asarray(B, float), floor)
    unc = np.maximum(np.asarray(unc, float), floor)
    if S.sum() <= 0:
        return float("inf")
    model = pyhf.Model({"channels": [{"name": "c", "samples": [
        {"name": "signal", "data": S.tolist(),
         "modifiers": [{"name": "mu", "type": "normfactor", "data": None}]},
        {"name": "background", "data": B.tolist(),
         "modifiers": [{"name": "ub", "type": "shapesys",
                        "data": unc.tolist()}]}]}]}, poi_name="mu")
    data = np.concatenate([S + B, model.config.auxdata])
    r = np.asarray(pyhf.infer.mle.fit(data, model, return_uncertainties=True))
    return float(r[model.config.poi_index][1])


@beta_tool
def read_references() -> str:
    """Read the curated summaries of the published reference analyses
    (variables, selections, control regions, note conventions). Call this
    at the PLAN stage, before designing any selection, and cite the papers
    it lists in your plan and note."""
    return (REPO / "docs" / "references.md").read_text()


@beta_tool
def read_recipe(name: str = "") -> str:
    """Read an analysis recipe (docs/recipes/<name>.md): the generalized
    strategy for one kind of measurement, with the seven specification
    fields and their defaults. Call with no name to get the index and
    the specification format, then with the recipe named in the task
    (or the one that fits the goal). Fill every field in your plan.

    Args:
        name: recipe name, e.g. "bf_measurement", "ratio_measurement",
            "search", "cutflow_reproduction"; empty for the index.
    """
    rdir = REPO / "docs" / "recipes"
    if name and not name.endswith(".md"):
        name += ".md"
    if name and not _NAME_RE.match(name):
        return f"error: invalid recipe name {name!r}"
    path = rdir / (name or "README.md")
    if not path.exists():
        names = sorted(p.stem for p in rdir.glob("*.md") if p.stem != "README")
        return f"error: no recipe '{name}'; available: {', '.join(names)}"
    return path.read_text()


@beta_tool
def read_selection(name: str) -> str:
    """Read a reference selection file (docs/selections/<name>.yaml) for
    selection Mode 1: the cuts in order, per-channel branch substitutions,
    the best-candidate rule, the signal box and, when known, the
    reference cutflow. Apply the cuts exactly as written.

    Args:
        name: file name, e.g. "kstll_reference_ntuple_plots.yaml".
    """
    if not name.endswith(".yaml"):
        name += ".yaml"
    if not _NAME_RE.match(name):
        return f"error: invalid selection file name {name!r}"
    path = REPO / "docs" / "selections" / name
    if not path.exists():
        avail = sorted(p.name for p in path.parent.glob("*.yaml"))
        return f"error: no selection file '{name}'; available: {', '.join(avail)}"
    return path.read_text()


@beta_tool
def read_note_template() -> str:
    """Read the fixed analysis-note template (section skeleton modelled on
    a Belle II paper, plus the agent-specific provenance section, and the
    tables/figures each section must contain). Call this before writing
    the note; save_note rejects notes that deviate from it."""
    return (REPO / "docs" / "note_template.md").read_text()


_NOTE_SECTIONS = [
    ("introduction", "1 Introduction"),
    ("detector", "2 Detector model and samples"),
    ("selection", "3 Event selection and reconstruction"),
    ("background", "4 Background estimation and suppression"),
    ("yield", "5 Signal yield extraction"),
    ("systematic", "6 Efficiency corrections and systematic uncertainties"),
    ("results", "7 Results and summary"),
    ("discussion", "8 Discussion"),
    ("provenance", "9 Analysis provenance"),
    ("references", "10 References"),
]
_NEEDS_TABLE_OR_FIGURE = {"detector", "selection", "background", "yield",
                          "systematic", "results"}


_JARGON_PATTERNS = [
    (r"`[^`\n]+`", "code span"),
    (r"(?<!\()\b[\w./-]+\.(root|py|dec|json|txt|tex|md)\b", "file name"),
    (r"\b(data|plots|notes|docs|fastsim|generation|analysis)/[\w./-]*",
     "path"),
    (r"\b(query_ntuple|scan_cut|plot_stacked|plot_variable|fit_templates|"
     r"inspect_ntuple|list_samples|list_branches|make_ntuple|generate_mc|"
     r"generate_continuum|apply_systematics|save_note|read_references|"
     r"read_note_template|best_by|post_selection|group_by|split_by|"
     r"root_files|isSignal|mcErrors|__event__|__run__)\b", "tool/branch name"),
]


def _check_note_register(content: str, heads: list, lines: list) -> list:
    """Technical identifiers in the paper-register part (Abstract and
    sections 1-8). Image embeds are exempt (their link target is a path)."""
    stop = [i for i, l in heads if "provenance" in l.lower()]
    end = stop[0] if stop else len(lines)
    body = "\n".join(lines[:end])
    body = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", body)   # image embeds
    body = re.sub(r"^#.*$", "", body, flags=re.M)             # headers
    hits = []
    for pat, kind in _JARGON_PATTERNS:
        for m in re.finditer(pat, body):
            tok = m.group(0)
            if tok not in [h[1] for h in hits]:
                hits.append((kind, tok))
    if not hits:
        return []
    shown = ", ".join(f"{t} ({k})" for k, t in hits[:8])
    more = f" and {len(hits) - 8} more" if len(hits) > 8 else ""
    return [f"sections 1-8 must be in paper register (physics names only; "
            f"branch/file/tool names belong in section 9 Analysis "
            f"provenance) but contain: {shown}{more}"]


def _check_table_captions(lines: list) -> list:
    """Every Markdown table must have a 'Table N.' caption line immediately
    above it (table captions go above, figure captions below)."""
    bad = []
    for i, l in enumerate(lines):
        if not (l.startswith("|") and i + 1 < len(lines)
                and re.match(r"^\|\s*:?-", lines[i + 1])):
            continue                      # not a table header row
        j = i - 1
        while j >= 0 and not lines[j].strip():
            j -= 1
        if j < 0 or not re.match(r"^\**\s*Table\s+\d+", lines[j].strip(),
                                 re.I):
            bad.append(i + 1)
    if not bad:
        return []
    return [f"table(s) starting at line(s) {bad[:6]} have no '**Table N.** "
            "...' caption line immediately above them (table captions go "
            "above the table, figure captions below the figure)"]


def _check_note_structure(content: str) -> list:
    """Problems with the note's structure (empty list = conforms)."""
    problems = []
    lines = content.splitlines()
    heads = [(i, l) for i, l in enumerate(lines) if l.startswith("## ")]
    problems += _check_note_register(content, heads, lines)
    problems += _check_table_captions(lines)
    if not re.search(r"^##\s*Abstract", content, re.M):
        problems.append("missing '## Abstract' before section 1")
    pos = []
    for key, title in _NOTE_SECTIONS:
        hit = [i for i, l in heads if key in l.lower()]
        if not hit:
            problems.append(f"missing section '## {title}'")
            pos.append(None)
        else:
            pos.append(hit[0])
    found = [p for p in pos if p is not None]
    if found != sorted(found):
        problems.append("sections are not in the template order")
    for (key, title), start in zip(_NOTE_SECTIONS, pos):
        if start is None or key not in _NEEDS_TABLE_OR_FIGURE:
            continue
        end = min([i for i, _ in heads if i > start] + [len(lines)])
        body = "\n".join(lines[start:end])
        has_table = re.search(r"^\|.*\|\s*$", body, re.M) is not None
        has_fig = "![" in body
        if not (has_table or has_fig):
            problems.append(f"section '{title}' has neither a table nor a figure")
    return problems


@beta_tool
def read_note(name: str) -> str:
    """Read back a previously saved analysis note from notes/, e.g. to
    amend it with a new section before saving it again.

    Args:
        name: file name, e.g. "dsttaunu_note_agent.md".
    """
    path = NOTES_DIR / _safe_name(name, ".md")
    if not path.exists():
        return f"error: notes/{name} does not exist"
    return path.read_text()


@beta_tool
def save_note(name: str, content: str) -> str:
    """Save the final analysis note as a Markdown file under notes/
    (kept out of git). Call this once, as the last step of an analysis,
    with the full note following docs/note_template.md (read it with
    read_note_template): Abstract, then the ten fixed sections 1
    Introduction ... 10 References, sections 2-7 each containing at
    least one table or figure. Non-conforming notes are rejected.

    Args:
        name: file name, e.g. "dsttaunu_bf_note.md".
        content: the complete note in Markdown. Reference plots by their
            paths under plots/ and put every number in a table.
    """
    problems = _check_note_structure(content)
    if problems:
        return ("note REJECTED — it does not follow docs/note_template.md "
                "(call read_note_template): " + "; ".join(problems)
                + ". Fix the structure and call save_note again.")
    NOTES_DIR.mkdir(exist_ok=True)
    out = NOTES_DIR / _safe_name(name, ".md")
    # web_search results carry <cite index="..."> markup; it must not leak
    # into the note (keep the quoted text, drop the tags)
    content = re.sub(r"\(?<?cite index=\"[^\"]*\">", "", content)
    content = content.replace("</cite>", "")
    out.write_text(content)
    return f"wrote notes/{out.name} ({len(content)} chars)"




BRANCH_LABELS = {
    "m_visible": r"$m(K\pi)$ [GeV]",
    "mbc": r"$M_{\mathrm{bc}}$ [GeV]",
    "delta_e": r"$\Delta E$ [GeV]",
    "m_ll": r"$m(\ell\ell)$ [GeV]",
    "m_d0": r"$m(K\pi)$ [GeV]",
    "delta_m": r"$\Delta m$ [GeV]",
    "r2": r"$R_2$",
    "e_tag_cm": r"$E_{\mathrm{tag}}^{\mathrm{CM}}$ [GeV]",
    "m2miss": r"$m^2_{\mathrm{miss}}$ [GeV$^2$]",
    "q2": r"$q^2$ [GeV$^2$]",
    "p_lep_cm": r"$p^{*}_{\ell}$ [GeV]",
}


@beta_tool
def plot_stacked(root_files: list[str], weights: list[float], variable: str,
                 output_name: str, selection: str = "1 == 1",
                 x_min: float = 0.0, x_max: float = 10.0, n_bins: int = 40,
                 cut_lines: list[float] | None = None,
                 sample_labels: list[str] | None = None,
                 x_label: str = "", log_y: bool = False,
                 split_by: str = "",
                 split_labels: list[str] | None = None,
                 best_by: str = "", post_selection: str = "") -> str:
    """Publication-style stacked histogram of one variable with optional
    vertical cut lines. Use this for the note figures: preselection
    windows, discriminating variables, control regions. The stack is
    split, in order of preference: by the values of `split_by` (any
    branch, e.g. isSignal or a truth code); else by this framework's
    true_mode x lepton truth when present; else one component per input
    sample (files sharing a sample_label are merged).

    Args:
        root_files: ntuple files in data/ forming the dataset.
        weights: per-file luminosity weights (same length as root_files).
        variable: branch to plot.
        output_name: output PNG under plots/.
        selection: numpy boolean expression applied first.
        x_min: lower histogram edge.
        x_max: upper histogram edge.
        n_bins: number of bins.
        cut_lines: optional x positions for dashed cut indicators.
        sample_labels: legend labels for the per-file stacks (no-truth
            ntuples only; same length/order as root_files; matplotlib
            mathtext allowed). Default: the file names.
        x_label: x-axis label (mathtext allowed); common branches get a
            physics label with units automatically.
        log_y: log y scale — use it whenever components differ by orders
            of magnitude, so the small ones stay visible.
        split_by: optional branch name to split the stack by its values
            (e.g. "isSignal"); values are pooled across all files.
        split_labels: optional legend labels for split_by values, as
            "value=label" strings, e.g. ["1=signal", "0=background"].
        best_by: optional expression (e.g. "abs(deltaE)"): keep one
            candidate per event, the lowest, among those passing the
            selection.
        post_selection: optional expression applied after the
            best-candidate choice (e.g. a signal box).
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    if len(weights) != len(root_files):
        return "error: weights must match root_files"
    if sample_labels and len(sample_labels) != len(root_files):
        return "error: sample_labels must match root_files"
    comps = {0: ("other $B$ decays", "#bdbdbd"),
             2: (r"$B \to D^{*}\ell\nu$", "#64b5f6"),
             3: (r"continuum $q\bar q$", "#c9a227"),
             None: ("fake lepton", "#8d6e63"),
             1: (r"signal", "crimson")}
    file_colors = ["#bdbdbd", "#64b5f6", "#c9a227", "#8d6e63", "crimson",
                   "#7e57c2", "#26a69a", "#ef6c00"]
    bins = np.linspace(x_min, x_max, n_bins + 1)
    vals, ws, labs, cols = [], [], [], []
    have_truth = (not split_by) and all("true_mode" in _branches(rf)
                                        for rf in root_files)
    if split_by:
        lab_map = {}
        for item in (split_labels or []):
            k, _, v = item.partition("=")
            lab_map[float(k)] = v
        pooled: dict = {}
        for rf, wt in zip(root_files, weights):
            t = _load_for(rf, selection, variable, split_by, best_by or "", post_selection or "")
            m = _best_per_event(t, _apply_cut(t, selection), best_by, _event_key(t, rf))
            if post_selection:
                m = m & _apply_cut(t, post_selection)
            keyv = t[split_by][m]
            for val in np.unique(keyv[~np.isnan(keyv)] if keyv.dtype.kind == "f" else keyv):
                sel = m.copy()
                sel[m] = keyv == val
                g = pooled.setdefault(float(val), [0.0, [], []])
                g[0] += float(sel.sum() * wt)
                g[1].append(t[variable][sel])
                g[2].append(np.full(int(sel.sum()), wt))
        ordered = sorted(pooled.items(), reverse=True, key=lambda kv: kv[1][0])
        for i, (val, (_, v, w)) in enumerate(ordered[:8]):
            vals.append(np.concatenate(v))
            ws.append(np.concatenate(w))
            labs.append(lab_map.get(val, f"{split_by} = {val:g}"))
            cols.append(file_colors[i % len(file_colors)])
    elif have_truth:
        for mode, (lab, col) in comps.items():
            v, w = [], []
            for rf, wt in zip(root_files, weights):
                t = _load_for(rf, selection, variable, "true_mode", "lep_true_pid", best_by or "", post_selection or "")
                m = _best_per_event(t, _apply_cut(t, selection), best_by, _event_key(t, rf))
                if post_selection:
                    m = m & _apply_cut(t, post_selection)
                lep_ok = np.isin(np.abs(t.get("lep_true_pid",
                                              t["true_mode"] * 0 + 13)),
                                 (11, 13))
                if mode is None:
                    m = m & ~lep_ok
                else:
                    m = m & (t["true_mode"] == mode) & lep_ok
                v.append(t[variable][m])
                w.append(np.full(int(m.sum()), wt))
            if v and sum(len(x) for x in v):
                vals.append(np.concatenate(v))
                ws.append(np.concatenate(w))
                labs.append(lab)
                cols.append(col)
    else:
        # no true_mode branch (exclusive ntuples): the truth label is the
        # sample itself, so stack one component per input file, largest
        # yield at the bottom, labeled by the file name
        groups = {}  # label -> [yield, values, weights] (files merged)
        for i, (rf, wt) in enumerate(zip(root_files, weights)):
            t = _load_for(rf, selection, variable, best_by or "", post_selection or "")
            m = _best_per_event(t, _apply_cut(t, selection), best_by, _event_key(t, rf))
            if post_selection:
                m = m & _apply_cut(t, post_selection)
            lab = sample_labels[i] if sample_labels else Path(rf).stem
            g = groups.setdefault(lab, [0.0, [], []])
            g[0] += float(m.sum() * wt)
            g[1].append(t[variable][m])
            g[2].append(np.full(int(m.sum()), wt))
        ordered = sorted(groups.items(), reverse=True, key=lambda kv: kv[1][0])
        for i, (lab, (_, v, w)) in enumerate(ordered):
            v = np.concatenate(v)
            if len(v):
                vals.append(v)
                ws.append(np.concatenate(w))
                labs.append(lab)
                cols.append(file_colors[i % len(file_colors)])
    PLOT_DIR.mkdir(exist_ok=True)
    fig, ax = plt.subplots(figsize=(6.6, 4.4))
    if vals:
        ax.hist(vals, bins=bins, weights=ws, stacked=True,
                color=cols, label=labs)
    for x in (cut_lines or []):
        ax.axvline(x, color="k", ls="--", lw=1.2)
    ax.set_xlabel(x_label or BRANCH_LABELS.get(variable, variable))
    ax.set_ylabel("candidates / bin (weighted)")
    if log_y:
        ax.set_yscale("log")
    ax.legend(fontsize=8)
    fig.tight_layout()
    out = PLOT_DIR / _safe_name(output_name, ".png")
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return f"wrote plots/{out.name}"


@beta_tool
def fit_templates(data_files: list[str], weights: list[float], variable: str,
                  signal_selection: str, output_name: str,
                  selection: str = "1 == 1",
                  x_min: float = -2.0, x_max: float = 10.0, n_bins: int = 24,
                  split_by_flavor: bool = True,
                  bkg_syst: float = 0.10,
                  lumi_projection: bool = False,
                  dataset_lumi_invab: float = 0.000906,
                  channels: list[str] | None = None,
                  best_by: str = "", post_selection: str = "") -> str:
    """Generic binned maximum-likelihood template fit (pyhf + MINUIT) of
    mu x S + B in one variable. S is the truth-labeled signal component of
    the dataset (signal_selection), B is everything else; per-bin background
    uncertainties are MC statistics (+) bkg_syst x B. With
    split_by_flavor, the electron and muon channels are fit simultaneously
    sharing mu (the practice of the published analyses). Returns mu with
    its uncertainty, per-channel standalone fits, and writes the post-fit
    plot. Multiply mu by the generator-truth BF to quote a branching
    fraction.

    Args:
        data_files: ntuple files in data/ forming the dataset.
        weights: per-file luminosity weights (same length as data_files).
        variable: branch to histogram, e.g. "m2miss".
        signal_selection: truth expression defining S, e.g.
            "(true_mode==1) & (abs(lep_true_pid)==13)"; for exclusive
            ntuples without true_mode, use the sample label instead,
            e.g. "mode_id == 1".
        output_name: post-fit PNG name under plots/.
        selection: preselection applied to everything.
        x_min: histogram lower edge.
        x_max: histogram upper edge.
        n_bins: number of bins.
        split_by_flavor: simultaneous e/mu channels sharing mu, using
            the lep_flavor branch of this framework's ntuples (ignored
            when the files have no such branch).
        channels: generic alternative: a list of "name=selection"
            strings defining the simultaneous channels, e.g.
            ["e=e1_B0_E > 0", "mu=mu1_B0_E > 0"] or
            ["ee=lep_flavor == 11", "mumu=lep_flavor == 13"]; each file
            contributes to a channel only where the branches exist.
        best_by: optional expression (e.g. "abs(deltaE)"): keep one
            candidate per event, the lowest, among those passing the
            selection (and the channel selection), before histogramming.
        post_selection: optional expression applied after the
            best-candidate choice.
        bkg_syst: relative background normalization uncertainty per bin.
        lumi_projection: also compute the statistical-only Asimov expected
            precision at 0.1, 0.36, 1, 5 and 50 ab^-1 (background shapes
            treated as known) and save a projection plot.
        dataset_lumi_invab: integrated luminosity of the dataset in ab^-1.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pyhf
    if len(weights) != len(data_files):
        return "error: weights must match data_files"
    bins = np.linspace(x_min, x_max, n_bins + 1)
    floor = 1e-3

    def build(chan_sel):
        S = np.zeros(n_bins); B = np.zeros(n_bins)
        Bv = np.zeros(n_bins); D = np.zeros(n_bins)
        for rf, wt in zip(data_files, weights):
            if chan_sel:
                needed = set(_known_free_symbols([chan_sel]))
                if not needed <= set(_branches(rf)):
                    continue  # this file has no such channel
            t = _load_for(rf, selection, signal_selection, variable, chan_sel or "", best_by or "", post_selection or "")
            m = _apply_cut(t, selection)
            if chan_sel:
                m = m & _apply_cut(t, chan_sel)
            m = _best_per_event(t, m, best_by, _event_key(t, rf))
            if post_selection:
                m = m & _apply_cut(t, post_selection)
            is_sig = m & _apply_cut(t, signal_selection)
            S += wt * np.histogram(t[variable][is_sig], bins=bins)[0]
            hb = np.histogram(t[variable][m & ~is_sig], bins=bins)[0]
            B += wt * hb
            Bv += wt * wt * hb
            D += wt * np.histogram(t[variable][m], bins=bins)[0]
        B = np.maximum(B, floor)
        unc = np.maximum(np.sqrt(Bv + (bkg_syst * B) ** 2), floor)
        return S, B, unc, D

    def spec(name, S, B, unc):
        return {"name": name, "samples": [
            {"name": "signal", "data": S.tolist(), "modifiers":
             [{"name": "mu", "type": "normfactor", "data": None}]},
            {"name": "background", "data": B.tolist(), "modifiers":
             [{"name": f"ub_{name}", "type": "shapesys",
               "data": unc.tolist()}]}]}

    pyhf.set_backend("numpy", "minuit")
    if channels:
        chans = [(c.partition("=")[2].strip(), c.partition("=")[0].strip())
                 for c in channels]
    elif split_by_flavor and all("lep_flavor" in _branches(rf)
                                 for rf in data_files):
        chans = [("lep_flavor == 11", "e"), ("lep_flavor == 13", "mu")]
    else:
        chans = [(None, "all")]
    parts = {n: build(f) for f, n in chans}
    model = pyhf.Model({"channels": [spec(n, S, B, u)
                                     for n, (S, B, u, D) in parts.items()]},
                       poi_name="mu")
    data = np.concatenate([parts[c][3] for c in model.config.channels]
                          + [model.config.auxdata])
    r = np.asarray(pyhf.infer.mle.fit(data, model, return_uncertainties=True))
    mu, err = r[model.config.poi_index]
    lines = [f"simultaneous fit: mu = {mu:.3f} +- {err:.3f} "
             f"(multiply by the generator-truth BF for the measured BF)"]
    for n, (S, B, u, D) in parts.items():
        m1 = pyhf.Model({"channels": [spec(n + "_solo", S, B, u)]},
                        poi_name="mu")
        r1 = np.asarray(pyhf.infer.mle.fit(
            np.concatenate([D, m1.config.auxdata]), m1,
            return_uncertainties=True))
        lines.append(f"  {n}-only: mu = {r1[m1.config.poi_index][0]:.3f} "
                     f"+- {r1[m1.config.poi_index][1]:.3f}")
    centers = 0.5 * (bins[:-1] + bins[1:])
    width = np.diff(bins)
    fig, axes = plt.subplots(1, len(parts), figsize=(5.6 * len(parts), 4.2),
                             squeeze=False)
    for ax, (n, (S, B, u, D)) in zip(axes[0], parts.items()):
        ax.bar(centers, B, width=width, color="#bdbdbd", label="background")
        ax.bar(centers, mu * S, width=width, bottom=B, color="crimson",
               label=rf"$\mu\times$signal")
        ax.errorbar(centers, D, yerr=np.sqrt(np.maximum(D, 1)), fmt="ko",
                    ms=3, lw=1, label="data")
        ax.set_xlabel(variable)
        ax.set_title(n, fontsize=10)
        ax.set_yscale("log")
    axes[0][0].legend(fontsize=8)
    fig.tight_layout()
    PLOT_DIR.mkdir(exist_ok=True)
    out = PLOT_DIR / _safe_name(output_name, ".png")
    fig.savefig(out, dpi=150)
    plt.close(fig)
    lines.append(f"post-fit plot: plots/{out.name}")

    if lumi_projection:
        lumis = np.array([0.1, 0.36, 1.0, 5.0, 50.0])
        S0 = np.concatenate([parts[c][0] for c in model.config.channels])
        B0 = np.concatenate([parts[c][1] for c in model.config.channels])
        rels = []
        for L in lumis:
            k = L / dataset_lumi_invab
            Bk = np.maximum(k * B0, floor)
            mk = pyhf.simplemodels.uncorrelated_background(
                signal=(k * S0).tolist(), bkg=Bk.tolist(),
                bkg_uncertainty=np.maximum(1e-3 * Bk, floor).tolist())
            asimov = np.asarray(mk.expected_data(
                pyhf.tensorlib.astensor([1.0] * (1 + len(B0)))))
            rk = np.asarray(pyhf.infer.mle.fit(asimov, mk,
                                               return_uncertainties=True))
            rels.append(float(rk[mk.config.poi_index][1]))
        lines.append("statistical-only Asimov projection "
                     "(background shape treated as known):")
        for L, r in zip(lumis, rels):
            lines.append(f"  L = {L:g} /ab: expected rel. precision "
                         f"= {r*100:.1f}%")
        figp, axp = plt.subplots(figsize=(5.8, 4.0))
        axp.loglog(lumis, np.array(rels) * 100, "o-", color="#5c7fb8")
        axp.axvline(dataset_lumi_invab, color="gray", ls=":", lw=1)
        axp.set_xlabel(r"integrated luminosity [ab$^{-1}$]")
        axp.set_ylabel(r"expected $\delta\mu/\mu$ [%]")
        axp.grid(alpha=0.3, which="both")
        figp.tight_layout()
        proj = PLOT_DIR / ("projection_" + _safe_name(output_name, ".png"))
        figp.savefig(proj, dpi=150)
        plt.close(figp)
        lines.append(f"projection plot: plots/{proj.name}")
    return "\n".join(lines)


@beta_tool
def save_note_latex(name: str, content: str) -> str:
    """Save the final TYPESET version of an approved note as LaTeX and
    compile it to PDF (xelatex, two passes). Call this only AFTER the
    Markdown note has been accepted by save_note. The content must be a
    complete, compilable .tex document (documentclass article; use
    booktabs tables, numbered figure floats with descriptive captions,
    \tableofcontents, the abstract, and the title block with the
    public-materials disclaimer; figures are available under ../plots/).
    Every table must fit the text width (\\small/\\footnotesize, short
    labels, resizebox or tabularx for wide ones); overfull boxes are
    reported back. Table captions go ABOVE the tabular, figure captions
    BELOW the graphic; floats without a caption are rejected.
    On compile errors the error lines are returned so you can fix the
    LaTeX and call again.

    Args:
        name: file name, e.g. "dsttaunu_note.tex".
        content: the complete LaTeX source.
    """
    caps = _check_latex_captions(content)
    if caps:
        return ("LaTeX REJECTED — fix the floats and call again: "
                + "; ".join(caps))
    NOTES_DIR.mkdir(exist_ok=True)
    out = NOTES_DIR / _safe_name(name, ".tex")
    out.write_text(content)
    for _ in range(2):
        proc = subprocess.run(
            ["xelatex", "-interaction=nonstopmode", out.name],
            capture_output=True, text=True, timeout=300, cwd=NOTES_DIR)
    if proc.returncode != 0:
        errs = [l for l in proc.stdout.splitlines() if l.startswith("!")]
        return ("compile FAILED — fix the LaTeX and call again:\n"
                + "\n".join(errs[:10]))
    msg = f"wrote notes/{out.name} and compiled notes/{out.stem}.pdf"
    wide = _overfull_boxes(NOTES_DIR / f"{out.stem}.log")
    if wide:
        msg += (f"\nWARNING: {len(wide)} overfull line(s)/table(s) wider than "
                "the text block: " + "; ".join(wide[:6]) + ". Make the "
                "tables fit (\\small or \\footnotesize, shorter row labels "
                "with abbreviations defined in the caption, "
                "\\resizebox{\\textwidth}{!}{...} or tabularx for wide "
                "ones, p{} columns for long text) and call save_note_latex "
                "again once; if the warning persists after that, accept it.")
    return msg


def _check_latex_captions(tex: str) -> list:
    """Table captions must precede the tabular, figure captions must follow
    the graphic, and every float needs a caption."""
    problems = []
    for kind, inner, where, shown in (
            ("table", r"\\begin\{tabular", "BEFORE", "\\begin{tabular}"),
            ("figure", r"\\includegraphics", "AFTER", "\\includegraphics")):
        envs = re.findall(r"\\begin\{%s\*?\}.*?\\end\{%s\*?\}"
                          % (kind, kind), tex, re.S)
        missing, wrong = [], []
        for n, env in enumerate(envs, 1):
            c = env.find("\\caption")
            m = re.search(inner, env)
            if c < 0:
                missing.append(n)
            elif m and ((c > m.start()) if where == "BEFORE"
                        else (c < m.start())):
                wrong.append(n)
        if missing:
            problems.append(f"{kind}(s) {missing} have no \\caption")
        if wrong:
            problems.append(f"{kind}(s) {wrong}: \\caption must come {where} "
                            f"{shown} ({kind} captions go "
                            f"{'above' if where == 'BEFORE' else 'below'})")
    return problems


def _overfull_boxes(log_path, min_pt: float = 10.0) -> list:
    """'Overfull \\hbox (Npt too wide)' entries wider than min_pt."""
    try:
        text = log_path.read_text(errors="replace")
    except OSError:
        return []
    out = []
    for m in re.finditer(r"Overfull \\hbox \(([\d.]+)pt too wide\)[^\n]*",
                         text):
        if float(m.group(1)) >= min_pt:
            where = re.search(r"lines? ([\d-]+)", m.group(0))
            out.append(f"{float(m.group(1)):.0f}pt at lines "
                       f"{where.group(1) if where else '?'}")
    return out


def _systematics_table(table: str) -> dict:
    import json
    return json.loads((SYST_DIR / _safe_name(table, ".json")).read_text())


@beta_tool
def apply_systematics(table: str, mode: str, value: float, stat: float,
                      evaluated: dict[str, float] | None = None) -> str:
    """Attach systematic uncertainties to a result, from a published
    systematics table (systematics/*.json) plus any sources you evaluated
    yourself on MC. Returns the result with stat and syst uncertainties and
    a Markdown breakdown table (with the origin of every entry) to put in
    the note. Sources are combined in quadrature; tracking is 0.3% per
    charged track added linearly, as in the published analysis.

    Args:
        table: table file in systematics/, e.g. "belle2_kstll_2206.05946.json".
        mode: decay-mode key in that table (an unknown key lists the valid ones).
        value: central value of the result, e.g. a branching fraction.
        stat: its statistical uncertainty, in the same units.
        evaluated: optional relative uncertainties in percent that you
            evaluated yourself on MC, keyed by source id (e.g.
            {"pdf_shape": 0.7}). Allowed only for sources marked
            mc_evaluable in the table; they replace the published values.
    """
    from math import sqrt
    data = _systematics_table(table)
    modes, sources = data["modes"], data["sources"]
    if mode not in modes:
        return (f"error: unknown mode {mode!r}; valid modes: "
                + ", ".join(modes))
    evaluated = evaluated or {}
    bad = [k for k in evaluated
           if not sources.get(k, {}).get("mc_evaluable")]
    if bad:
        ok = [k for k, s in sources.items() if s.get("mc_evaluable")]
        return (f"error: {bad} cannot be replaced by an MC evaluation; "
                f"mc_evaluable sources are {ok}")
    m = modes[mode]
    rows, up2, dn2 = [], 0.0, 0.0
    for sid in m["sources"]:
        s = sources[sid]
        if "per_track" in s:
            up = dn = s["per_track"] * m["n_tracks"]
            origin = (f"published ({s['per_track']}% x {m['n_tracks']} "
                      "tracks, linear)")
        elif sid in evaluated:
            up = dn = float(evaluated[sid])
            origin = "evaluated on MC (this analysis)"
        else:
            up, dn = s["up"], s.get("down", s["up"])
            origin = "published" + (" — placeholder" if s.get("placeholder")
                                    else "")
        up2, dn2 = up2 + up * up, dn2 + dn * dn
        rows.append(f"| {s['label']} | +{up:.2g} | -{dn:.2g} | {origin} |")
    tot_up, tot_dn = sqrt(up2), sqrt(dn2)
    lines = [
        f"{mode}: {value:.4g} ± {stat:.2g} (stat) "
        f"+{value * tot_up / 100:.2g} -{value * tot_dn / 100:.2g} (syst)",
        f"total syst: +{tot_up:.2g}% / -{tot_dn:.2g}% "
        f"(source: {data['citation']})",
        "",
        "| Source | + (%) | - (%) | Origin |",
        "|---|---|---|---|",
        *rows,
        f"| **Total** | +{tot_up:.2g} | -{tot_dn:.2g} | quadrature |",
    ]
    placeholders = [sources[sid]["label"] for sid in m["sources"]
                    if sources[sid].get("placeholder") and sid not in evaluated]
    if placeholders:
        lines.append("")
        lines.append("Placeholders (published values for a different "
                     "selection; state this in the note): "
                     + ", ".join(placeholders))
    return "\n".join(lines)


ANALYSIS_TOOLS = [read_references, read_recipe, read_selection,
                  read_note_template, list_samples, inspect_ntuple,
                  list_branches, list_decay_modes, generate_mc,
                  generate_continuum, make_ntuple, query_ntuple,
                  plot_variable, plot_stacked, scan_cut, fit_templates,
                  apply_systematics, read_note, save_note, save_note_latex]
