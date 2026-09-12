"""Summarize a Track-C per-model result and evaluate the PREREG headline gate.

Usage: python3 scripts/summarize_trackC.py results/rounds/round4/trackC-*.json

Reads `run_round4.py`-style outputs {meta, totals, pairs, details} and prints,
per model: totals, every pair, and the PREREG Track-C contract
(PREREG-round4.md line 16):

  headline pairs : step-calc vs concise-reason (Round-2 replication)
                   step-calc vs cot-zero       (Round-4 extension)
  expansion rule : expand that model to batch2-160 iff a headline pair has
                   p < 0.2 AND |gain| >= 0.02  (weak-signal spend rule)

Pure recompute: no model calls. Recomputes pairs from `details` and asserts the
recorded pair fields match (catches a truncated/hand-edited result file).
"""
import json
import sys
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from evokit.stats import ledger_ok, mcnemar_two_sided

HEADLINE_PAIRS = ["step-calc_vs_concise-reason", "step-calc_vs_cot-zero"]
EXPAND_P_THRESHOLD = 0.2
EXPAND_GAIN_THRESHOLD = 0.02


def recompute(data: dict) -> dict:
    policies = data["meta"]["policies"]
    details = data["details"]
    n = len(details)
    totals = {p: sum(1 for row in details.values() if row[p]["passed"])
              for p in policies}
    lat = {p: sum(row[p]["latency"] for row in details.values()) / max(n, 1)
           for p in policies}
    pairs = {}
    for x, y in combinations(policies, 2):
        better = sum(1 for r in details.values()
                     if r[y]["passed"] and not r[x]["passed"])
        worse = sum(1 for r in details.values()
                    if r[x]["passed"] and not r[y]["passed"])
        assert ledger_ok(totals[x], totals[y], better, worse), (x, y)
        pairs["%s_vs_%s" % (x, y)] = {
            "better": better, "worse": worse,
            "p": mcnemar_two_sided(better, worse),
            "gain": (totals[y] - totals[x]) / n if n else 0.0,
            "ledger_ok": True, "lat_x": lat[x], "lat_y": lat[y],
            "lat_ratio": (lat[y] / lat[x]) if lat[x] else None}
    return {"n": n, "totals": totals, "pairs": pairs}


def main() -> None:
    paths = [Path(p) for p in sys.argv[1:]]
    if not paths:
        paths = sorted((ROOT / "results" / "rounds" / "round4").glob("trackC-*.json"))
    if not paths:
        print("no trackC-*.json found")
        sys.exit(1)

    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        rec = recompute(data)
        # integrity: recorded values must match a from-details recompute
        for k, v in rec["pairs"].items():
            got = data["pairs"][k]
            for f in ("better", "worse"):
                assert got[f] == v[f], (path.name, k, f)
            assert abs(got["p"] - v["p"]) < 1e-12, (path.name, k, "p")
            assert abs(got["gain"] - v["gain"]) < 1e-12, (path.name, k, "gain")
        assert rec["totals"] == data["totals"], path.name

        model = data["meta"].get("model", "?")
        n = rec["n"]
        print("=" * 72)
        print("MODEL=%s  n=%d  file=%s" % (model, n, path.name))
        print("totals:", rec["totals"])
        print("pairs (better=2nd wins | worse=1st wins | gain=(t2-t1)/n):")
        for k, v in sorted(rec["pairs"].items()):
            print("  %-34s better=%-3d worse=%-3d p=%.4g gain=%+.4f lat_ratio=%.3f"
                  % (k, v["better"], v["worse"], v["p"], v["gain"], v["lat_ratio"]))
        print("PREREG Track-C headline (line 16):")
        expand = False
        for key in HEADLINE_PAIRS:
            if key not in rec["pairs"]:
                print("  %-34s MISSING (policy pair not present)" % key)
                continue
            v = rec["pairs"][key]
            c1 = v["p"] < EXPAND_P_THRESHOLD
            c2 = abs(v["gain"]) >= EXPAND_GAIN_THRESHOLD
            weak = c1 and c2
            expand = expand or weak
            print("  %-34s p=%.4g (<%.1f:%s)  |gain|=%.4f (>=%.2f:%s)  weak-signal=%s"
                  % (key, v["p"], EXPAND_P_THRESHOLD, c1, abs(v["gain"]),
                     EXPAND_GAIN_THRESHOLD, c2, weak))
        print("  expansion to batch2-160: %s" % ("YES" if expand else "NO"))
    print("=" * 72)


if __name__ == "__main__":
    main()