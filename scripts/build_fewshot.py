"""Build frozen few-shot exemplars from train file order (no cherry-picking).

Takes gsm8k-01..04 (first 4 cases in file order), runs step-calc on each via
the evaluator subprocess protocol, keeps traces that reach expected (up to 3
tries), else falls back to a minimal Q+Answer exemplar. Writes
examples/prompts/fewshot-4.txt with a frozen header. Oracle on train only.
"""
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRAIN = ROOT / "examples" / "gsm8k40.json"
OUT = ROOT / "examples" / "prompts" / "fewshot-4.txt"
CAND = {"answer_policy": "step-calc"}


def run_case(question: str, expected: float) -> dict:
    cand_path = ROOT / ".tmp-fewshot-cand.json"
    cand_path.write_text(json.dumps(CAND), encoding="utf-8")
    env = dict(os.environ, EVO_MODEL=os.environ.get("EVO_MODEL", "qwen2.5:7b"),
               EVO_CANDIDATE=str(cand_path),
               EVO_INPUT=json.dumps(question),
               EVO_EXPECTED=json.dumps(expected))
    last = None
    for _ in range(3):
        p = subprocess.run(["python3", str(ROOT / "examples" / "gsm8k_evaluator.py")],
                           capture_output=True, text=True, env=env, cwd=str(ROOT),
                           timeout=150)
        last = json.loads(p.stdout)
        if last.get("passed"):
            break
    cand_path.unlink(missing_ok=True)
    return last


def main() -> None:
    cases = json.load(TRAIN.open(encoding="utf-8"))["cases"][:4]
    assert [c["id"] for c in cases] == ["gsm8k-01", "gsm8k-02", "gsm8k-03", "gsm8k-04"], "train file order changed"
    blocks = []
    for c in cases:
        r = run_case(c["input"], float(c["expected"]))
        if r.get("passed"):
            blocks.append("Q: %s\n%s" % (c["input"], r["details"]["raw"]))
        else:
            blocks.append("Q: %s\nAnswer: %s" % (c["input"], c["expected"]))
    header = '{"built_from": "gsm8k-01..04 file order", "oracle": "train-only", "frozen": true}'
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(header + "\n\n" + "\n\n".join(blocks) + "\n", encoding="utf-8")
    print("wrote", OUT, "fallback-minimal:", sum(1 for b in blocks if b.count("\n") == 1))


if __name__ == "__main__":
    main()
