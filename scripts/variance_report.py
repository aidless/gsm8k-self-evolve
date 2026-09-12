"""Quantify run-to-run variance from repeated paired runs.

Usage: python3 scripts/variance_report.py results/rounds/round4/variance-*.json

Reads N result files produced by run_paired_incremental.py for the SAME dataset
and policy set, and reports, per policy and per headline pair:

  - per-repeat accuracy (and min/max/spread across repeats)
  - per-repeat paired counts (better/worse) and exact McNemar p
  - whether the qualitative verdict (significant / not) is stable across repeats

This is the evidence that closes the "single run, variance unquantified"
soundness gap: it shows how much the numbers move when nothing changes but the
run itself. Pure recompute over `details`; no model calls.
"""
import json
import sys
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from evokit.stats import ledger_ok, mcnemar_two_sided


def recompute(data: dict):
    policies = data["meta"]["policies"]
    details = {q: r for q, r in data["details"].items()
               if all(p in r for p in policies)}
    n = len(details)
    totals = {p: sum(1 for r in details.values() if r[p]["passed"]) for p in policies}
    pairs = {}
    for x, y in combinations(policies, 2):
        better = sum(1 for r in details.values() if r[y]["passed"] and not r[x]["passed"])
        worse = sum(1 for r in details.values() if r[x]["passed"] and not r[y]["passed"])
        assert ledger_ok(totals[x], totals[y], better, worse), (x, y)
        pairs["%s_vs_%s" % (x, y)] = {
            "better": better, "worse": worse,
            "p": mcnemar_two_sided(better, worse),
            "gain": (totals[y] - totals[x]) / n if n else 0.0}
    return n, totals, pairs


def main() -> None:
    paths = [Path(p) for p in sys.argv[1:]]
    if not paths:
        paths = sorted((ROOT / "results" / "rounds" / "round4").glob("variance-*.json"))
    if not paths:
        print("no variance-*.json found")
        sys.exit(1)

    runs = []
    for p in paths:
        data = json.loads(p.read_text(encoding="utf-8"))
        n, totals, pairs = recompute(data)
        runs.append({"file": p.name, "model": data["meta"].get("model"), "n": n,
                     "totals": totals, "pairs": pairs})
        print("read %-34s n=%-3d totals=%s" % (p.name, n, totals))

    policies = sorted(runs[0]["totals"])
    print("\n=== per-policy accuracy across %d repeats ===" % len(runs))
    for pol in policies:
        vals = [r["totals"][pol] / r["n"] for r in runs]
        print("  %-16s %s  spread=%.3f (min %.3f max %.3f)"
              % (pol, " ".join("%.3f" % v for v in vals),
                 max(vals) - min(vals), min(vals), max(vals)))

    print("\n=== per-pair stability across repeats ===")
    pair_keys = sorted(runs[0]["pairs"])
    for key in pair_keys:
        ps = [r["pairs"][key]["p"] for r in runs]
        bw = ["%d:%d" % (r["pairs"][key]["better"], r["pairs"][key]["worse"]) for r in runs]
        gains = [r["pairs"][key]["gain"] for r in runs]
        sig = [p < 0.05 for p in ps]
        print("  %-34s" % key)
        print("     better:worse  %s" % "  ".join(bw))
        print("     p             %s" % "  ".join("%.4g" % p for p in ps))
        print("     gain          %s" % "  ".join("%+.4f" % g for g in gains))
        print("     significant?  %s   -> %s"
              % ("  ".join(str(s) for s in sig),
                 "STABLE" if len(set(sig)) == 1 else "UNSTABLE (verdict flips!)"))

    print("\n=== summary ===")
    acc_spread = {p: (max(r["totals"][p] / r["n"] for r in runs)
                      - min(r["totals"][p] / r["n"] for r in runs)) for p in policies}
    print("max per-policy accuracy spread: %.3f" % max(acc_spread.values()))
    flips = [k for k in pair_keys
             if len({(r["pairs"][k]["p"] < 0.05) for r in runs}) > 1]
    print("pairs whose significance verdict flips across repeats: %s"
          % (", ".join(flips) if flips else "none"))


if __name__ == "__main__":
    main()