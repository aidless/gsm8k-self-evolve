"""Run the Amendment-1 primary Track B contrast: step-calc vs cot-zero.

This replaces the uninformative step-calc vs direct sanity check with the
informative contrast (does the frozen step-calc differ from standard zero-shot
CoT on datasets beyond GSM8K?). Per PREREG-round4.md Amendment 1.

Usage (from repo root, backend pinned to round-4):
    EVO_MODEL=qwen2.5:7b python3 scripts/run_transfer_cotzero.py

Runs, sequential & resume-safe, three paired runs (per Amendment 1, 1 call per
(policy, question)):
    step-calc vs cot-zero  on  SVAMP (1000) / MultiArith (180) / ASDiv (2249)
Outputs results/rounds/round4/transfer-cotzero-{name}.json (same out-schema as
run_round4.py, with per-call ledger asserts inside run_round4.py).
~2 x (1000+180+2249) = 6858 calls ≈ 6-8 h (the step-calc halves are ALREADY
being reused from transfer-*.json — see --reuse-note below; actually this
re-runs step-calc too unless you resume from a prior combined file, which the
sanity-check outputs do not provide). Do NOT run under memory pressure; the
SELF_ASSESSMENT flagged ~8 h budget and this machine's memory headroom.
"""
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SETS = [("svamp", 1000), ("multiarith", 180), ("asdiv", 2249)]
POLICIES = "step-calc,cot-zero"
MODEL = os.environ.get("EVO_MODEL", "qwen2.5:7b")


def main() -> None:
    for name, _n in SETS:
        dataset = ROOT / "results" / "rounds" / "round4" / "inputs" / f"{name}.json"
        out = ROOT / "results" / "rounds" / "round4" / f"transfer-cotzero-{name}.json"
        cmd = [
            "python3", str(ROOT / "scripts" / "run_round4.py"),
            "--dataset", str(dataset),
            "--policies", POLICIES,
            "--out", str(out),
            "--model", MODEL,
            "--resume",
        ]
        print(f"== {name}: {' '.join(cmd)}", flush=True)
        r = subprocess.run(cmd, cwd=str(ROOT))
        if r.returncode != 0:
            print(f"== {name} FAILED rc={r.returncode}; re-run this set with --resume", flush=True)
        else:
            print(f"== {name} done -> {out}", flush=True)


if __name__ == "__main__":
    main()