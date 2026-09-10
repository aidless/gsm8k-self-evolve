"""Task 5 Step 2: pilot step-calc vs reflect-retry on train-40 (paired).

Informational ONLY: train wins NEVER promote. Gate for proceeding to Task 7
is pilot showing better >= worse (weak signal, NOT a promotion claim).

Reads examples/gsm8k40.json ONLY (train oracle allowed). NEVER reads
heldout40.json or heldout-batch2-160.json. reflect-retry consumes the frozen
lessons in examples/lessons-round3.json via EVO_LESSONS. Backend pinned via
EVO_MODEL=qwen2.5:7b.

Ledger identity (reflect_total - step_total == better - worse) is asserted
in code where the paired counts are produced.

Writes results/rounds/round3/pilot-train40.json with n == 40 and per-id
details for both policies; prints better/worse/p.

Usage: python3 scripts/run_pilot_train.py  (cwd = repo root)
"""
import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRAIN_PATH = ROOT / "examples" / "gsm8k40.json"
LESSONS_PATH = ROOT / "examples" / "lessons-round3.json"
OUT_PATH = ROOT / "results" / "rounds" / "round3" / "pilot-train40.json"
EVALUATOR = "examples/gsm8k_evaluator.py"
MODEL = "qwen2.5:7b"

POLICIES = {
    "step_calc": {"answer_policy": "step-calc"},
    "reflect_retry": {"answer_policy": "reflect-retry"},
}


def run_policy(cases, cand_path: str, label: str):
    passed, details = 0, []
    for c in cases:
        env = dict(os.environ, EVO_CANDIDATE=cand_path,
                   EVO_INPUT=json.dumps(c["input"], ensure_ascii=False),
                   EVO_EXPECTED=json.dumps(c["expected"]),
                   EVO_CASE_ID=c["id"],
                   EVO_MODEL=MODEL,
                   EVO_LESSONS=str(LESSONS_PATH))
        try:
            r = subprocess.run([sys.executable, EVALUATOR],
                               cwd=ROOT, env=env, capture_output=True,
                               text=True, timeout=300)
            out = json.loads(r.stdout.strip())
        except Exception as e:  # noqa: BLE001 - evaluator must never stop pilot
            out = {"passed": False, "error": type(e).__name__}
        ok = out.get("passed") is True
        passed += ok
        details.append({"id": c["id"], "passed": ok,
                        "parsed": out.get("details", {}).get("parsed"),
                        "expected": out.get("details", {}).get("expected")})
        print(f"{label} {c['id']}: {'PASS' if ok else 'FAIL'}", flush=True)
    return {"passed": passed, "total": len(cases),
            "score": round(passed / len(cases), 4), "details": details}


def mcnemar_two_sided(better: int, worse: int) -> float:
    n = better + worse
    if n == 0:
        return 1.0
    k = min(better, worse)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def main() -> None:
    cases = json.load(open(TRAIN_PATH, encoding="utf-8"))["cases"]
    assert len(cases) == 40, f"expected 40 train cases, got {len(cases)}"
    assert LESSONS_PATH.exists(), f"missing frozen lessons: {LESSONS_PATH}"

    cand_paths = {}
    for label, cand in POLICIES.items():
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, dir="/tmp")
        json.dump(cand, f)
        f.close()
        cand_paths[label] = f.name

    results = {}
    for label in ("step_calc", "reflect_retry"):
        results[label] = run_policy(cases, cand_paths[label], label)

    a = results["step_calc"]["details"]
    b = results["reflect_retry"]["details"]
    assert [x["id"] for x in a] == [x["id"] for x in b], "id order mismatch"
    better = worse = both = neither = 0
    flips = []
    for x, y in zip(a, b):
        xp, yp = x["passed"], y["passed"]
        if xp and not yp:
            worse += 1
            flips.append((x["id"], "step-only"))
        elif not xp and yp:
            better += 1
            flips.append((x["id"], "reflect-only"))
        elif xp and yp:
            both += 1
        else:
            neither += 1

    # Ledger identity asserted where paired counts are produced.
    step_total = results["step_calc"]["passed"]
    reflect_total = results["reflect_retry"]["passed"]
    assert (reflect_total - step_total) == (better - worse), "ledger mismatch"

    p = mcnemar_two_sided(better, worse)
    paired = {"reflect_better": better, "step_better": worse,
              "both_pass": both, "both_fail": neither,
              "mcnemar_p_value": p, "flips": flips,
              "gate_better_ge_worse": better >= worse,
              "note": "train-40 pilot, informational only; "
                      "train wins NEVER promote"}

    out = {"step_calc": results["step_calc"],
           "reflect_retry": results["reflect_retry"],
           "paired": paired,
           "n": len(cases),
           "oracle": "train-only",
           "model": MODEL}
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")
    print(json.dumps({"step_calc": step_total, "reflect_retry": reflect_total,
                      "better": better, "worse": worse,
                      "both_pass": both, "both_fail": neither, "p": p,
                      "gate_better_ge_worse": better >= worse}),
          flush=True)


if __name__ == "__main__":
    main()
