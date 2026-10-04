#!/usr/bin/env python3
"""The accuracy-cost frontier of the committed evidence.

Why this exists
---------------
Every accuracy comparison in this project now returns "no significant difference":
step-calc vs cot-zero p=0.804, vs few-shot p=0.404, cot-zero vs few-shot p=1.000,
and the 7B arm puts cot-zero at 26/26. That is not three inconclusive
experiments -- it is an axis at ceiling. On a saturated axis no intervention can
show damage, because there is no headroom left to be pushed around.

Latency has 3.6x of spread and is already recorded per item in
`details[*][policy].latency`. This script computes, from committed evidence only:

  1. accuracy per policy with Wilson intervals
  2. latency per policy with bootstrap intervals
  3. paired latency differences against the incumbent, with paired bootstrap CIs
  4. exact McNemar for every accuracy pair
  5. the Pareto frontier on (higher accuracy, lower latency)
  6. THE QUESTION: among policies statistically indistinguishable from the best on
     accuracy, which is cheapest?

Zero model calls. Reads committed JSON; writes nothing unless --json is given.

  python scripts/frontier.py
  python scripts/frontier.py --incumbent step-calc --json results/frontier.json
"""

import argparse
import itertools
import json
import math
import os
import random

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DEFAULT_EVIDENCE = "results/rounds/round4/trackA-merged.json"


# ---------------------------------------------------------------- statistics
def wilson(passed, n, z=1.959963984540054):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = passed / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (p, max(0.0, c - h), min(1.0, c + h))


def mcnemar_exact(better, worse):
    """Two-sided exact binomial on the discordant pairs."""
    n = better + worse
    if n == 0:
        return 1.0
    k = min(better, worse)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def boot_ci(values, stat, n_boot=10000, seed=20260912, alpha=0.05):
    rng = random.Random(seed)
    N = len(values)
    if N == 0:
        return (float("nan"), float("nan"))
    reps = []
    for _ in range(n_boot):
        reps.append(stat([values[rng.randrange(N)] for _ in range(N)]))
    reps.sort()
    lo = reps[int(alpha / 2 * n_boot)]
    hi = reps[min(n_boot - 1, int((1 - alpha / 2) * n_boot))]
    return (lo, hi)


def paired_boot_diff(a, b, n_boot=10000, seed=20260912, alpha=0.05):
    """CI on mean(a) - mean(b) with items paired."""
    d = [x - y for x, y in zip(a, b)]
    if not d:
        return (float("nan"), float("nan"), float("nan"))
    lo, hi = boot_ci(d, lambda v: sum(v) / len(v), n_boot, seed, alpha)
    return (sum(d) / len(d), lo, hi)


# ---------------------------------------------------------------- the analysis
def load(evidence_rel):
    path = os.path.join(ROOT, evidence_rel)
    with open(path, encoding="utf-8") as fh:
        return json.load(fh), evidence_rel


def analyse(data):
    items = sorted(data["details"])
    pols = sorted(data["totals"])
    per = {}
    for p in pols:
        passed = sum(1 for i in items if data["details"][i][p]["passed"])
        acc, lo, hi = wilson(passed, len(items))
        lat = [data["details"][i][p]["latency"] for i in items]
        mlo, mhi = boot_ci(lat, lambda v: sum(v) / len(v))
        per[p] = {"passed": passed, "n": len(items), "accuracy": acc,
                  "acc_lo": lo, "acc_hi": hi,
                  "lat_mean": sum(lat) / len(lat), "lat_lo": mlo, "lat_hi": mhi,
                  "lat_median": sorted(lat)[len(lat) // 2], "_lat": lat}
    return items, pols, per


def pairs(items, pols, per, data):
    out = {}
    for x, y in itertools.combinations(pols, 2):
        bx = sum(1 for i in items if data["details"][i][x]["passed"])
        by = sum(1 for i in items if data["details"][i][y]["passed"])
        better = sum(1 for i in items
                     if data["details"][i][x]["passed"] and not data["details"][i][y]["passed"])
        worse = sum(1 for i in items
                    if data["details"][i][y]["passed"] and not data["details"][i][x]["passed"])
        d, dlo, dhi = paired_boot_diff(per[x]["_lat"], per[y]["_lat"])
        out[f"{x}|{y}"] = {
            "better": better, "worse": worse,
            "mcnemar_p": mcnemar_exact(better, worse),
            "acc_delta": (bx - by) / len(items),
            "lat_diff_s": d, "lat_diff_lo": dlo, "lat_diff_hi": dhi,
        }
    return out


def frontier(per):
    """Non-dominated on (higher accuracy, lower latency)."""
    keep = []
    for p, v in per.items():
        dominated = any(
            (o["accuracy"] >= v["accuracy"] and o["lat_mean"] <= v["lat_mean"]) and
            (o["accuracy"] > v["accuracy"] or o["lat_mean"] < v["lat_mean"])
            for q, o in per.items() if q != p)
        if not dominated:
            keep.append(p)
    return sorted(keep, key=lambda p: per[p]["lat_mean"])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", default=DEFAULT_EVIDENCE)
    ap.add_argument("--incumbent", default=None,
                    help="policy to compare everything against on latency")
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--json", help="write the report here")
    a = ap.parse_args(argv)

    data, rel = load(a.evidence)
    items, pols, per = analyse(data)
    pr = pairs(items, pols, per, data)
    keep = frontier(per)
    best_acc = max(per, key=lambda p: per[p]["accuracy"])

    print(f"evidence: {rel}   items={len(items)}   policies={pols}")
    print()
    print(f"{'policy':14}{'accuracy':>10} {'Wilson 95%':>18} {'lat mean':>10} "
          f"{'boot 95%':>18}  frontier")
    print("-" * 92)
    for p in sorted(pols, key=lambda x: per[x]["lat_mean"]):
        v = per[p]
        star = "*" if p in keep else " "
        print(f"{star}{p:13}{v['accuracy']:>10.3f} "
              f"[{v['acc_lo']:.3f},{v['acc_hi']:.3f}]".ljust(34) +
              f"{v['lat_mean']:>10.3f} [{v['lat_lo']:.3f},{v['lat_hi']:.3f}]")

    print()
    print("* = on the accuracy/cost Pareto frontier (not dominated on either axis)")
    print(f"  frontier: {keep}")

    print()
    print("accuracy, pairwise (exact McNemar):")
    for k, v in sorted(pr.items(), key=lambda kv: kv[1]["mcnemar_p"]):
        x, y = k.split("|")
        verdict = "SIGNIFICANT" if v["mcnemar_p"] < a.alpha else "indistinguishable"
        print(f"  {x:12} vs {y:12}  better:worse={v['better']:>3}:{v['worse']:<3} "
              f"p={v['mcnemar_p']:.4f}  {verdict}")

    # THE QUESTION
    print()
    print(f"=== among policies ACCURACY-INDISTINGUISHABLE from the best ({best_acc}), "
          f"which is cheapest? ===")
    tie = [p for p in pols
           if p == best_acc
           or (f"{p}|{best_acc}" in pr and pr[f"{p}|{best_acc}"]["mcnemar_p"] >= a.alpha)
           or (f"{best_acc}|{p}" in pr and pr[f"{best_acc}|{p}"]["mcnemar_p"] >= a.alpha)]
    tie.sort(key=lambda p: per[p]["lat_mean"])
    if not tie:
        tie = [best_acc]
    cheapest = tie[0]
    for p in tie:
        v = per[p]
        print(f"  {p:14} acc={v['accuracy']:.3f}  lat={v['lat_mean']:>7.3f}s")
    if cheapest != best_acc:
        gain = 1 - per[cheapest]["lat_mean"] / per[best_acc]["lat_mean"]
        print()
        print(f"  => {cheapest} is {gain:+.1%} cheaper than {best_acc} at accuracy that "
              f"cannot be distinguished from it.")
        print(f"     That is a real move along the frontier, already in hand, currently "
              f"reported only as 'no significant difference'.")
    else:
        print(f"  => {cheapest} is already the cheapest of the tied set.")

    if a.incumbent:
        print()
        print(f"latency vs incumbent {a.incumbent} (paired, negative = cheaper):")
        for k, v in sorted(pr.items()):
            x, y = k.split("|")
            for p, q in ((x, y), (y, x)):
                if q == a.incumbent and p != a.incumbent:
                    d = -v["lat_diff_s"]
                    lo, hi = -v["lat_diff_hi"], -v["lat_diff_lo"]
                    sig = "SIGNIFICANT" if (lo > 0 or hi < 0) else "not significant"
                    print(f"  {p:14} {d:>+8.3f}s  CI[{lo:+.3f},{hi:+.3f}]  {sig}")

    if a.json:
        out = {"evidence": rel, "n_items": len(items),
               "policies": {p: {k: v for k, v in per[p].items() if k != "_lat"}
                            for p in pols},
               "pairs": pr, "frontier": keep,
               "best_accuracy": best_acc,
               "indistinguishable_from_best": tie,
               "cheapest_among_tied": cheapest}
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=2)
        print(f"\nwrote {a.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())