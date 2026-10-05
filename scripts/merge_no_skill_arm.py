"""Merge the two no-skill runs into the n=200 file the retention form needs.

Same discipline as scripts/merge_trackA.py, same 200-question blind set, so a_empty
is measured on exactly the questions every other arm was scored on:

    examples/heldout40.json (40) + examples/heldout-batch2-160.json (160)
    == the set behind results/rounds/round4/trackA-merged.json (meta.n = 200)

Reads results/rounds/round4/no-skill-heldout40.json and
results/rounds/round4/no-skill-batch2-160.json, re-derives each file's own totals
from its per-id details (asserting they equal the recorded ones, so a truncated or
hand-edited result file cannot pass as evidence), asserts 200 unique ids with zero
overlap, and writes results/rounds/round4/no-skill-merged.json in the same
{meta, totals, details} shape the runner emits.

A single policy means no pairs: the purpose of this file is the baseline rate, not
a contrast. The contrast against every other arm is recomputed in
scripts/retention_report.py from per-id data, where McNemar can be exact.

Pure recompute: no model calls, no re-runs, no re-judgment.

Usage: python3 scripts/merge_no_skill_arm.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ROUND = ROOT / "results" / "rounds" / "round4"
INPUTS = [ROUND / "no-skill-heldout40.json", ROUND / "no-skill-batch2-160.json"]
OUT = ROUND / "no-skill-merged.json"
EXPECTED_N = 200
POLICY = "no-skill"


def verify_source(path: Path) -> dict:
    """Re-derive the totals from the file's own details and assert they match."""
    data = json.loads(path.read_text(encoding="utf-8"))
    assert set(data) == {"meta", "totals", "pairs", "details"}, (
        "%s: unexpected top-level keys %s; a result file must carry exactly "
        "meta/totals/pairs/details" % (path.name, sorted(data)))
    assert data["meta"]["policies"] == [POLICY], (
        "%s: policies is %s, expected exactly ['%s']; another arm's file "
        "substituted here would be exactly the substitution "
        "scripts/retention_report.py refuses to make"
        % (path.name, data["meta"]["policies"], POLICY))
    assert len(data["details"]) == data["meta"]["n"], (
        "%s: meta.n is %s but details holds %d rows; the file is truncated or "
        "hand-edited" % (path.name, data["meta"]["n"], len(data["details"])))
    recomputed = sum(1 for row in data["details"].values() if row[POLICY]["passed"])
    assert recomputed == data["totals"][POLICY], (
        "%s: totals claims %s but recomputing from details gives %d; refusing a "
        "file whose aggregate disagrees with its own per-id evidence"
        % (path.name, data["totals"][POLICY], recomputed))
    # A transport failure must never be counted as a wrong answer. The runner's
    # fail-closed gate refuses to emit totals at all in that case, so reaching
    # this point with a cell carrying an error means the gate regressed.
    bad = [q for q, row in data["details"].items() if row[POLICY].get("error")]
    assert not bad, (path.name, "cells carrying a transport error", bad[:5])
    print("verified %-28s n=%-4d passed=%d/%d" % (
        path.name, data["meta"]["n"], data["totals"][POLICY], data["meta"]["n"]))
    return data


def main() -> None:
    details: dict = {}
    datasets = []
    model = None
    for path in INPUTS:
        data = verify_source(path)
        if model is None:
            model = data["meta"]["model"]
        else:
            assert data["meta"]["model"] == model, path.name
        overlap = set(details) & set(data["details"])
        assert not overlap, ("id overlap between input files", sorted(overlap)[:5])
        details.update(data["details"])
        datasets.append(data["meta"]["dataset"])

    assert len(details) == EXPECTED_N, (
        "expected %d unique ids, got %d" % (EXPECTED_N, len(details)))

    passed = sum(1 for row in details.values() if row[POLICY]["passed"])
    # run_round4.run_one() returns {passed, latency, parsed, [error]} -- `parsed` sits
    # at the cell's top level, not under a nested "details" key (that is the shape
    # gsm8k_evaluator.py prints on stdout, which run_one flattens before writing).
    unparsed = sum(1 for row in details.values()
                   if row[POLICY].get("parsed") is None)

    OUT.write_text(json.dumps({
        "meta": {"dataset": datasets, "policies": [POLICY], "model": model,
                 "n": len(details), "sources": [str(p.relative_to(ROOT)) for p in INPUTS]},
        "totals": {POLICY: passed},
        "pairs": {},
        "details": details}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    print("wrote %s" % OUT.relative_to(ROOT))
    print("n = %d  a_empty = %d/%d = %.6f" % (len(details), passed, len(details),
                                               passed / len(details)))
    print("cells where no number could be parsed at all: %d" % unparsed)
    print("\nNow re-run the retention report; it will pick this up as the measured")
    print("baseline instead of reporting the blocking gap:")
    print("    python3 scripts/retention_report.py")


if __name__ == "__main__":
    main()
