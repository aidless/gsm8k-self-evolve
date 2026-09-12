"""Incremental paired runner — same statistics as run_round4.py, but the output
file is re-written after EVERY single (policy, question) call. An interrupted
long spend (Track-B ≈ 8 h / Track-C multi-model) therefore loses at most one
call, and a re-run resumes exactly where it stopped.

Usage:
  python3 scripts/run_paired_incremental.py --dataset D.json --policies a,b,c \
      --out O.json [--model M] [--limit N]

Semantics identical to run_round4.py: pairs computed over COMPLETE rows only,
exact two-sided McNemar, ledger identity asserted in code (evokit.stats).
Stdlib only; the model call is run_round4.run_one (single source of truth).
"""
import argparse
import json
import sys
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from evokit.stats import ledger_ok, mcnemar_two_sided
from run_round4 import run_one


def complete_rows(details: dict, policies: list) -> dict:
    return {qid: r for qid, r in details.items() if all(p in r for p in policies)}


def compute(details: dict, policies: list):
    done = complete_rows(details, policies)
    n = len(done)
    totals = {p: sum(1 for r in done.values() if r[p]["passed"]) for p in policies}
    lat = {p: sum(r[p]["latency"] for r in done.values()) / max(n, 1) for p in policies}
    pairs = {}
    for x, y in combinations(policies, 2):
        better = sum(1 for r in done.values() if r[y]["passed"] and not r[x]["passed"])
        worse = sum(1 for r in done.values() if r[x]["passed"] and not r[y]["passed"])
        assert ledger_ok(totals[x], totals[y], better, worse), (x, y)
        pairs["%s_vs_%s" % (x, y)] = {
            "better": better, "worse": worse,
            "p": mcnemar_two_sided(better, worse),
            "gain": (totals[y] - totals[x]) / n if n else 0.0,
            "ledger_ok": True, "lat_x": lat[x], "lat_y": lat[y],
            "lat_ratio": (lat[y] / lat[x]) if lat[x] else None}
    return done, totals, pairs


def save(path: Path, dataset: str, policies: list, model: str,
         details: dict, progress: dict) -> None:
    done, totals, pairs = compute(details, policies)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "meta": {"dataset": dataset, "policies": policies, "model": model,
                 "n": len(done), "progress": progress},
        "totals": totals, "pairs": pairs, "details": details},
        ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--policies", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default=None)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    model = a.model or "qwen2.5:7b"
    policies = a.policies.split(",")
    cases = json.loads(Path(a.dataset).read_text(encoding="utf-8"))["cases"]
    if a.limit:
        cases = cases[: a.limit]
    out = Path(a.out)

    details: dict = {}
    if out.exists():
        try:
            details = json.loads(out.read_text(encoding="utf-8")).get("details", {})
        except Exception:
            details = {}
    total = len(cases) * len(policies)
    done_calls = sum(1 for r in details.values() for p in policies if p in r)
    print("resume: %d/%d calls already done" % (done_calls, total), flush=True)

    for c in cases:
        qid = c["id"]
        row = details.setdefault(qid, {})
        for pol in policies:
            if pol in row:
                continue
            row[pol] = run_one(pol, None, c["input"], float(c["expected"]), model)
            done_calls += 1
            save(out, a.dataset, policies, model, details,
                 {"calls_done": done_calls, "calls_total": total,
                  "questions_done": len(complete_rows(details, policies))})
            print(json.dumps({"qid": qid, "policy": pol, "passed": row[pol]["passed"],
                              "call": done_calls, "of": total}), flush=True)

    done, totals, pairs = compute(details, policies)
    print("FINAL model=%s n=%d totals=%s" % (model, len(done), totals), flush=True)


if __name__ == "__main__":
    main()