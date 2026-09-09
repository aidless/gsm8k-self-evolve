"""Held-out validation: direct (seed) vs concise-reason (promoted active).
Runs on cloud. One model task at a time. Usage:
  python3 run_heldout.py  (cwd=/root/exp-gsm8k, uses system python3)
Writes /root/exp-gsm8k/heldout-result.json
"""
import json, os, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path("/root/exp-gsm8k")
CASES = json.load(open(ROOT / "examples" / "heldout40.json"))["cases"]
POLICIES = {
    "direct-baseline": ROOT / "seed.json",
    "concise-reason-promoted": ROOT / ".evo" / "active.json",
}
print("active candidate:", json.load(open(ROOT / ".evo" / "active.json")), flush=True)

results = {}
for name, cand in POLICIES.items():
    passed, details = 0, []
    for c in CASES:
        env = dict(os.environ, EVO_CANDIDATE=str(cand),
                   EVO_INPUT=json.dumps(c["input"], ensure_ascii=False),
                   EVO_EXPECTED=json.dumps(c["expected"]),
                   EVO_CASE_ID=c["id"])
        try:
            r = subprocess.run([sys.executable, "examples/gsm8k_evaluator.py"],
                               cwd=ROOT, env=env, capture_output=True,
                               text=True, timeout=150)
            out = json.loads(r.stdout.strip())
        except Exception as e:
            out = {"passed": False, "error": type(e).__name__}
        ok = out.get("passed") is True
        passed += ok
        details.append({"id": c["id"], "passed": ok})
        print(f"{name} {c['id']}: {'PASS' if ok else 'FAIL'}", flush=True)
    results[name] = {"passed": passed, "total": len(CASES),
                     "score": round(passed / len(CASES), 4), "details": details}

json.dump(results, open(ROOT / "heldout-result.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps({k: v["passed"] for k, v in results.items()}), flush=True)
