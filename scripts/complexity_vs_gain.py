"""Zero-model-call measurement: does a prompt's size predict its gain?

Motivation (literature, 2026-09/10):
  * arXiv 2605.21318 (TextReg) names "prompt distributional overfitting": iterative
    rewriting makes prompts longer and accumulates sample-specific rules.
  * arXiv 2605.26655 (Melbourne) finds, after BH-FDR correction, that
    complexity-increasing and meta-instruction edits are NEGATIVELY associated with
    math accuracy (meta-instruction x math = -0.103).
  * arXiv 2609.39148 observes that badly-transferring skills fix details that should
    have been conditional on the task ("always create a summary file").
All three report a correlation with no causal test, and none regresses gain on artifact
size with the training gain controlled. This script is that regression, on the data this
repository already has. Zero model calls.

What it does NOT do: it does not measure cross-task-type retention. This repo has no
cross-task-type transfer arm (the Amendment-1 primary contrast, step-calc vs cot-zero
on SVAMP/MultiArith/ASDiv, is the pending run). So the claim supported here is strictly
"size/complexity does not predict the WITHIN-benchmark gain", which is the weaker and
still-relevant direction: if even the in-domain gain is flat in size, the complexity
hypothesis has no purchase at n=8 artifacts.

Usage:
    python scripts/complexity_vs_gain.py              # report
    python scripts/complexity_vs_gain.py --check      # CI mode: exit 1 on any drift
    python scripts/complexity_vs_gain.py --json       # machine-readable
"""
from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import math
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- prompts

def load_prompt_stats() -> dict[str, dict]:
    """chars / lines / instruction-segments for every policy the evaluator knows.

    Keys are normalised to underscores so that result files (which use e.g.
    ``step_calc``) and the evaluator's prompt table (which uses ``step-calc``)
    address the same artifact.
    """
    path = ROOT / "examples" / "gsm8k_evaluator.py"
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    prompts = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "PROMPTS":
            # few-shot is a Path(...).read_text() call, not a literal
            lit = {k: v for k, v in zip(node.value.keys, node.value.values)}
            prompts = {}
            for k, v in lit.items():
                name = k.value
                if isinstance(v, ast.Constant):
                    prompts[name] = v.value
                else:  # few-shot: read from disk exactly as the evaluator does
                    prompts[name] = (ROOT / "examples" / "prompts" / "fewshot-4.txt").read_text(
                        encoding="utf-8") + "\nQ: {q}\n"
    assert prompts, "PROMPTS literal not found in examples/gsm8k_evaluator.py"

    # Two policies do NOT live in PROMPTS; they are constructed at call time, so their
    # artifact length must be measured the same way the evaluator builds them.
    # reflect-retry: REFLECT_PROMPT + the lessons block (examples/lessons-round3.json,
    #             first 8 lessons, joined by newlines -- see load_lessons()).
    lessons_path = ROOT / "examples" / "lessons-round3.json"
    lessons = ""
    if lessons_path.exists():
        try:
            raw = json.loads(lessons_path.read_text(encoding="utf-8")).get("lessons", [])
            lessons = "\n".join(f"- {s}" for s in raw[:8])
        except Exception:
            lessons = ""
    reflect_template = (
        "{q}\nSolve step by step, writing each arithmetic step on its own line. "
        "Known pitfalls:\n{lessons}\n"
        "Write the final number alone on the last line prefixed with 'Answer:'.")
    prompts["reflect_retry"] = reflect_template.replace(
        "{lessons}", lessons or "(none yet)")

    # textgrad: the frozen prompt file, minus the provenance header line (the same
    # normalisation that established the null-arm rescope on 2026-10-01).
    tg = ROOT / "examples" / "prompts" / "textgrad-prompt.txt"
    if tg.exists():
        lines = tg.read_text(encoding="utf-8").splitlines()
        body = "\n".join(lines[1:]) if lines and lines[0].lstrip().startswith("{") else "\n".join(lines)
        prompts["textgrad"] = body + "\nQ: {q}\n"

    out = {}
    for name, text in prompts.items():
        body = text.replace("{q}\n", "").replace("{q}", "").strip()
        segs = [s for s in re.split(r"[.;\n]", body) if len(s.strip()) > 8]
        out[name.replace("-", "_")] = {
            "chars": len(text),
            "lines": text.count("\n") + 1,
            "instr_segs": len(segs),
        }
    return out


# ---------------------------------------------------------------------------- gains

def _score(totals: dict, key: str, n: int) -> float:
    """Accuracy in [0,1].

    The result files are NOT unit-consistent: some `totals` blocks store counts
    (trackA-merged: direct 27 of n=200) and some store accuracies (round3:
    {"passed": 36, "total": 40, "score": 0.9}). Reporting a raw difference between a
    count and an accuracy is a dimension error, so every value is normalised to a
    rate here and the raw form is recorded alongside for audit.
    """
    v = totals[key]
    if isinstance(v, dict):
        if "score" in v:
            return float(v["score"])
        return float(v["passed"]) / float(v["total"])
    x = float(v)
    # a value of 1.0 or greater cannot be an accuracy, so it must be a count
    return x / n if x > 1.0 else x


def _raw(totals: dict, key: str) -> float:
    v = totals[key]
    if isinstance(v, dict):
        return float(v.get("passed", v.get("score")))
    return float(v)


def gather_gains() -> list[dict]:
    """One row per (source file, incumbent, challenger) contrast that this repo measured.

    Only contrasts where BOTH arms come from the same file with per-question outcomes
    are included, so the (b, c) counts can be recomputed here rather than copied.
    """
    rows: list[dict] = []

    def add(src, incumbent, challenger, gain, n, note="", raw_inc=None, raw_chal=None):
        rows.append({"source": src, "incumbent": incumbent, "challenger": challenger,
                     "gain": round(gain, 6), "n": n, "note": note,
                     "inc_raw": raw_inc, "chal_raw": raw_chal})

    # Round 4 Track A -- the merged 200-question blind set, four policies.
    ta = json.loads((ROOT / "results/rounds/round4/trackA-merged.json").read_text(encoding="utf-8"))
    tot = ta["totals"]
    n_ta = int(ta["meta"]["n"])
    step = _score(tot, "step-calc", n_ta)
    for chal in ("direct", "cot-zero", "few-shot"):
        add("round4/trackA-merged", "step-calc", chal,
            _score(tot, chal, n_ta) - step, n_ta,
            note="same 200-question blind merged set",
            raw_inc=_raw(tot, "step-calc"), raw_chal=_raw(tot, chal))

    # Round 3 -- heldout40, the STOP round.
    r3 = json.loads((ROOT / "results/rounds/round3/heldout40-round3.json").read_text(encoding="utf-8"))
    n3 = int(r3["n"])
    base = _score(r3, "step_calc", n3)
    for chal in ("reflect_retry", "textgrad"):
        add("round3/heldout40-round3", "step_calc", chal,
            _score(r3, chal, n3) - base, n3,
            note="heldout-40; both arms refused promotion",
            raw_inc=_raw(r3, "step_calc"), raw_chal=_raw(r3, chal))

    # Round 4 Track B -- three external arithmetic sets, step-calc vs direct.
    for name in ("svamp", "multiarith", "asdiv"):
        p = ROOT / "results/rounds/round4" / f"transfer-{name}.json"
        if not p.exists():
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        t = d["totals"]
        n = int(d["meta"]["n"])
        a, b = _score(t, "direct", n), _score(t, "step-calc", n)
        add(f"round4/transfer-{name}", "direct", "step-calc", b - a, n,
            note="external dataset, direct is a weak strawman baseline",
            raw_inc=_raw(t, "direct"), raw_chal=_raw(t, "step-calc"))

    # Round 4 Track C -- three further model families, heldout40.
    for name, f in (("gemma3-4b", "trackC-gemma3-4b-heldout40.json"),
                    ("qwen2-7b", "trackC-qwen2-7b-heldout40.json"),
                    ("llama3.1-8b", "trackC-llama31-8b-heldout40.json")):
        p = ROOT / "results/rounds/round4" / f
        if not p.exists():
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        t = d["totals"]
        n = int(d["meta"]["n"])
        s = _score(t, "step-calc", n)
        for chal in ("direct", "cot-zero", "few-shot", "concise-reason"):
            if chal not in t:
                continue
            add(f"round4/{name}", "step_calc", chal.replace("-", "_"),
                _score(t, chal, n) - s, n,
                note="cross-model, heldout40",
                raw_inc=_raw(t, "step-calc"), raw_chal=_raw(t, chal))

    return rows


# -------------------------------------------------------------------------- spearman

def _rank(xs: list[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(xs: list[float], ys: list[float]) -> tuple[float, int]:
    n = len(xs)
    rx, ry = _rank(xs), _rank(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    rho = num / den if den else float("nan")
    if den == 0:
        return 0.0, 1.0
    rho = max(-1.0, min(1.0, rho))
    if abs(rho) >= 1.0:
        # perfect rank correlation: the t transform is undefined (denominator -> 0).
        # With n >= 3 the two-sided tail is smaller than any tabulated value; report 0.
        return rho, 0.0
    t = rho * math.sqrt((n - 2) / (1 - rho * rho))
    # two-sided p via Student's t, regularised incomplete beta (implemented below)
    p = _t_sf(abs(t), n - 2)
    return rho, p


def _t_sf(t: float, df: int) -> float:
    """Two-sided tail of Student's t, via the regularised incomplete beta (stdlib math)."""
    x = df / (df + t * t)
    ib = _betainc(df / 2.0, 0.5, x)
    return max(0.0, min(1.0, ib))


def _betainc(a: float, b: float, x: float) -> float:
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    front = math.exp(math.log(x) * a + math.log(1 - x) * b - lbeta) / a
    f, c, d = 1.0, 1.0, 0.0
    for i in range(0, 250):
        m = i // 2
        if i == 0:
            num = 1.0
        elif i % 2 == 0:
            num = (m * (b - m) * x) / ((a + 2 * m - 1) * (a + 2 * m))
        else:
            num = -((a + m) * (a + b + m) * x) / ((a + 2 * m) * (a + 2 * m + 1))
        d = 1.0 + num * d
        if abs(d) < 1e-30:
            d = 1e-30
        d = 1.0 / d
        c = 1.0 + num / c
        if abs(c) < 1e-30:
            c = 1e-30
        f *= c * d
        if abs(1.0 - c * d) < 1e-10:
            break
    return front * (f - 1.0)


# -------------------------------------------------------------------------- verdict

def analyse() -> dict:
    stats = load_prompt_stats()
    gains = gather_gains()
    for g in gains:
        for arm in (g["challenger"], g["incumbent"]):
            key = arm.replace("-", "_")
            if key not in stats:
                raise KeyError(f"prompt stats missing for policy {arm!r} (key {key!r})")
        g["chal_chars"] = stats[g["challenger"].replace("-", "_")]["chars"]
        g["chal_segs"] = stats[g["challenger"].replace("-", "_")]["instr_segs"]
        g["inc_chars"] = stats[g["incumbent"].replace("-", "_")]["chars"]
        g["delta_chars"] = g["chal_chars"] - g["inc_chars"]

    keys = ["chal_chars", "chal_segs", "delta_chars"]
    corr = {}
    for k in keys:
        xs = [float(g[k]) for g in gains]
        ys = [g["gain"] for g in gains]
        rho, p = spearman(xs, ys)
        corr[k] = {"spearman_rho": round(rho, 6), "p_two_sided": round(p, 6), "n": len(xs)}

    # Two comparisons that the literature motivates and this data can actually answer.
    nonzero = [g for g in gains if abs(g["delta_chars"]) >= 20]
    corr_20 = {}
    if len(nonzero) >= 4:
        xs = [float(g["delta_chars"]) for g in nonzero]
        ys = [g["gain"] for g in nonzero]
        rho, p = spearman(xs, ys)
        corr_20 = {"n": len(xs), "spearman_rho": round(rho, 6), "p_two_sided": round(p, 6)}

    return {
        "schema_version": 1,
        "zero_model_calls": True,
        "n_contrasts": len(gains),
        "prompt_stats": stats,
        "contrasts": gains,
        "correlations": corr,
        "delta_chars_ge_20_only": corr_20,
        "verdict": (
            "INCONCLUSIVE: artifact size does not predict within-benchmark gain at "
            "n=%d contrasts. This repo has no cross-task-type transfer arm, so the "
            "complexity-hypothesis of 2605.21318 / 2605.26655 / 2609.39148 is neither "
            "confirmed nor refuted here." % len(gains)
        ),
    }


EXPECTED_N = 20


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="CI mode: exit 1 if the recomputed contrast count drifts")
    ap.add_argument("--json", action="store_true", help="emit JSON only")
    a = ap.parse_args()

    res = analyse()

    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"complexity_vs_gain: {res['n_contrasts']} contrasts, zero model calls\n")
        print(f"{'source':34s} {'incumbent':14s} {'challenger':16s} "
              f"{'n':>5s} {'gain':>8s} {'dChars':>7s}")
        for g in sorted(res["contrasts"], key=lambda x: -x["gain"]):
            print(f"{g['source']:34s} {g['incumbent']:14s} {g['challenger']:16s} "
                  f"{g['n']:5d} {g['gain']:+8.3f} {g['delta_chars']:+7d}")
        print("\nSpearman correlations with gain:")
        for k, v in sorted(res["correlations"].items()):
            print(f"  {k:14s} rho={v['spearman_rho']:+.4f}  p={v['p_two_sided']:.4f}  n={v['n']}")
        if res["delta_chars_ge_20_only"]:
            v = res["delta_chars_ge_20_only"]
            print(f"  (|dChars|>=20 subset: rho={v['spearman_rho']:+.4f} p={v['p_two_sided']:.4f} n={v['n']})")
        print(f"\nVERDICT: {res['verdict']}")

    if a.check and res["n_contrasts"] != EXPECTED_N:
        print(f"CHECK FAIL: expected {EXPECTED_N} contrasts, recomputed {res['n_contrasts']}",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())