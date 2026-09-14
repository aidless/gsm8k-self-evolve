"""GSM8K evaluator for the exp-gsm8k experiment.

Candidate policy knob: answer_policy in {
  "direct", "concise-reason", "double-check",   # round 1
  "step-calc", "rounding-aware", "rectify",     # round 2
}.
Calls cloud ollama (qwen2.5:7b, temperature 0), extracts the numeric answer,
compares against EVO_EXPECTED with exact float equality.
Transport note: ``EVO_BACKEND=openai`` + ``EVO_OPENAI_BASE`` route the same prompt
to an OpenAI-compatible server (vLLM) instead; prompts, extraction and scoring are
identical either way (see scripts/llm_backends.py).
"""
import json
import os
import re
import time
import urllib.request
from pathlib import Path

OLLAMA_URL = os.environ.get("EVO_OLLAMA_URL", "http://127.0.0.1:11434/api/generate")
MODEL = os.environ.get("EVO_MODEL", "qwen2.5:7b")

PROMPTS = {
    "direct": "{q}\nReturn only the final number, no other text.",
    "concise-reason": (
        "{q}\nThink step by step in at most 2 short sentences, "
        "then write the final number alone on the last line prefixed with 'Answer:'."
    ),
    "double-check": (
        "{q}\nSolve the problem, double-check the arithmetic, "
        "then return only the final number, no other text."
    ),
    "step-calc": (
        "{q}\nSolve step by step, writing each arithmetic step on its own line, "
        "then write the final number alone on the last line prefixed with 'Answer:'."
    ),
    "rounding-aware": (
        "{q}\nSolve step by step, paying careful attention to rounding rules "
        "(partial time units typically bill as a full unit). "
        "Write the final number alone on the last line prefixed with 'Answer:'."
    ),
    "rectify": (
        "{q}\nThink step by step in at most 3 short sentences, computing carefully, "
        "then re-check your arithmetic once before answering. "
        "Write the final number alone on the last line prefixed with 'Answer:'."
    ),
    "cot-zero": (
        "{q}\nLet's think step by step.\n"
        "Write the final number alone on the last line prefixed with 'Answer:'."
    ),
    "few-shot": (
        Path("examples/prompts/fewshot-4.txt").read_text(encoding="utf-8")
        + "\nQ: {q}\n"
    ),
}

LESSONS_PATH = os.environ.get("EVO_LESSONS", "examples/lessons-round3.json")

def load_lessons() -> str:
    try:
        ls = json.loads(Path(LESSONS_PATH).read_text(encoding="utf-8")).get("lessons", [])
    except Exception:
        ls = []
    return "\n".join(f"- {s}" for s in ls[:8])

REFLECT_PROMPT = (
    "{q}\nSolve step by step, writing each arithmetic step on its own line. "
    "Known pitfalls:\n{lessons}\n"
    "Write the final number alone on the last line prefixed with 'Answer:'.")

def run_reflect_retry(question: str) -> tuple[bool, float, dict]:
    import time as _t
    t0 = _t.monotonic()
    lessons = load_lessons()
    raw, _ = call_model(REFLECT_PROMPT.format(q=question, lessons=lessons or "(none yet)"))
    got = extract_number(raw, "reflect-retry")
    attempts, trigger = 1, "first-pass"
    if got is None:
        trigger = "parse-fail"
    else:
        raw2, _ = call_model(REFLECT_PROMPT.format(q=question, lessons=lessons or "(none yet)"))
        got2 = extract_number(raw2, "reflect-retry")
        attempts = 2
        if got2 != got:
            trigger = "disagreement"
    if trigger in ("parse-fail", "disagreement"):
        reflection = (
            "My previous attempt failed (%s). Reflect in one sentence on the likely "
            "arithmetic mistake, redo the computation step by step, and write the final "
            "number alone on the last line prefixed with 'Answer:'.\nQuestion: %s"
            % (trigger, question))
        raw_r, _ = call_model(reflection)
        got_r = extract_number(raw_r, "reflect-retry")
        if got_r is not None:
            raw, got = raw_r, got_r
        attempts += 1
    latency = _t.monotonic() - t0
    return got, latency, {"policy": "reflect-reason-retry", "attempts": attempts,
                         "trigger": trigger, "raw": raw[:200], "parsed": got}

REASONING_POLICIES = {"concise-reason", "step-calc", "rounding-aware", "rectify", "reflect-retry", "textgrad", "cot-zero", "few-shot"}

NUM_RE = re.compile(r"-?[\d,]*\.?\d+")


def call_model(prompt: str, timeout: int | None = None) -> tuple[str, float]:
    """Transport only.  ``EVO_BACKEND=openai`` (set by run_proposer_arm.py when a
    vLLM/OpenAI-compatible base is selected) routes the SAME prompt to
    ``POST {EVO_OPENAI_BASE}/v1/chat/completions``; anything else keeps the frozen
    ollama path below, byte-for-byte.  Prompts, extraction and scoring are not
    touched by the backend choice."""
    if timeout is None:
        timeout = int(float(os.environ.get("EVO_REQUEST_TIMEOUT", 90)))
    if os.environ.get("EVO_BACKEND", "ollama").strip().lower() == "openai":
        return call_model_openai(prompt, timeout)
    body = json.dumps({
        "model": MODEL, "prompt": prompt, "stream": False,
        "options": {"temperature": 0},
    }).encode()
    t0 = time.monotonic()
    req = urllib.request.Request(OLLAMA_URL, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.load(resp)
    return data.get("response", ""), time.monotonic() - t0


def call_model_openai(prompt: str, timeout: int) -> tuple[str, float]:
    """OpenAI-compatible transport (vLLM).  Lazily imported so the default path
    cannot break if the scripts/ helper is unavailable."""
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from llm_backends import openai_chat  # noqa: E402 - lazy, transport-only

    base = os.environ.get("EVO_OPENAI_BASE")
    if not base:
        raise RuntimeError("EVO_BACKEND=openai requires EVO_OPENAI_BASE")
    res = openai_chat(
        prompt, model=MODEL, base=base,
        max_tokens=int(os.environ.get("EVO_MAX_TOKENS", 4096)),
        timeout=timeout,
        retries=int(os.environ.get("EVO_REQUEST_RETRIES", 2)),
        backoff_base=float(os.environ.get("EVO_RETRY_BACKOFF", 2.0)),
    )
    return res["text"], res["latency_s"]


def extract_number(text: str, policy: str) -> float | None:
    text = text.strip().replace(",", "")
    if policy in REASONING_POLICIES:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        pool = lines[-1] if lines else text
        m = NUM_RE.findall(pool)
        if not m:
            m = NUM_RE.findall(text)
    else:
        m = NUM_RE.findall(text)
    if not m:
        return None
    try:
        return float(m[-1] if policy in REASONING_POLICIES else m[0])
    except ValueError:
        return None


def main() -> None:
    candidate = json.loads(Path(os.environ["EVO_CANDIDATE"]).read_text(encoding="utf-8"))
    question = json.loads(os.environ["EVO_INPUT"])
    expected = float(json.loads(os.environ["EVO_EXPECTED"]))
    policy = candidate.get("answer_policy", "direct")
    if policy == "reflect-retry":
        try:
            got, latency, detail = run_reflect_retry(question)
            passed = got is not None and got == expected
            detail.update({"expected": expected})
        except Exception as exc:
            passed, latency = False, 0.0
            detail = {"policy": policy, "error": type(exc).__name__}
        print(json.dumps({"passed": passed, "score": 1.0 if passed else 0.0,
                          "cost": 0.0, "latency_s": round(latency, 3),
                          "details": detail}))
        return
    if policy == "textgrad":
        prompt_file = candidate.get("prompt_file", "examples/prompts/textgrad-prompt.txt")
        prompt = Path(prompt_file).read_text(encoding="utf-8").format(q=question)
    else:
        prompt = PROMPTS.get(policy, PROMPTS["direct"]).format(q=question)
    try:
        raw, latency = call_model(prompt)
        got = extract_number(raw, policy)
        passed = got is not None and got == expected
        detail = {"policy": policy, "raw": raw[:200], "parsed": got,
                  "expected": expected}
    except Exception as exc:  # noqa: BLE001 - evaluator must always emit JSON
        passed, latency = False, 0.0
        detail = {"policy": policy, "error": type(exc).__name__}
    print(json.dumps({"passed": passed, "score": 1.0 if passed else 0.0,
                      "cost": 0.0, "latency_s": round(latency, 3),
                      "details": detail}))


if __name__ == "__main__":
    main()
