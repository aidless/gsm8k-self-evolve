"""Run the no-skill arm that the SANKEN-style retention form requires.

arXiv:2609.39148 defines Retention(s) = G_test(s) - G_train(s) where G is measured
relative to a_empty, the agent with NO skill/artifact. This repository has never
measured it: every round contrasts artifact against artifact, so there is no
baseline to subtract. ``scripts/retention_report.py`` already refuses to substitute
``direct`` for the missing arm -- correctly, because ``direct`` still carries an
answer-format instruction ("Return only the final number"), so using it as a_empty
would subtract an instructed baseline from every G and report low retention for
arms that did retain.

This script measures it properly, on the same 200-question blind set the other
arms were scored on, so the numbers are comparable:

    examples/heldout40.json (40) + examples/heldout-batch2-160.json (160)
    = exactly the set behind results/rounds/round4/trackA-merged.json (meta.n = 200)

200 calls, one per question, policy "no-skill" (see the PROMPTS entry in
examples/gsm8k_evaluator.py: the question alone, no instruction, and its own
extraction rule, because the free-form arm cannot borrow the reasoning policies'
last-line convention).

Usage (from repo root):
    EVO_MODEL=qwen2.5:7b python3 scripts/run_no_skill_arm.py
    python3 scripts/run_no_skill_arm.py --limit 5     # smoke test

Deliberately reuses scripts/run_round4.py per set, so the no-skill arm inherits its
fail-closed gate: if any call fails to reach the model, the run writes an INCOMPLETE
record and exits non-zero instead of scoring a transport failure as a wrong answer.
"""
from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SETS = ["examples/heldout40.json", "examples/heldout-batch2-160.json"]
POLICY = "no-skill"
OUTS = {
    "examples/heldout40.json": "results/rounds/round4/no-skill-heldout40.json",
    "examples/heldout-batch2-160.json": "results/rounds/round4/no-skill-batch2-160.json",
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--model", default=os.environ.get("EVO_MODEL", "qwen2.5:7b"))
    a = ap.parse_args()

    rc_all = 0
    for ds in SETS:
        out = ROOT / OUTS[ds]
        cmd = [
            "python3", str(ROOT / "scripts" / "run_round4.py"),
            "--dataset", str(ROOT / ds),
            "--policies", POLICY,
            "--out", str(out),
            "--model", a.model,
            "--resume",
        ]
        if a.limit:
            cmd += ["--limit", str(a.limit)]
        print(f"== {ds} -> {OUTS[ds]}", flush=True)
        r = subprocess.run(cmd, cwd=str(ROOT))
        if r.returncode != 0:
            rc_all = r.returncode
            print(
                f"== {ds} FAILED rc={r.returncode}. Nothing was scored: the runner "
                "refused to aggregate because cells carry transport errors. "
                "Re-run the same command; --resume retries only the failed cells.",
                flush=True,
            )
        else:
            print(f"== {ds} done -> {OUTS[ds]}", flush=True)

    if rc_all:
        raise SystemExit(rc_all)
    print("\n== both sets done. Merge them and re-run the retention report:")
    print("   python3 scripts/merge_no_skill_arm.py && python3 scripts/retention_report.py")


if __name__ == "__main__":
    main()
