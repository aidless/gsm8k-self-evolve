"""Merge the two Track-A true-baseline runs into one n=200 evidence file.

Usage: python3 scripts/merge_trackA.py

Reads results/rounds/round4/trackA-heldout40.json (n=40) and
results/rounds/round4/trackA-batch2-160.json (n=160), concatenates their per-id
`details` dicts (asserting exactly 200 unique ids and zero id overlap), and
recomputes -- from the per-id details only -- the totals for the 4 policies,
every unordered pair's better/worse (with evokit.stats.ledger_ok asserted),
exact two-sided McNemar p, gain, mean latencies and the challenger/incumbent
latency ratio. Writes results/rounds/round4/trackA-merged.json with the same
{meta, totals, pairs, details} shape as scripts/run_round4.py.

Pure recompute: no model calls, no re-runs, no re-judgment. The PREREG headline
gate (results/rounds/round4/PREREG-round4.md) is only *evaluated* and printed
here, verbatim as three conditions; no branch is selected by this script.
"""
import json
import sys
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from evokit.stats import ledger_ok, mcnemar_two_sided

ROUND = ROOT / "results" / "rounds" / "round4"
INPUTS = [ROUND / "trackA-heldout40.json", ROUND / "trackA-batch2-160.json"]
OUT = ROUND / "trackA-merged.json"
EXPECTED_N = 200
HEADLINE_PAIRS = ["step-calc_vs_cot-zero", "step-calc_vs_few-shot"]


def totals_of(details: dict, policies: list) -> dict:
    return {p: sum(1 for row in details.values() if row[p]["passed"]) for p in policies}


def lat_of(details: dict, policies: list) -> dict:
    n = len(details)
    return {p: sum(row[p]["latency"] for row in details.values()) / max(n, 1)
            for p in policies}


def pairs_of(details: dict, policies: list) -> dict:
    """Same pair semantics as run_round4.py: for (x, y), better = y-only passes,
    worse = x-only passes, gain = (totals[y] - totals[x]) / n, lat_ratio = lat[y]/lat[x]."""
    n = len(details)
    totals = totals_of(details, policies)
    lat = lat_of(details, policies)
    pairs = {}
    for x, y in combinations(policies, 2):
        better = sum(1 for row in details.values() if row[y]["passed"] and not row[x]["passed"])
        worse = sum(1 for row in details.values() if row[x]["passed"] and not row[y]["passed"])
        assert ledger_ok(totals[x], totals[y], better, worse), (
            x, y, totals[x], totals[y], better, worse)
        pairs["%s_vs_%s" % (x, y)] = {
            "better": better, "worse": worse,
            "p": mcnemar_two_sided(better, worse),
            "gain": (totals[y] - totals[x]) / n if n else 0.0,
            "ledger_ok": True, "lat_x": lat[x], "lat_y": lat[y],
            "lat_ratio": (lat[y] / lat[x]) if lat[x] else None}
    return pairs


def verify_source(path: Path) -> dict:
    """Re-derive totals and pair counts of an input file from its own details
    dict and assert they equal the recorded ones (integrity check on inherited
    evidence -- catches a truncated or hand-edited result file)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    assert set(data) == {"meta", "totals", "pairs", "details"}, (path.name, sorted(data))
    policies = data["meta"]["policies"]
    assert len(data["details"]) == data["meta"]["n"], path.name
    assert totals_of(data["details"], policies) == data["totals"], path.name
    recomputed = pairs_of(data["details"], policies)
    for key, rec in recomputed.items():
        got = data["pairs"][key]
        for field in ("better", "worse", "ledger_ok"):
            assert got[field] == rec[field], (path.name, key, field, got[field], rec[field])
        assert abs(got["gain"] - rec["gain"]) < 1e-12, (path.name, key)
        assert abs(got["p"] - rec["p"]) < 1e-12, (path.name, key)
        for field in ("lat_x", "lat_y", "lat_ratio"):
            assert abs(got[field] - rec[field]) < 1e-9, (path.name, key, field)
    print("verified %-28s n=%-4d totals=%s" % (path.name, data["meta"]["n"], data["totals"]))
    return data


def main() -> None:
    details: dict = {}
    policies = None
    model = None
    datasets = []
    for path in INPUTS:
        data = verify_source(path)
        if policies is None:
            policies = data["meta"]["policies"]
            model = data["meta"]["model"]
        else:
            assert data["meta"]["policies"] == policies, path.name
            assert data["meta"]["model"] == model, path.name
        overlap = set(details) & set(data["details"])
        assert not overlap, ("id overlap between input files", sorted(overlap)[:5])
        details.update(data["details"])
        datasets.append(data["meta"]["dataset"])

    assert len(details) == EXPECTED_N, (
        "expected %d unique ids, got %d" % (EXPECTED_N, len(details)))
    for qid, row in details.items():
        assert set(row) == set(policies), (qid, sorted(row))

    n = len(details)
    totals = totals_of(details, policies)
    lat = lat_of(details, policies)
    pairs = pairs_of(details, policies)

    OUT.write_text(json.dumps({
        "meta": {"dataset": datasets, "policies": policies, "model": model, "n": n,
                 "sources": [str(p.relative_to(ROOT)) for p in INPUTS]},
        "totals": totals, "pairs": pairs, "details": details},
        ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    print("wrote %s" % OUT.relative_to(ROOT))
    print("n = %d  totals = %s" % (n, totals))
    print("mean latency (s): %s" % {p: round(lat[p], 6) for p in policies})
    print("pairs (better = second policy wins, worse = first policy wins,"
          " gain = (totals[second]-totals[first])/n, lat_ratio = lat[second]/lat[first]):")
    for key, v in pairs.items():
        print("  %-22s better=%-4d worse=%-4d p=%.6g gain=%+.4f lat_ratio=%.4f ledger_ok=%s"
              % (key, v["better"], v["worse"], v["p"], v["gain"], v["lat_ratio"], v["ledger_ok"]))

    print("PREREG headline gate conditions, verbatim contract"
          " (PREREG-round4.md line 10: exact McNemar two-sided p < 0.05 AND"
          " gain >= 0.02 AND challenger/incumbent mean-latency <= 2.0),"
          " evaluated on merged-200 exactly as recorded in the pairs above:")
    for key in HEADLINE_PAIRS:
        v = pairs[key]
        incumbent, challenger = key.split("_vs_")
        c1 = v["p"] < 0.05
        c2 = v["gain"] >= 0.02
        c3 = v["lat_ratio"] is not None and v["lat_ratio"] <= 2.0
        print("  %-22s challenger=%s incumbent=%s" % (key, challenger, incumbent))
        print("      c1 p < 0.05            : p=%.6g -> %s" % (v["p"], c1))
        print("      c2 gain >= 0.02        : gain=%+.4f -> %s" % (v["gain"], c2))
        print("      c3 lat_ratio <= 2.0    : lat_ratio=%.4f -> %s" % (v["lat_ratio"], c3))
        print("      all three (gate true)  : %s" % (c1 and c2 and c3))


if __name__ == "__main__":
    main()
