"""Round-2 held-out: concise-reason (round1 winner) vs step-calc (round2 winner).
Same heldout40, same time window, paired. Paired exact McNemar computed in-place.
"""
import json, os, subprocess, sys, math
from pathlib import Path

ROOT = Path("/root/exp-gsm8k")
CASES = json.load(open(ROOT / "examples" / "heldout40.json"))["cases"]
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
        det.append({"id": c["id"], "passed": ok, "parsed": out.get("details", {}).get("parsed"),
                    "expected": out.get("details", {}).get("expected")})
        print(f"{name} {c['id']}: {'PASS' if ok else 'FAIL'}", flush=True)
    results[name] = {"passed": passed, "total": len(CASES),
                     "score": round(passed / len(CASES), 4), "details": det}

a = results["concise-reason"]["details"]
b = results["step-calc"]["details"]
better = worse = both = neither = 0
flips = []
for x, y in zip(a, b):
    xp, yp = x["passed"], y["passed"]
    if xp and not yp:
        worse += 1; flips.append((x["id"], "concise-only"))
    elif not xp and yp:
        better += 1; flips.append((x["id"], "step-only"))
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
paired = {"step_wins_consecutive": better, "concise_wins_step": worse,
          "step_calc_better": better, "concise_reason_better": worse,
          "both_pass": both, "both_fail": neither,
          "mcnemar_p_value": p, "flips": flips}

out = {"concise_reason": results["concise-reason"], "step_calc": results["step-calc"],
       "paired": paired}
json.dump(out, open(ROOT / "heldout-round2-result.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps({"concise": results["concise-reason"]["passed"],
                  "step_calc": results["step-calc"]["passed"],
                  "paired": {k: paired[k] for k in
                             ("step_calc_better", "concise_reason_better",
                              "both_pass", "both_fail", "mcnemar_p_value")}}), flush=True)
