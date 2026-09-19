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
NOTES_DIR = REPO / "notes"
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
            Available branches: m2miss, m2miss_roe, e_tag_cm, m_tag, n_roe,
            q_roe, plep_star, q2, m_d0, delta_m, cos_by, r2, p_lep_lab,
            costh_lep_lab, p_dst_lab, m2miss_true, plep_star_true, q2_true,
            true_mode (1 = D* tau nu, 2 = D* l nu, 0 = other B, 3 = continuum),
            lep_true_pid (true PDG id of the lepton candidate),
            lep_flavor (reconstructed: 11 = e, 13 = mu), mode_id, event.
            Ntuples from make_ntuple_exclusive.py instead carry: m2miss,
            plep_star, q2, m_visible, mbc, delta_e, m_ll, r2, e_tag_cm,
            m_tag, n_roe, q_roe, n_tracks, n_photons, n_mu, lep_flavor,
            mode_id, event (no true_mode).
    """
    t = _load(root_file)
    mask = _apply_cut(t, selection)
    parts = [f"total: {len(mask)}", f"pass: {int(mask.sum())}"]
    if "true_mode" in t:
        for mode, label in [(1, "true D*taunu"), (2, "true D*lnu"),
                            (0, "true other B"), (3, "continuum")]:
            n = int((mask & (t["true_mode"] == mode)).sum())
            if n:
                parts.append(f"{label}: {n}")
    return ", ".join(parts)


@beta_tool
def plot_variable(root_files: list[str], variable: str, output_name: str,
                  selection: str = "m2miss > -999",
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
        t = _load(rf)
        cut = selections[i] if selections is not None else selection
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
             base_selection: str = "m2miss > -999") -> str:
    """Scan a one-dimensional cut and report S, B and S/sqrt(S+B) at each
    threshold, so the best working point can be chosen (cut & count policy:
    optimize one variable at a time on top of a fixed base selection).

    Args:
        signal_file: ROOT file in data/ treated as signal (S).
        background_files: ROOT files in data/ treated as background (B).
        variable: branch name to cut on, e.g. "m2miss".
        thresholds: cut values to test, e.g. [0.5, 1.0, 1.5, 2.0].
        direction: ">" keeps variable > threshold, "<" keeps variable < threshold.
        base_selection: numpy boolean expression applied before the scan.
    """
    if direction not in (">", "<"):
        return 'error: direction must be ">" or "<"'
    sig = _load(signal_file)
    bkgs = [_load(b) for b in background_files]
    sig_base = _apply_cut(sig, base_selection)
    bkg_base = [_apply_cut(b, base_selection) for b in bkgs]
    lines = [f"threshold  S  B  S/sqrt(S+B)   (base: {base_selection})"]
    for thr in thresholds:
        def passing(t, base):
            var = t[variable]
            keep = var > thr if direction == ">" else var < thr
            return int((base & keep).sum())
        s = passing(sig, sig_base)
        b = sum(passing(t, m) for t, m in zip(bkgs, bkg_base))
        fom = s / np.sqrt(s + b) if s + b > 0 else 0.0
        lines.append(f"{variable} {direction} {thr}: S={s} B={b} FoM={fom:.2f}")
    return "\n".join(lines)


@beta_tool
def read_references() -> str:
    """Read the curated summaries of the published reference analyses
    (variables, selections, control regions, note conventions). Call this
    at the PLAN stage, before designing any selection, and cite the papers
    it lists in your plan and note."""
    return (REPO / "docs" / "references.md").read_text()


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
    with the full note following the standard structure:
    Introduction (motivation) / Samples / Selection optimization /
    Background estimation / Results / Discussion / Conclusion.

    Args:
        name: file name, e.g. "dsttaunu_bf_note.md".
        content: the complete note in Markdown. Reference plots by their
            paths under plots/ and put every number in a table.
    """
    NOTES_DIR.mkdir(exist_ok=True)
    out = NOTES_DIR / _safe_name(name, ".md")
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
                 output_name: str, selection: str = "m2miss > -999",
                 x_min: float = 0.0, x_max: float = 10.0, n_bins: int = 40,
                 cut_lines: list[float] | None = None,
                 sample_labels: list[str] | None = None,
                 x_label: str = "", log_y: bool = False) -> str:
    """Publication-style stacked histogram of one variable, split by the
    true origin of each candidate (true_mode x lepton truth), with optional
    vertical cut lines. Use this for the note figures: preselection windows,
    discriminating variables, control regions. When the ntuples carry no
    true_mode branch, the stack is one component per input file instead.

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
    file_colors = ["#bdbdbd", "#64b5f6", "#c9a227", "#8d6e63", "crimson"]
    bins = np.linspace(x_min, x_max, n_bins + 1)
    vals, ws, labs, cols = [], [], [], []
    have_truth = all("true_mode" in _load(rf) for rf in root_files)
    if have_truth:
        for mode, (lab, col) in comps.items():
            v, w = [], []
            for rf, wt in zip(root_files, weights):
                t = _load(rf)
                m = _apply_cut(t, selection)
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
        per_file = []
        for i, (rf, wt) in enumerate(zip(root_files, weights)):
            t = _load(rf)
            m = _apply_cut(t, selection)
            lab = sample_labels[i] if sample_labels else Path(rf).stem
            per_file.append((float(m.sum() * wt), t[variable][m],
                             np.full(int(m.sum()), wt),
                             lab, file_colors[i % len(file_colors)]))
        for _, v, w, lab, col in sorted(per_file, reverse=True,
                                        key=lambda x: x[0]):
            if len(v):
                vals.append(v)
                ws.append(w)
                labs.append(lab)
                cols.append(col)
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
                  selection: str = "m2miss > -999",
                  x_min: float = -2.0, x_max: float = 10.0, n_bins: int = 24,
                  split_by_flavor: bool = True,
                  bkg_syst: float = 0.10,
                  lumi_projection: bool = False,
                  dataset_lumi_invab: float = 0.000906) -> str:
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
            "(true_mode==1) & (abs(lep_true_pid)==13)".
        output_name: post-fit PNG name under plots/.
        selection: preselection applied to everything.
        x_min: histogram lower edge.
        x_max: histogram upper edge.
        n_bins: number of bins.
        split_by_flavor: simultaneous e/mu channels sharing mu.
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

    def build(flavor):
        S = np.zeros(n_bins); B = np.zeros(n_bins)
        Bv = np.zeros(n_bins); D = np.zeros(n_bins)
        for rf, wt in zip(data_files, weights):
            t = _load(rf)
            m = _apply_cut(t, selection)
            if flavor is not None:
                m = m & (t["lep_flavor"] == flavor)
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
    flavors = [(11, "e"), (13, "mu")] if split_by_flavor else [(None, "all")]
    parts = {n: build(f) for f, n in flavors}
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
    On compile errors the error lines are returned so you can fix the
    LaTeX and call again.

    Args:
        name: file name, e.g. "dsttaunu_note.tex".
        content: the complete LaTeX source.
    """
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
    return f"wrote notes/{out.name} and compiled notes/{out.stem}.pdf"


ANALYSIS_TOOLS = [read_references, list_decay_modes, generate_mc,
                  generate_continuum, make_ntuple, query_ntuple,
                  plot_variable, plot_stacked, scan_cut, fit_templates,
                  read_note, save_note, save_note_latex]
