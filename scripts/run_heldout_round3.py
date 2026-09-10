"""Task 7: blind validation — challengers vs step-calc on held-out sets.

FIRST blind contact with heldout-40 / heldout-batch2-160. The held-out files
are opened ONLY inside the runner path (main(), via --batch). Nothing in this
module may read held-out content at import time, and held-out content must
NEVER feed back into challengers, lessons, or prompts — failure debugging
stays at the harness level (crash/timeout), never at the answer level.

Pairing: per question id; matched on candidate answer_policy and
details.passed/details.parsed — NEVER on details.policy equality
(known label quirk: reflect-retry emits details.policy
"reflect-reason-retry"; harmless, do not "fix").

Ledger identity per challenger per batch:
  (chall_total - incumb_total) == (better - worse)
asserted in code via evokit.stats.ledger_ok.

Latency cap (from evo.json statistical_gate.max_latency_increase = 2.0):
mean challenger latency <= 2x incumbent mean, else the challenger FAILS
the gate even if p < 0.05 — enforced in the script output
(latency_ok flag + gate_pass flag).

Promotion gate (evo.json: alpha 0.05, min_gain 0.02):
heldout-40 p < 0.05 AND gain >= 0.02 (AND latency_ok) -> run batch2-160.

Usage (cwd = repo root):
  python3 scripts/run_heldout_round3.py --batch heldout40 --out <path>
  python3 scripts/run_heldout_round3.py --batch heldout-batch2-160 --out <path>
  python3 scripts/run_heldout_round3.py --batch heldout40 --out <path> --limit 3
Backend pinned via EVO_MODEL=qwen2.5:7b.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVALUATOR = "examples/gsm8k_evaluator.py"
MODEL = "qwen2.5:7b"

sys.path.insert(0, str(ROOT))
from evokit.stats import ledger_ok, mcnemar_two_sided

BATCHES = {
    "heldout40": ROOT / "examples" / "heldout40.json",
    "heldout-batch2-160": ROOT / "examples" / "heldout-batch2-160.json",
}

ALPHA = 0.05
MIN_GAIN = 0.02
MAX_LATENCY_RATIO = 2.0

LESSONS_PATH = ROOT / "examples" / "lessons-round3.json"
TEXTGRAD_PROMPT = ROOT / "examples" / "prompts" / "textgrad-prompt.txt"


def run_policy(cases, cand_path: str, label: str):
    passed, details = 0, []
    latencies = []
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
        except Exception as e:  # noqa: BLE001 - evaluator must never stop run
            out = {"passed": False, "error": type(e).__name__}
        ok = out.get("passed") is True
        passed += ok
        lat = out.get("latency_s", 0.0) or 0.0
        latencies.append(lat)
        details.append({"id": c["id"], "passed": ok,
                        "parsed": out.get("details", {}).get("parsed"),
                        "expected": out.get("details", {}).get("expected"),
                        "latency_s": lat})
        print(f"{label} {c['id']}: {'PASS' if ok else 'FAIL'}", flush=True)
    n = len(cases)
    mean_lat = round(sum(latencies) / n, 3) if n else 0.0
    return {"passed": passed, "total": n,
            "score": round(passed / n, 4) if n else 0.0,
            "mean_latency_s": mean_lat, "details": details}


def pair_challenger(incumb_details, chall_details, incumb_total, chall_total,
                    incumb_mean_lat, chall_mean_lat, name):
    assert [x["id"] for x in incumb_details] == [x["id"] for x in chall_details], \
        f"{name}: id order mismatch"
    better = worse = both = neither = 0
    flips = []
    for x, y in zip(incumb_details, chall_details):
        xp, yp = x["passed"], y["passed"]
        if xp and not yp:
            worse += 1
            flips.append((x["id"], "incumbent-only"))
        elif not xp and yp:
            better += 1
            flips.append((x["id"], f"{name}-only"))
        elif xp and yp:
            both += 1
        else:
            neither += 1
    # Ledger identity asserted where paired counts are produced.
    assert ledger_ok(incumb_total, chall_total, better, worse), \
        f"{name}: ledger mismatch"
    p = mcnemar_two_sided(better, worse)
    gain = round(chall_total / len(incumb_details) - incumb_total / len(incumb_details), 4)
    lat_ratio = round(chall_mean_lat / incumb_mean_lat, 3) if incumb_mean_lat else None
    latency_ok = (lat_ratio is not None and lat_ratio <= MAX_LATENCY_RATIO)
    gate_pass = bool(p < ALPHA and gain >= MIN_GAIN and latency_ok)
    return {"better": better, "worse": worse,
            "both_pass": both, "both_fail": neither,
            "mcnemar_p_value": p,
            "gain": gain,
            "latency_ratio": lat_ratio,
            "latency_ok": latency_ok,
            "ledger_ok": True,
            "gate_pass": gate_pass,
            "flips": flips}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", required=True, choices=sorted(BATCHES),
                    help="heldout40 | heldout-batch2-160")
    ap.add_argument("--out", required=True, help="output JSON path")
    ap.add_argument("--limit", type=int, default=0,
                    help="dry-run: only first N questions (0 = full)")
    args = ap.parse_args()

    # Runner path: the ONLY place held-out files are opened.
    batch_path = BATCHES[args.batch]
    cases = json.load(open(batch_path, encoding="utf-8"))["cases"]
    if args.limit and args.limit > 0:
        cases = cases[:args.limit]
    n = len(cases)
    print(f"batch={args.batch} n={n} path={batch_path}", flush=True)

    cand_defs = {
        "step_calc": {"answer_policy": "step-calc"},
        "reflect_retry": {"answer_policy": "reflect-retry"},
        "textgrad": {"answer_policy": "textgrad",
                     "prompt_file": str(TEXTGRAD_PROMPT)},
    }
    cand_paths = {}
    for label, cand in cand_defs.items():
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, dir="/tmp")
        json.dump(cand, f)
        f.close()
        cand_paths[label] = f.name

    results = {}
    for label in ("step_calc", "reflect_retry", "textgrad"):
        results[label] = run_policy(cases, cand_paths[label], label)

    incumb = results["step_calc"]
    paired = {}
    for name in ("reflect_retry", "textgrad"):
        chall = results[name]
        paired[name] = pair_challenger(
            incumb["details"], chall["details"],
            incumb["passed"], chall["passed"],
            incumb["mean_latency_s"], chall["mean_latency_s"], name)

    out = {"step_calc": incumb,
           "reflect_retry": results["reflect_retry"],
           "textgrad": results["textgrad"],
           "paired": paired,
           "n": n,
           "batch": args.batch,
           "oracle": "blind-heldout",
           "model": MODEL,
           "gate": {"alpha": ALPHA, "min_gain": MIN_GAIN,
                    "max_latency_ratio": MAX_LATENCY_RATIO,
                    "rule": "p < 0.05 AND gain >= 0.02 AND latency_ok "
                            "-> run batch2-160 / promote only if merged "
                            "p < 0.05 with ledger identity holding"}}
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")
    print(json.dumps({
        "batch": args.batch, "n": n,
        "step_calc": incumb["passed"],
        "reflect_retry": results["reflect_retry"]["passed"],
        "textgrad": results["textgrad"]["passed"],
        "paired": {k: {kk: v[kk] for kk in
                        ("better", "worse", "both_pass", "both_fail",
                         "mcnemar_p_value", "gain", "latency_ratio",
                         "latency_ok", "ledger_ok", "gate_pass")}
                   for k, v in paired.items()}}), flush=True)


if __name__ == "__main__":
    main()
