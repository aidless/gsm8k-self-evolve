"""GSM8K evaluator for the exp-gsm8k experiment.

Candidate policy knob: {"answer_policy": "direct" | "concise-reason" | "double-check"}.
Calls cloud ollama (qwen2.5:7b, temperature 0), extracts the numeric answer,
compares against EVO_EXPECTED with exact float equality.
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
}

NUM_RE = re.compile(r"-?[\d,]*\.?\d+")


def call_model(prompt: str, timeout: int = 90) -> tuple[str, float]:
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


def extract_number(text: str, policy: str) -> float | None:
    text = text.strip().replace(",", "")
    if policy == "concise-reason":
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        pool = lines[-1] if lines else text
        m = NUM_RE.findall(pool)
        if not m:
            m = NUM_RE.findall(text)
    else:
        m = NUM_RE.findall(text)
        # direct/double-check: whole response should be the number; take first
    if not m:
        return None
    try:
        return float(m[-1] if policy == "concise-reason" else m[0])
    except ValueError:
        return None


def main() -> None:
    candidate = json.loads(Path(os.environ["EVO_CANDIDATE"]).read_text(encoding="utf-8"))
    question = json.loads(os.environ["EVO_INPUT"])
    expected = float(json.loads(os.environ["EVO_EXPECTED"]))
    policy = candidate.get("answer_policy", "direct")
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
