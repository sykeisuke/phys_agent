#!/usr/bin/env python3
"""Plots from the K*ll and D*lnu ntuples, for one production set (copy 1 by default).

Run on KEKCC from ntupleProduction/ after b2setup:
    python3 ntuple_plots.py              # copy 1 only ("one set" for testing)
    python3 ntuple_plots.py --copies 1-5 # all five copies
Uses only ntuples whose batch job has finished (log in ../log contains
'completed!'); _test files and still-running jobs are skipped.

Plots requested by Tommy (signal vs backgrounds, normalized histograms):
    all_mbc_de.png          Mbc and deltaE, every channel (K*ll neutral, K*ll charged, D*lnu)
    roe_kstll_neutral.png   rest-of-event variables, K*ll neutral
    roe_kstll_charged.png   rest-of-event variables, K*ll charged
    roe_dstlnu.png          rest-of-event variables, D*lnu
    dstlnu_missing.png      D*lnu missing energy / momentum / mass^2 (the neutrino)
    kstll_vs_jpsi_mll.png   m(ll): K*ll signal vs B -> J/psi K*, direct comparison
Also:
    cutflow.txt             signal cut flow and generic B Bbar counts (also printed)
    signal_mc_overview.png  Mbc / deltaE / m(ll) per signal channel, paper selection
    pid_study_mu.png, pid_study_e.png

Signal = truth-matched candidates (isSignal == 1) in the signal ntuple.
Backgrounds = all candidates in the generic B0B0bar ("mixed"), B+B- ("charged")
and J/psi K* ntuples. Offline "paper selection" = arXiv:2206.05946 without the BDT;
binaryPID is not stored, so K/pi PID uses kaonID/(kaonID+pionID).
"""
import argparse
import glob
import os
import re

import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams.update({"font.size": 12, "axes.titlesize": 13, "legend.fontsize": 10})
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import uproot  # noqa: E402

DATA = "../data"
OUT = "../plots/0930"
EVENTS_PER_JOB = 5000
LEPTON_FRACTION = 0.5          # dec files split ee / mumu 50/50

SIGNAL = [                     # (label, sample, script, lepton)
    ("B0 -> K*0 mu mu", "B0_Kstll", "neutral", "mu"),
    ("B0 -> K*0 e e", "B0_Kstll", "neutral", "e"),
    ("B+ -> K*+ mu mu", "B_Kstll", "charged", "mu"),
    ("B+ -> K*+ e e", "B_Kstll", "charged", "e"),
]
CONTROL = [("B0_JpsiKst", "neutral"), ("B_JpsiKst", "charged")]
GENERIC = [("mixed", "neutral"), ("mixed", "charged"),
           ("charged", "neutral"), ("charged", "charged")]

VETO = {"e": [(2.846, 3.176), (3.439, 3.719)], "mu": [(2.946, 3.176), (3.539, 3.719)]}
PID_CUT = {"e": ("electronID", 0.9, 0.4), "mu": ("muonID", 0.9, 0.8)}   # (var, ID cut, p cut)
KPI_CUT = 0.6
KST_WINDOW = (0.796, 0.996)
BOX_MBC, BOX_DE = (5.27, 5.29), 0.05          # signal box used for the efficiency

BLUE, ORANGE = "#2a78d6", "#eb6834"
INK, MUTED, GRID = "#1f1f1e", "#6b6a63", "#e4e3dc"


# ---------------------------------------------------------------- loading
LOG = "../log"
COPIES = {1}                   # set from --copies in main()


def job_finished(tag, copy):
    """True if the batch log nt_<tag>_<copy>.log exists and reached 'completed!'."""
    log = os.path.join(LOG, f"nt_{tag}_{copy}.log")
    if not os.path.exists(log):
        return False
    with open(log, errors="ignore") as f:
        return "completed!" in f.read()


def files_for_tag(tag):
    """(copy, path) for <tag>_ntuple_<copy>.root, selected copies, finished jobs only."""
    out = []
    for f in sorted(glob.glob(os.path.join(DATA, f"{tag}_ntuple_*.root"))):
        m = re.search(r"_ntuple_(\d+)\.root$", f)
        if m and int(m.group(1)) in COPIES and job_finished(tag, int(m.group(1))):
            out.append((int(m.group(1)), f))
    return out


def files_for(sample, script, lep):
    return files_for_tag(f"{sample}_{script}_{lep}")


def root_name(var):
    """basf2 writes e.g. roeE() as roeE__bo__bc."""
    return (var.replace("(", "__bo").replace(")", "__bc").replace(",", "__cm")
            .replace(" ", "__sp").replace(":", "__cl"))


def load_vars(tag, wanted):
    """Concatenate the wanted variables over the selected copies. Variables that are not
    in the ntuple are skipped with a note. Returns (dict, ncopies) or (None, 0)."""
    found = files_for_tag(tag)
    if not found:
        return None, 0
    parts, missing = [], set()
    for copy, path in found:
        tree = uproot.open(path)["ntuple"]
        have = set(tree.keys())
        use = {}
        for v in wanted:
            for cand in (v, root_name(v)):
                if cand in have:
                    use[v] = cand
                    break
            else:
                missing.add(v)
        arr = tree.arrays(list(use.values()), library="np")
        parts.append({v: arr[b] for v, b in use.items()})
    if missing:
        print(f"  note: {tag}: not in ntuple, skipped: {sorted(missing)}")
    keys = set.intersection(*[set(p) for p in parts])
    return {k: np.concatenate([p[k] for p in parts]) for k in keys}, len(found)


def branches(script, lep):
    b = "B0" if script == "neutral" else "B"
    names = {
        "Mbc": "Mbc", "deltaE": "deltaE", "m_ll": "m_ll", "Kstr_M": "Kstr_M",
        "isSignal": "isSignal", "event": "__event__",
        "l1_id": f"{lep}1_{b}_{PID_CUT[lep][0]}", "l2_id": f"{lep}2_{b}_{PID_CUT[lep][0]}",
        "l1_p": f"{lep}1_{b}_p", "l2_p": f"{lep}2_{b}_p",
        "K_kID": "K_Kstr_kaonID", "K_piID": "K_Kstr_pionID",
        "pi_kID": "pi_Kstr_kaonID", "pi_piID": "pi_Kstr_pionID",
    }
    if script == "charged":
        names["dm"] = "Kstr_decayModeID"
    return names


def load(sample, script, lep):
    """Concatenate all copies; returns (dict of arrays, number of copies)."""
    found = files_for(sample, script, lep)
    if not found:
        return None, 0
    names = branches(script, lep)
    parts = []
    for copy, path in found:
        tree = uproot.open(path)["ntuple"]
        have = set(tree.keys())
        missing = [v for v in names.values() if v not in have]
        if missing:
            raise SystemExit(f"{path}: missing branches {missing}")
        arr = tree.arrays(list(names.values()), library="np")
        d = {k: arr[v] for k, v in names.items()}
        d["copy"] = np.full(len(d["Mbc"]), copy)
        parts.append(d)
    t = {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}
    if "dm" not in t:
        t["dm"] = np.zeros(len(t["Mbc"]))
    return t, len(found)


# ------------------------------------------------------------- selections
def ratio(a, b):
    with np.errstate(divide="ignore", invalid="ignore"):
        return a / (a + b)


def sel_kst(t):
    return (t["Kstr_M"] > KST_WINDOW[0]) & (t["Kstr_M"] < KST_WINDOW[1])


def sel_veto(t, lep):
    ok = np.ones(len(t["m_ll"]), bool)
    for lo, hi in VETO[lep]:
        ok &= ~((t["m_ll"] > lo) & (t["m_ll"] < hi))
    if lep == "e":
        ok &= t["m_ll"] > 0.14
    return ok


def sel_pid(t, lep):
    """Paper PID. dm: 0 = neutral script (K+ and pi- both tracks), 1 = K+ pi0, 2 = K_S0 pi+."""
    _, idcut, pcut = PID_CUT[lep]
    ok = (t["l1_id"] > idcut) & (t["l2_id"] > idcut) & (t["l1_p"] > pcut) & (t["l2_p"] > pcut)
    k_ok = np.where(t["dm"] != 2, ratio(t["K_kID"], t["K_piID"]) > KPI_CUT, True)
    pi_ok = np.where(t["dm"] != 1, ratio(t["pi_piID"], t["pi_kID"]) > KPI_CUT, True)
    return ok & k_ok & pi_ok


def best_candidate(t, mask):
    """Among candidates passing mask, keep the smallest |deltaE| per event."""
    idx = np.flatnonzero(mask)
    if len(idx) == 0:
        return idx
    key = t["copy"][idx] * 10_000_000 + t["event"][idx]
    order = np.lexsort((np.abs(t["deltaE"][idx]), key))
    idx, key = idx[order], key[order]
    first = np.r_[True, key[1:] != key[:-1]]
    return idx[first]


def in_box(t, idx):
    return ((t["Mbc"][idx] > BOX_MBC[0]) & (t["Mbc"][idx] < BOX_MBC[1])
            & (np.abs(t["deltaE"][idx]) < BOX_DE))


def n_events(t, mask):
    key = t["copy"][mask] * 10_000_000 + t["event"][mask]
    return len(np.unique(key))


# ------------------------------------------------------------------ style
def style(ax, xlabel, ylabel="candidates / bin"):
    ax.set_xlabel(xlabel, color=INK)
    ax.set_ylabel(ylabel, color=MUTED)
    ax.tick_params(colors=MUTED)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def hist_pair(ax, a, b, bins, la, lb, density=False):
    ax.hist(a, bins=bins, color=BLUE, alpha=0.35, label=la, density=density)
    ax.hist(b, bins=bins, histtype="step", linewidth=2, color=ORANGE, label=lb, density=density)


# ------------------------------------------------------- Tommy's plot list
AQUA, YELLOW = "#1baf7a", "#eda100"
CAT_STYLE = {   # category -> (colour, linestyle); legend + linestyle carry identity too
    "signal":  (BLUE, "-"),
    "mixed":   (ORANGE, "--"),
    "charged": (AQUA, "-."),
    "jpsi":    (YELLOW, ":"),
}
CAT_LABEL = {"mixed": r"generic $B^0\bar{B}^0$", "charged": r"generic $B^+B^-$",
             "jpsi": r"$B\to J/\psi K^{*}$"}

# analysis -> list of (category, ntuple tag without lepton, sample label)
ANALYSES = {
    "kstll_neutral": {
        "title": r"$B^0\to K^{*0}\ell\ell$ (neutral script)",
        "signal_label": r"signal $B^0\to K^{*0}\ell\ell$",
        "tags": [("signal", "B0_Kstll_neutral_{l}"), ("mixed", "mixed_neutral_{l}"),
                 ("charged", "charged_neutral_{l}"), ("jpsi", "B0_JpsiKst_neutral_{l}")],
    },
    "kstll_charged": {
        "title": r"$B^+\to K^{*+}\ell\ell$ (charged script)",
        "signal_label": r"signal $B^+\to K^{*+}\ell\ell$",
        "tags": [("signal", "B_Kstll_charged_{l}"), ("mixed", "mixed_charged_{l}"),
                 ("charged", "charged_charged_{l}"), ("jpsi", "B_JpsiKst_charged_{l}")],
    },
    "dstlnu": {
        "title": r"$B^0\to D^{*}\ell\nu$ (Dstlnu script)",
        "signal_label": r"signal $B^0\to D^{*}\ell\nu$",
        "tags": [("signal", "B0_Dstlnu_Dst{l}nu"), ("mixed", "mixed_Dst{l}nu"),
                 ("charged", "charged_Dst{l}nu")],
    },
}
ROE_VARS = ["roeE()", "roeM()", "roeP()", "roeMbc()", "roeDeltae()", "roeEextra()",
            "nROE_Charged()", "nROE_Photons()", "nROE_NeutralHadrons()"]
ROE_LABEL = {"roeE()": "ROE energy [GeV]", "roeM()": r"ROE mass [GeV/c$^2$]",
             "roeP()": "ROE momentum [GeV/c]", "roeMbc()": r"ROE $M_{bc}$ [GeV/c$^2$]",
             "roeDeltae()": r"ROE $\Delta E$ [GeV]", "roeEextra()": r"ROE $E_{extra}$ [GeV]",
             "nROE_Charged()": "ROE charged tracks", "nROE_Photons()": "ROE photons",
             "nROE_NeutralHadrons()": "ROE neutral hadrons"}
MISSING_VARS = [("missingEnergyOfEventCMS", "missing energy (CMS) [GeV]"),
                ("missingMomentumOfEventCMS", "missing momentum (CMS) [GeV/c]"),
                ("missingMass2OfEvent", r"missing mass$^2$ [GeV$^2$/c$^4$]")]


def load_category(tag_tmpl, wanted, truth_only):
    """e + mu combined. Signal keeps truth-matched candidates only."""
    parts = []
    for lep in ("e", "mu"):
        t, n = load_vars(tag_tmpl.format(l=lep), wanted + ["isSignal"])
        if t is None:
            continue
        m = (t["isSignal"] == 1) if truth_only else np.ones(len(t["isSignal"]), bool)
        parts.append({k: v[m] for k, v in t.items()})
    if not parts:
        return None
    keys = set.intersection(*[set(p) for p in parts])
    return {k: np.concatenate([p[k] for p in parts]) for k in keys}


def auto_bins(arrays, integer=False, n=40):
    vals = np.concatenate([a[np.isfinite(a)] for a in arrays if len(a)]) if arrays else np.array([])
    if len(vals) == 0:
        return np.linspace(0, 1, n + 1)
    lo, hi = np.percentile(vals, [0.5, 99.5])
    if integer:
        return np.arange(np.floor(lo) - 0.5, np.ceil(hi) + 1.5, 1.0)
    if hi <= lo:
        hi = lo + 1
    return np.linspace(lo, hi, n + 1)


def draw_cats(ax, data, var, bins, labels):
    for cat, t in data.items():
        x = t[var][np.isfinite(t[var])]
        if len(x) == 0:
            continue
        col, ls = CAT_STYLE[cat]
        if cat == "signal":
            ax.hist(x, bins=bins, density=True, color=col, alpha=0.30, label=labels[cat])
            ax.hist(x, bins=bins, density=True, histtype="step", color=col, linewidth=1.5)
        else:
            ax.hist(x, bins=bins, density=True, histtype="step", color=col, linestyle=ls,
                    linewidth=2, label=labels[cat])


def tommy_plots(say):
    say("SIGNAL vs BACKGROUND SAMPLES  (candidates used in the overlay plots; e + mu combined)")
    loaded = {}
    for key, ana in ANALYSES.items():
        wanted = ["Mbc", "deltaE"] + ROE_VARS + [v for v, _ in MISSING_VARS] + \
                 (["m_ll"] if key != "dstlnu" else [])
        data = {}
        for cat, tag in ana["tags"]:
            t = load_category(tag, wanted, truth_only=(cat == "signal"))
            if t is not None:
                data[cat] = t
                say(f"  {key:14s} {cat:8s} {len(t['Mbc']):9d} candidates")
        loaded[key] = data
    say()
    labels_for = {k: {"signal": a["signal_label"], **CAT_LABEL} for k, a in ANALYSES.items()}

    # (all) Mbc and deltaE
    keys = [k for k in ANALYSES if loaded[k]]
    if keys:
        fig, axes = plt.subplots(2, len(keys), figsize=(5.4 * len(keys), 7.0), squeeze=False)
        for row, key in zip(axes.T, keys):
            d = loaded[key]
            draw_cats(row[0], d, "Mbc", np.linspace(5.2, 5.29, 37), labels_for[key])
            style(row[0], r"$M_{bc}$ [GeV/c$^2$]", "normalized")
            de_range = (-4.0, 2.0) if key == "dstlnu" else (-0.3, 0.3)   # fixed; overflow not shown
            draw_cats(row[1], d, "deltaE", np.linspace(*de_range, 41), labels_for[key])
            style(row[1], r"$\Delta E$ [GeV]", "normalized")
            row[0].set_title(ANALYSES[key]["title"], loc="left", color=INK, fontsize=11, fontweight="bold")
            row[0].legend(frameon=False, fontsize=9, loc="upper left")
        fig.suptitle(r"$M_{bc}$ and $\Delta E$: signal (truth-matched) vs backgrounds (all candidates)",
                     x=0.01, ha="left", color=INK, fontsize=13)
        fig.tight_layout()
        fig.savefig(f"{OUT}/all_mbc_de.png", dpi=130)
        plt.close(fig)

    # (all) rest of event
    for key in keys:
        d = loaded[key]
        roe = [v for v in ROE_VARS if all(v in t for t in d.values())]
        if not roe:
            continue
        fig, axes = plt.subplots(3, 3, figsize=(15, 8.2))
        for ax, v in zip(axes.flat, roe):
            integer = v.startswith("nROE")
            draw_cats(ax, d, v, auto_bins([t[v] for t in d.values()], integer=integer), labels_for[key])
            style(ax, ROE_LABEL[v], "normalized")
        for ax in list(axes.flat)[len(roe):]:
            ax.set_visible(False)
        axes[0][0].legend(frameon=False, fontsize=8)
        fig.suptitle(f"Rest of event, {ANALYSES[key]['title']}", x=0.01, ha="left", color=INK, fontsize=13)
        fig.tight_layout()
        name = {"kstll_neutral": "roe_kstll_neutral", "kstll_charged": "roe_kstll_charged",
                "dstlnu": "roe_dstlnu"}[key]
        fig.savefig(f"{OUT}/{name}.png", dpi=130)
        plt.close(fig)

    # D*lnu: missing energy / momentum (the neutrino)
    d = loaded.get("dstlnu", {})
    miss = [(v, xl) for v, xl in MISSING_VARS if d and all(v in t for t in d.values())]
    if miss:
        fig, axes = plt.subplots(1, len(miss), figsize=(4.4 * len(miss), 3.4), squeeze=False)
        for ax, (v, xl) in zip(axes[0], miss):
            draw_cats(ax, d, v, auto_bins([t[v] for t in d.values()]), labels_for["dstlnu"])
            style(ax, xl, "normalized")
        axes[0][0].legend(frameon=False, fontsize=8)
        fig.suptitle(r"$B^0\to D^{*}\ell\nu$: missing energy and momentum of the event",
                     x=0.01, ha="left", color=INK, fontsize=13)
        fig.tight_layout()
        fig.savefig(f"{OUT}/dstlnu_missing.png", dpi=130)
        plt.close(fig)

    # K*ll: m(ll), signal vs J/psi K*, per channel (truth-matched both)
    chans = [(r"$B^0\to K^{*0}\mu\mu$", "B0_Kstll_neutral_mu", "B0_JpsiKst_neutral_mu", "mu"),
             (r"$B^0\to K^{*0}ee$", "B0_Kstll_neutral_e", "B0_JpsiKst_neutral_e", "e"),
             (r"$B^+\to K^{*+}\mu\mu$", "B_Kstll_charged_mu", "B_JpsiKst_charged_mu", "mu"),
             (r"$B^+\to K^{*+}ee$", "B_Kstll_charged_e", "B_JpsiKst_charged_e", "e")]
    fig, axes = plt.subplots(1, 4, figsize=(17, 4.0), squeeze=False)
    drew = False
    say("m(ll) COMPARISON  (truth-matched candidates)")
    for ax, (title, stag, jtag, lep) in zip(axes[0], chans):
        s, _ = load_vars(stag, ["m_ll", "isSignal"])
        j, _ = load_vars(jtag, ["m_ll", "isSignal"])
        if s is None or j is None:
            ax.set_visible(False)
            continue
        drew = True
        bins = np.linspace(0, 4.8, 49)
        sv, jv = s["m_ll"][s["isSignal"] == 1], j["m_ll"][j["isSignal"] == 1]
        ax.hist(sv, bins=bins, density=True, color=BLUE, alpha=0.30, label=r"$K^{*}\ell\ell$ signal")
        ax.hist(sv, bins=bins, density=True, histtype="step", color=BLUE, linewidth=1.5)
        ax.hist(jv, bins=bins, density=True, histtype="step", color=YELLOW, linestyle=":", linewidth=2,
                label=r"$J/\psi K^{*}$")
        for lo, hi in VETO[lep]:
            ax.axvspan(lo, hi, color=MUTED, alpha=0.15, linewidth=0)
        style(ax, r"$m(\ell\ell)$ [GeV/c$^2$]", "normalized")
        ax.set_yscale("log")
        ax.set_title(title, loc="left", color=INK, fontsize=11, fontweight="bold")
        say(f"  {stag:22s} K*ll: {len(sv):7d}   J/psi K*: {len(jv):7d}")
    if drew:
        axes[0][0].legend(frameon=False, fontsize=9)
        fig.suptitle(r"$m(\ell\ell)$: $K^{*}\ell\ell$ signal vs $B\to J/\psi K^{*}$ (shaded: veto windows)",
                     x=0.01, ha="left", color=INK, fontsize=13)
        fig.tight_layout()
        fig.savefig(f"{OUT}/kstll_vs_jpsi_mll.png", dpi=130)
    plt.close(fig)
    say()



# ------------------------------------------------------------------- main
def main():
    global COPIES
    ap = argparse.ArgumentParser()
    ap.add_argument("--copies", default="1", help="e.g. 1, 1-5 or 1,3 (default: 1)")
    args = ap.parse_args()
    if "-" in args.copies:
        lo, hi = args.copies.split("-")
        COPIES = set(range(int(lo), int(hi) + 1))
    else:
        COPIES = {int(c) for c in args.copies.split(",")}
    os.makedirs(OUT, exist_ok=True)
    report = []

    def say(line=""):
        print(line)
        report.append(line)

    # ---------------- signal cut flow and efficiency
    say(f"COPIES USED: {sorted(COPIES)}  ({EVENTS_PER_JOB} events per copy per sample)")
    say()
    say("SIGNAL CUT FLOW  (events with a truth-matched candidate, % of generated)")
    say(f"{'channel':18s} {'copies':>6s} {'ntuple':>8s} {'+K*':>8s} {'+vetoes':>8s} "
        f"{'+PID':>8s} {'best+box':>9s}")
    sig_tables = {}
    for label, sample, script, lep in SIGNAL:
        t, ncopy = load(sample, script, lep)
        if t is None:
            say(f"{label:18s}  no ntuples yet")
            continue
        ngen = ncopy * EVENTS_PER_JOB * LEPTON_FRACTION
        truth = t["isSignal"] == 1
        m_kst, m_veto, m_pid = sel_kst(t), sel_veto(t, lep), sel_pid(t, lep)
        steps = [truth, truth & m_kst, truth & m_kst & m_veto, truth & m_kst & m_veto & m_pid]
        effs = [100 * n_events(t, s) / ngen for s in steps]
        best = best_candidate(t, m_kst & m_veto & m_pid)
        box = best[in_box(t, best)]
        eff_final = 100 * np.sum(t["isSignal"][box] == 1) / ngen
        say(f"{label:18s} {ncopy:6d} " + " ".join(f"{e:7.1f}%" for e in effs) + f" {eff_final:8.1f}%")
        sig_tables[label] = (t, lep, m_kst & m_veto & m_pid, best, ncopy)
    say()

    # ---------------- signal overview (paper-style Mbc / deltaE / m(ll))
    rows = [k for k in sig_tables]
    if rows:
        fig, axes = plt.subplots(3, len(rows), figsize=(4.3 * len(rows), 9.0), squeeze=False)
        say(f"{'channel':18s} {'selected':>8s} {'truth':>6s} {'eff':>6s} {'Mbc width':>10s} {'dE width':>9s}")
        for row, label in zip(axes.T, rows):
            t, lep, mask, best, ncopy = sig_tables[label]
            ngen = ncopy * EVENTS_PER_JOB * LEPTON_FRACTION
            b = best
            sig = t["isSignal"][b] == 1
            in_de = np.abs(t["deltaE"][b]) < BOX_DE
            in_mbc = (t["Mbc"][b] > BOX_MBC[0]) & (t["Mbc"][b] < BOX_MBC[1])
            hist_pair(row[0], t["Mbc"][b][in_de], t["Mbc"][b][in_de & sig], np.linspace(5.2, 5.29, 28),
                      "all selected", "truth-matched")
            style(row[0], r"$M_{bc}$ [GeV/c$^2$]  ($|\Delta E|<0.05$)")
            hist_pair(row[1], t["deltaE"][b][in_mbc], t["deltaE"][b][in_mbc & sig], np.linspace(-0.3, 0.3, 40),
                      "all selected", "truth-matched")
            style(row[1], r"$\Delta E$ [GeV]  ($5.27<M_{bc}<5.29$)")
            hist_pair(row[2], t["m_ll"][b], t["m_ll"][b][sig], np.linspace(0, 4.8, 49),
                      "all selected", "truth-matched")
            for lo, hi in VETO[lep]:
                row[2].axvspan(lo, hi, color=MUTED, alpha=0.15, linewidth=0)
            style(row[2], r"$m(\ell\ell)$ [GeV/c$^2$]")
            row[0].set_title(label, loc="left", color=INK, fontsize=11, fontweight="bold")
            n_sel = int((in_de & in_mbc).sum())
            n_sig = int((in_de & in_mbc & sig).sum())

            def spread(x):
                return float("nan") if len(x) < 5 else (np.percentile(x, 84) - np.percentile(x, 16)) / 2
            say(f"{label:18s} {n_sel:8d} {n_sig:6d} {100 * n_sig / ngen:5.1f}% "
                f"{1000 * spread(t['Mbc'][b][sig & in_de]):7.1f} MeV {1000 * spread(t['deltaE'][b][sig & in_mbc]):6.1f} MeV")
        axes[0][0].legend(frameon=False, fontsize=9)
        axes[2][0].text(0.02, 0.95, r"shaded: $J/\psi$, $\psi(2S)$ vetoes", transform=axes[2][0].transAxes,
                        color=MUTED, fontsize=9, va="top")
        fig.suptitle("Signal MC, paper selection (no BDT), best candidate", x=0.01, ha="left",
                     color=INK, fontsize=13)
        fig.tight_layout()
        fig.savefig(f"{OUT}/signal_mc_overview.png", dpi=130)
        plt.close(fig)
        say()

    # ---------------- generic background: load once
    gen = {}
    for sample, script in GENERIC:
        for lep in ("e", "mu"):
            t, n = load(sample, script, lep)
            if t is not None:
                gen[(sample, script, lep)] = (t, n)

    say("GENERIC B Bbar  (candidates after each step; 'box' = best candidate in signal box)")
    say(f"{'sample / script / lep':30s} {'copies':>6s} {'ntuple':>8s} {'+K*':>8s} {'+vetoes':>8s} {'+PID':>8s} {'box':>5s}")
    for (sample, script, lep), (t, n) in gen.items():
        m1, m2, m3 = sel_kst(t), sel_veto(t, lep), sel_pid(t, lep)
        best = best_candidate(t, m1 & m2 & m3)
        say(f"{sample + ' / ' + script + ' / ' + lep:30s} {n:6d} {len(t['Mbc']):8d} {int(m1.sum()):8d} "
            f"{int((m1 & m2).sum()):8d} {int((m1 & m2 & m3).sum()):8d} {int(in_box(t, best).sum()):5d}")
    say()

    # ---------------- PID study: signal truth vs generic, per lepton flavour
    for lep in ("mu", "e"):
        sig = [(v[0], v[2]) for k, v in sig_tables.items() if v[1] == lep]
        bkg = [v[0] for k, v in gen.items() if k[2] == lep]
        if not sig or not bkg:
            continue

        def gather(ts, key, extra=None):
            out = []
            for t in ts:
                m = sel_kst(t) & sel_veto(t, lep)
                if extra is not None:
                    m &= extra(t)
                out.append(t[key][m])
            return np.concatenate(out) if out else np.array([])
        sig_ts = [s[0] for s in sig]
        truth = lambda t: t["isSignal"] == 1  # noqa: E731
        idvar, idcut, pcut = PID_CUT[lep]
        fig, ax = plt.subplots(1, 4, figsize=(15, 3.4))
        panels = [
            ("lepton ID", np.r_[gather(sig_ts, "l1_id", truth), gather(sig_ts, "l2_id", truth)],
             np.r_[gather(bkg, "l1_id"), gather(bkg, "l2_id")], np.linspace(0, 1, 41), idcut, f"{idvar}"),
            ("lepton p", np.r_[gather(sig_ts, "l1_p", truth), gather(sig_ts, "l2_p", truth)],
             np.r_[gather(bkg, "l1_p"), gather(bkg, "l2_p")], np.linspace(0, 3, 41), pcut, "p [GeV/c]"),
        ]
        ksig = [ratio(t["K_kID"], t["K_piID"])[sel_kst(t) & sel_veto(t, lep) & truth(t) & (t["dm"] != 2)] for t in sig_ts]
        kbkg = [ratio(t["K_kID"], t["K_piID"])[sel_kst(t) & sel_veto(t, lep) & (t["dm"] != 2)] for t in bkg]
        psig = [ratio(t["pi_piID"], t["pi_kID"])[sel_kst(t) & sel_veto(t, lep) & truth(t) & (t["dm"] != 1)] for t in sig_ts]
        pbkg = [ratio(t["pi_piID"], t["pi_kID"])[sel_kst(t) & sel_veto(t, lep) & (t["dm"] != 1)] for t in bkg]
        panels += [("kaon", np.concatenate(ksig), np.concatenate(kbkg), np.linspace(0, 1, 41), KPI_CUT, "K/π ratio of the K"),
                   ("pion", np.concatenate(psig), np.concatenate(pbkg), np.linspace(0, 1, 41), KPI_CUT, "π/K ratio of the π")]
        for a, (title, s, b, bins, cut, xl) in zip(ax, panels):
            s, b = s[np.isfinite(s)], b[np.isfinite(b)]
            hist_pair(a, s, b, bins, "signal (truth)", "generic $B\\bar{B}$", density=True)
            a.axvline(cut, color=INK, linestyle="--", linewidth=1)
            a.text(cut, 0.97, " paper cut", transform=a.get_xaxis_transform(), color=INK, fontsize=8, va="top")
            a.set_yscale("log")
            style(a, xl, "normalized")
            a.set_title(title, loc="left", color=INK, fontsize=11, fontweight="bold")
        ax[0].legend(frameon=False, fontsize=9, loc="upper center")
        lname = r"$\mu\mu$" if lep == "mu" else "$ee$"
        fig.suptitle(f"PID, {lname} channels: signal vs generic $B\\bar{{B}}$ (after K* window and vetoes)",
                     x=0.01, ha="left", color=INK, fontsize=13)
        fig.tight_layout()
        fig.savefig(f"{OUT}/pid_study_{lep}.png", dpi=130)
        plt.close(fig)

    tommy_plots(say)

    with open(f"{OUT}/cutflow.txt", "w") as f:
        f.write("\n".join(report) + "\n")
    print(f"wrote plots and cutflow.txt to {OUT}/")


if __name__ == "__main__":
    main()
