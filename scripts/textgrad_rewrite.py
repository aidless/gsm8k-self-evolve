"""Task 6 Step 2: TextGrad-lite prompt rewrite, frozen to a file (train oracle OK).

Concept reimplementation of the TextGrad loop (textual loss -> textual
gradient -> update); zero verbatim upstream files (see
third_party/textgrad/NOTICE). 2 iterations max:

  (a) textual loss = list of failing train cases for the current instruction;
  (b) textual gradient = one model call
      "Given these failures of the current instruction: <prompt>,
       <failures>, propose 3 concrete edits to the instruction";
  (c) update = a separate model call rewriting the prompt with the best edit;
      the rewrite is validated on train-40 via the evaluator subprocess
      (candidate {"answer_policy": "textgrad", "prompt_file": <tmp>});
      kept iff train score does not drop.

Consumes train-40 step-calc failures, NOT examples/lessons-round3.json.
Reads examples/gsm8k40.json ONLY. NEVER reads heldout40.json or
heldout-batch2-160.json. Backend pinned via EVO_MODEL=qwen2.5:7b.

The winner is written to examples/prompts/textgrad-prompt.txt with header
{"rewritten_from": "step-calc", "oracle": "train-only", "frozen": true}.
Format-safety note: the evaluator resolves the file with
Path(...).read_text().format(q=question), so every literal brace except the
single {q} placeholder would raise KeyError at .format time. The header is
therefore stored brace-escaped (doubled); .format renders it back to the
exact single-brace JSON for the model, and the raw file still contains the
exact key substrings for grep verification. Rewrites are rejected unless
they contain exactly one {q} and no other braces.

Usage: python3 scripts/textgrad_rewrite.py  (cwd = repo root)
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
OUT_PATH = ROOT / "examples" / "prompts" / "textgrad-prompt.txt"
EVALUATOR = "examples/gsm8k_evaluator.py"
MODEL = "qwen2.5:7b"
OLLAMA_URL = os.environ.get("EVO_OLLAMA_URL", "http://127.0.0.1:11434/api/generate")

BASE_PROMPT = (
    "{q}\nSolve step by step, writing each arithmetic step on its own line, "
    "then write the final number alone on the last line prefixed with 'Answer:'."
)

HEADER_JSON = '{"rewritten_from": "step-calc", "oracle": "train-only", "frozen": true}'
# Brace-escaped so str.format(q=...) renders the exact single-brace JSON.
HEADER_ESCAPED = HEADER_JSON.replace("{", "{{").replace("}", "}}")


def call_model(prompt: str, timeout: int = 120) -> str:
    body = json.dumps({
        "model": MODEL, "prompt": prompt, "stream": False,
        "options": {"temperature": 0},
    }).encode()
    req = urllib.request.Request(OLLAMA_URL, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.load(resp)
    return data.get("response", "")


def eval_prompt(cases, prompt_text: str, label: str):
    """Validate a prompt string on train-40 via the evaluator (textgrad branch).

    Writes the prompt to a temp file (format-safe: single {q}, no other
    braces) and runs the evaluator subprocess per case. Returns
    (score:int, failures:list).
    """
    assert prompt_text.count("{q}") == 1, "prompt must contain exactly one {q}"
    assert prompt_text.count("{") == 1 and prompt_text.count("}") == 1, \
        "prompt must contain no braces besides {q}"
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False,
                                      dir="/tmp", encoding="utf-8")
    tmp.write(prompt_text)
    tmp.close()
    cand = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False,
                                       dir="/tmp")
    json.dump({"answer_policy": "textgrad", "prompt_file": tmp.name}, cand)
    cand.close()
    score, failures = 0, []
    for c in cases:
        env = dict(os.environ, EVO_CANDIDATE=cand.name,
                   EVO_INPUT=json.dumps(c["input"], ensure_ascii=False),
                   EVO_EXPECTED=json.dumps(c["expected"]),
                   EVO_CASE_ID=c["id"],
                   EVO_MODEL=MODEL)
        try:
            r = subprocess.run([sys.executable, EVALUATOR],
                               cwd=ROOT, env=env, capture_output=True,
                               text=True, timeout=300)
            out = json.loads(r.stdout.strip())
        except Exception as e:  # noqa: BLE001 - evaluator must never stop rewrite
            out = {"passed": False, "error": type(e).__name__}
        ok = out.get("passed") is True
        score += ok
        print(f"{label} {c['id']}: {'PASS' if ok else 'FAIL'}", flush=True)
        if not ok:
            failures.append({
                "id": c["id"],
                "question": c["input"],
                "expected": c["expected"],
                "trace": str(out.get("details", {}).get("raw", ""))[:300],
            })
    return score, failures


def eval_policy(cases, policy: str, label: str):
    """Baseline sweep for a fixed registry policy (step-calc)."""
    cand = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False,
                                       dir="/tmp")
    json.dump({"answer_policy": policy}, cand)
    cand.close()
    score, failures = 0, []
    for c in cases:
        env = dict(os.environ, EVO_CANDIDATE=cand.name,
                   EVO_INPUT=json.dumps(c["input"], ensure_ascii=False),
                   EVO_EXPECTED=json.dumps(c["expected"]),
                   EVO_CASE_ID=c["id"],
                   EVO_MODEL=MODEL)
        try:
            r = subprocess.run([sys.executable, EVALUATOR],
                               cwd=ROOT, env=env, capture_output=True,
                               text=True, timeout=300)
            out = json.loads(r.stdout.strip())
        except Exception as e:  # noqa: BLE001 - evaluator must never stop rewrite
            out = {"passed": False, "error": type(e).__name__}
        ok = out.get("passed") is True
        score += ok
        print(f"{label} {c['id']}: {'PASS' if ok else 'FAIL'}", flush=True)
        if not ok:
            failures.append({
                "id": c["id"],
                "question": c["input"],
                "expected": c["expected"],
                "trace": str(out.get("details", {}).get("raw", ""))[:300],
            })
    return score, failures


def is_format_safe(text: str) -> bool:
    return text.count("{q}") == 1 and text.count("{") == 1 and text.count("}") == 1


def main() -> None:
    cases = json.load(open(TRAIN_PATH, encoding="utf-8"))["cases"]
    assert len(cases) == 40, f"expected 40 train cases, got {len(cases)}"

    base_score, base_failures = eval_policy(cases, "step-calc", "base")
    print(json.dumps({"baseline": base_score, "n": len(cases),
                      "failures": len(base_failures)}), flush=True)

    current, cur_score, cur_failures = BASE_PROMPT, base_score, base_failures
    history = [{"iter": 0, "score": base_score, "kept": True,
                "note": "step-calc baseline"}]

    for it in (1, 2):
        if not cur_failures:
            print(f"iter{it}: no failures left, stopping", flush=True)
            history.append({"iter": it, "score": cur_score, "kept": False,
                            "note": "no failures, loop stopped"})
            break
        # (a) textual loss = failing train cases (cap 8 for context).
        loss_cases = cur_failures[:8]
        loss_txt = "\n".join(
            "- id=%s expected=%s\n  question: %s\n  wrong trace: %s"
            % (f["id"], f["expected"], f["question"], f["trace"] or "(no trace)")
            for f in loss_cases)
        # (b) textual gradient: one model call proposing 3 concrete edits.
        grad_q = ("Given these failures of the current instruction:\n"
                  "INSTRUCTION:\n%s\n\nFAILURES:\n%s\n\n"
                  "propose 3 concrete edits to the instruction. "
                  "Number them 1-3, one sentence each, most promising first."
                  % (current, loss_txt))
        try:
            gradient = call_model(grad_q).strip()
        except Exception as e:  # noqa: BLE001 - one bad call ends the loop
            print(f"iter{it}: gradient call failed: {type(e).__name__}",
                  flush=True)
            history.append({"iter": it, "score": cur_score, "kept": False,
                            "note": "gradient call failed"})
            break
        print(f"iter{it} gradient:\n{gradient[:600]}", flush=True)
        time.sleep(1)
        # (c) update: separate model call applying the best edit.
        upd_q = ("Rewrite the instruction below by applying the best (first) "
                 "of these 3 proposed edits:\nEDITS:\n%s\n\n"
                 "INSTRUCTION:\n%s\n\nRules: keep the placeholder {q} exactly "
                 "once for the question; use no other curly braces anywhere; "
                 "keep the convention of writing the final number alone on "
                 "the last line prefixed with 'Answer:'. Return ONLY the "
                 "rewritten instruction, no commentary."
                 % (gradient, current))
        try:
            rewrite = call_model(upd_q).strip()
        except Exception as e:  # noqa: BLE001 - one bad call ends the loop
            print(f"iter{it}: update call failed: {type(e).__name__}",
                  flush=True)
            history.append({"iter": it, "score": cur_score, "kept": False,
                            "note": "update call failed"})
            break
        # Strip accidental quoting/fences the model may add.
        rewrite = rewrite.strip().strip('"').strip("'").strip()
        if rewrite.startswith("```"):
            lines = rewrite.splitlines()
            rewrite = "\n".join(
                ln for ln in lines if not ln.strip().startswith("```")).strip()
        print(f"iter{it} rewrite:\n{rewrite[:600]}", flush=True)
        if not is_format_safe(rewrite):
            print(f"iter{it}: rewrite not format-safe, dropped", flush=True)
            history.append({"iter": it, "score": cur_score, "kept": False,
                            "note": "rewrite not format-safe (braces)"})
            continue
        new_score, new_failures = eval_prompt(cases, rewrite, f"iter{it}")
        print(json.dumps({"iter": it, "old": cur_score, "new": new_score}),
              flush=True)
        if new_score >= cur_score:
            current, cur_score, cur_failures = rewrite, new_score, new_failures
            history.append({"iter": it, "score": new_score, "kept": True,
                            "note": f"{new_score}>= {cur_score} before update"})
        else:
            history.append({"iter": it, "score": new_score, "kept": False,
                            "note": f"{new_score} < {cur_score}, dropped"})
        time.sleep(1)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(HEADER_ESCAPED + "\n" + current + "\n", encoding="utf-8")
    print(json.dumps({"baseline": base_score, "final": cur_score,
                      "history": history, "out": str(OUT_PATH)}), flush=True)


if __name__ == "__main__":
    main()
