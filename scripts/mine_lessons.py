"""Task 5 Step 1: mine frozen lessons from step-calc train failures (train oracle OK).

Runs step-calc over the 40 train cases (examples/gsm8k40.json) via the
evaluator subprocess protocol (EVO_CANDIDATE/EVO_INPUT/EVO_EXPECTED, same as
run_heldout_round2.py). For each failing case, asks the model in one sentence
what arithmetic mistake likely caused the wrong answer. Keeps the first 8
distinct sentences and writes examples/lessons-round3.json as:
  {"lessons": [...<=8 strings], "mined_from": "gsm8k40", "oracle": "train-only"}

Blindness: reads examples/gsm8k40.json ONLY. NEVER reads heldout40.json or
heldout-batch2-160.json. Backend pinned via EVO_MODEL=qwen2.5:7b.

Usage: python3 scripts/mine_lessons.py  (cwd = repo root)
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRAIN_PATH = ROOT / "examples" / "gsm8k40.json"
OUT_PATH = ROOT / "examples" / "lessons-round3.json"
EVALUATOR = "examples/gsm8k_evaluator.py"
MODEL = "qwen2.5:7b"
OLLAMA_URL = os.environ.get("EVO_OLLAMA_URL", "http://127.0.0.1:11434/api/generate")


def call_model(prompt: str, timeout: int = 90) -> str:
    body = json.dumps({
        "model": MODEL, "prompt": prompt, "stream": False,
        "options": {"temperature": 0},
    }).encode()
    req = urllib.request.Request(OLLAMA_URL, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.load(resp)
    return data.get("response", "")


def main() -> None:
    cases = json.load(open(TRAIN_PATH, encoding="utf-8"))["cases"]
    assert len(cases) == 40, f"expected 40 train cases, got {len(cases)}"

    cand_file = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, dir="/tmp")
    json.dump({"answer_policy": "step-calc"}, cand_file)
    cand_file.close()

    failures = []
    for c in cases:
        env = dict(os.environ, EVO_CANDIDATE=cand_file.name,
                   EVO_INPUT=json.dumps(c["input"], ensure_ascii=False),
                   EVO_EXPECTED=json.dumps(c["expected"]),
                   EVO_CASE_ID=c["id"],
                   EVO_MODEL=MODEL)
        try:
            r = subprocess.run([sys.executable, EVALUATOR],
                               cwd=ROOT, env=env, capture_output=True,
                               text=True, timeout=150)
            out = json.loads(r.stdout.strip())
        except Exception as e:  # noqa: BLE001 - evaluator must never stop mining
            out = {"passed": False, "error": type(e).__name__}
        ok = out.get("passed") is True
        print(f"step-calc {c['id']}: {'PASS' if ok else 'FAIL'}", flush=True)
        if not ok:
            failures.append({
                "id": c["id"],
                "question": c["input"],
                "trace": str(out.get("details", {}).get("raw", ""))[:500],
            })

    print(f"train failures: {len(failures)}/{len(cases)}", flush=True)

    lessons, seen = [], set()
    for f in failures:
        if len(lessons) >= 8:
            break
        q = ("In one sentence, what arithmetic mistake likely caused this "
             "wrong answer? Question: %s Wrong trace: %s"
             % (f["question"], f["trace"] or "(no trace)"))
        try:
            sent = call_model(q).strip().splitlines()
            sent = " ".join(s.strip() for s in sent if s.strip())
        except Exception as e:  # noqa: BLE001 - one bad call must not stop mining
            print(f"lesson call failed for {f['id']}: {type(e).__name__}",
                  flush=True)
            continue
        key = sent.lower()
        if sent and key not in seen:
            seen.add(key)
            lessons.append(sent)
            print(f"lesson {len(lessons)} from {f['id']}: {sent[:120]}",
                  flush=True)
        time.sleep(1)

    payload = {"lessons": lessons[:8], "mined_from": "gsm8k40",
               "oracle": "train-only"}
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")
    print(json.dumps({"lessons_kept": len(payload["lessons"]),
                      "out": str(OUT_PATH)}), flush=True)


if __name__ == "__main__":
    main()
