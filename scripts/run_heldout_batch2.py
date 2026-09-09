"""Batch-2 held-out (160 fresh GSM8K-test items, seed=20260908, excludes the 80 used).
concise-reason (round1) vs step-calc (round2 active). Paired exact McNemar in-place.
"""
import json, os, subprocess, sys, math
from pathlib import Path

ROOT = Path("/root/exp-gsm8k")
CASES = json.load(open(ROOT / "examples" / "heldout-batch2-160.json"))["cases"]
CANDIDATES = {
    "concise-reason": ROOT / ".evo" / "before-round2" / "active.round1.json",
    "step-calc": ROOT / ".evo" / "active.json",
}

results = {}
for name, cand in CANDIDATES.items():
    passed, det = 0, []
    for c in CASES:
        env = dict(os.environ, EVO_CANDIDATE=str(cand),
                   EVO_INPUT=json.dumps(c["input"], ensure_ascii=False),
                   EVO_EXPECTED=json.dumps(c["expected"]),
                   EVO_CASE_ID=c["id"])
        try:
            r = subprocess.run([sys.executable, "examples/gsm8k_evaluator.py"],
                               cwd=ROOT, env=env, capture_output=True, text=True, timeout=150)
            out = json.loads(r.stdout.strip())
        except Exception as e:
            out = {"passed": False, "error": type(e).__name__}
        ok = out.get("passed") is True
        passed += ok
        det.append({"id": c["id"], "passed": ok})
        print(f"{name} {c['id']}: {'PASS' if ok else 'FAIL'}", flush=True)
    results[name] = {"passed": passed, "total": len(CASES),
                     "score": round(passed / len(CASES), 4), "details": det}

a = results["concise-reason"]["details"]
b = results["step-calc"]["details"]
better = worse = both = neither = 0
for x, y in zip(a, b):
    xp, yp = x["passed"], y["passed"]
    if xp and not yp:
        worse += 1
    elif not xp and yp:
        better += 1
    elif xp and yp:
        both += 1
    else:
        neither += 1

def binom_tail(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)

p = binom_tail(better, worse)
# 同时给出比例和精确计数
out = {"concise_reason": {k: results["concise-reason"][k] for k in ("passed","total","score")},
       "step_calc": {k: results["step-calc"][k] for k in ("passed","total","score")},
       "paired": {"step_better": better, "concise_better": worse,
                  "both_pass": both, "both_fail": neither,
                  "discordant_n": better + worse, "mcnemar_p_value": p}}
json.dump(out, open(ROOT / "heldout-batch2-result.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps({"concise": results["concise-reason"]["passed"],
                  "step_calc": results["step-calc"]["passed"],
                  "paired": {k: out["paired"][k] for k in
                             ("step_better", "concise_better", "both_pass",
                              "both_fail", "mcnemar_p_value")}}), flush=True)
