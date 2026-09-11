"""Generic paired runner for Round-4 (tracks A+C, reusable for transfer).

Usage: python3 scripts/run_round4.py --dataset <path.json> --policies a,b,c
  --out <path.json> [--limit N] [--resume]
Dataset schema: {"cases": [{"id","input","expected"}]}. Each (policy, case) runs
once via the evaluator subprocess (EVO_MODEL from env, default qwen2.5:7b).
Pairs: every unordered policy pair -> better/worse/mcnemar p/gain/latency ratio,
ledger asserted in code. --resume skips (policy,id) already in out file.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from evokit.stats import ledger_ok, mcnemar_two_sided


def run_one(policy: str, prompt_file: str | None, question: str, expected: float,
            model: str) -> dict:
    cand = {"answer_policy": policy}
    if prompt_file:
        cand["prompt_file"] = prompt_file
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(cand, f)
        cand_path = f.name
    env = dict(os.environ, EVO_MODEL=model, EVO_CANDIDATE=cand_path,
               EVO_INPUT=json.dumps(question), EVO_EXPECTED=json.dumps(expected))
    try:
        p = subprocess.run(["python3", str(ROOT / "examples" / "gsm8k_evaluator.py")],
                           capture_output=True, text=True, env=env, cwd=str(ROOT),
                           timeout=150)
        out = json.loads(p.stdout)
        return {"passed": bool(out["passed"]),
                "latency": float(out.get("latency_s", 0.0)),
                "parsed": out.get("details", {}).get("parsed")}
    except Exception as exc:
        return {"passed": False, "latency": 0.0, "parsed": None,
                "error": type(exc).__name__}
    finally:
        Path(cand_path).unlink(missing_ok=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--policies", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--model", default=os.environ.get("EVO_MODEL", "qwen2.5:7b"))
    a = ap.parse_args()
    policies = a.policies.split(",")
    cases = json.load(Path(a.dataset).open(encoding="utf-8"))["cases"]
    if a.limit:
        cases = cases[: a.limit]
    out_path = Path(a.out)
    done: dict = {}
    if a.resume and out_path.exists():
        done = json.load(out_path.open(encoding="utf-8")).get("details", {})
    details: dict = {k: v for k, v in done.items()}
    for c in cases:
        qid = c["id"]
        row = details.get(qid, {})
        for pol in policies:
            if pol not in row:
                row[pol] = run_one(pol, None, c["input"], float(c["expected"]), a.model)
                print(json.dumps({"id": qid, "policy": pol, "passed": row[pol]["passed"]}),
                      flush=True)
        details[qid] = row
    totals = {pol: sum(1 for qid in details for _ in [details[qid][pol]]
                       if details[qid][pol]["passed"]) for pol in policies}
    n = len(details)
    lat = {pol: sum(details[q][pol]["latency"] for q in details) / max(n, 1)
           for pol in policies}
    pairs = {}
    for x, y in combinations(policies, 2):
        better = sum(1 for q in details
                     if details[q][y]["passed"] and not details[q][x]["passed"])
        worse = sum(1 for q in details
                    if details[q][x]["passed"] and not details[q][y]["passed"])
        assert ledger_ok(totals[x], totals[y], better, worse), (x, y)
        pairs["%s_vs_%s" % (x, y)] = {
            "better": better, "worse": worse,
            "p": mcnemar_two_sided(better, worse),
            "gain": (totals[y] - totals[x]) / n if n else 0.0,
            "ledger_ok": True, "lat_x": lat[x], "lat_y": lat[y],
            "lat_ratio": (lat[y] / lat[x]) if lat[x] else None}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({
        "meta": {"dataset": a.dataset, "policies": policies, "model": a.model, "n": n},
        "totals": totals, "pairs": pairs, "details": details},
        ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("wrote", out_path, totals)


if __name__ == "__main__":
    main()
