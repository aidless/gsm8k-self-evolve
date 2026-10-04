"""Gate for tools/check_treatment_applied.py.

The tool exists because an arm that injects nothing still loses to the incumbent,
so "our X did not beat the baseline" is not evidence about X. Two directions must
hold, and both are asserted here:

  - a real shipped artefact in this repo is judged EMPTY
  - guidance that is genuinely present is judged REAL

A detector that only ever fails would pass a suite of negative cases alone.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
from check_treatment_applied import (  # noqa: E402
    ROOT, content_tokens, scan, split_header, treatment_delta,
)

BASE = ("{q}\nSolve step by step, writing each arithmetic step on its own line, then "
        "write the final number alone on the last line prefixed with 'Answer:'.")
HEADER = '{{"rewritten_from": "step-calc", "oracle": "train-only", "frozen": true}}'


# ---- the real artefact -------------------------------------------------------
def test_shipped_round5_artefact_is_judged_empty():
    """The actual file the round-5 arms served."""
    injected = open(os.path.join(ROOT, "examples/prompts/textgrad-prompt.txt"),
                    encoding="utf-8").read()
    r = treatment_delta(BASE, injected)
    assert r["verdict"] == "empty", r
    assert r["added_content_tokens"] == 0


def test_scan_finds_the_round5_arm_and_reports_empty():
    rows = [r for r in scan() if r["product"].endswith("textgrad-prompt.txt")]
    assert rows, "scan found nothing; it is not actually scanning"
    assert all(r["verdict"] == "empty" for r in rows)
    assert all(r["added_content_tokens"] == 0 for r in rows)


# ---- the null shapes ---------------------------------------------------------
def test_baseline_copy_is_empty():
    assert treatment_delta(BASE, BASE)["verdict"] == "empty"


def test_baseline_plus_newline_is_empty():
    r = treatment_delta(BASE, BASE + "\n")
    assert r["verdict"] == "empty", r


def test_provenance_header_alone_is_not_a_treatment():
    """A header is metadata. Counting it would let a null arm look instrumented."""
    _, body = split_header(HEADER + "\n" + BASE)
    assert body.strip() == BASE.strip()
    assert treatment_delta(BASE, HEADER + "\n" + BASE)["verdict"] == "empty"


def test_whitespace_only_injection_is_empty():
    assert treatment_delta(BASE, BASE + "\n\n   \n")["verdict"] == "empty"


# ---- the positive direction --------------------------------------------------
def test_genuine_guidance_is_judged_real():
    guidance = ("Known pitfalls already falsified on the training set:\n"
                "- `direct` answering was rejected: it failed to beat step-calc.\n"
                "- `cot-zero` tied step-calc with no significant gain at p = 0.804.")
    r = treatment_delta(BASE, HEADER + "\n" + guidance + "\n" + BASE)
    assert r["verdict"] == "real", r
    assert r["added_content_tokens"] > 15


def test_real_lesson_block_is_judged_real():
    """The other real guidance in the repo (EVO_LESSONS, used by reflect-retry)."""
    import json
    lessons = json.load(open(os.path.join(ROOT, "examples/lessons-round3.json"),
                             encoding="utf-8"))["lessons"]
    block = "\n".join(f"- {s}" for s in lessons)
    r = treatment_delta(BASE, block)
    assert r["verdict"] == "real", r


# ---- mechanics ---------------------------------------------------------------
def test_missing_product_file_is_flagged_not_ignored(tmp_path):
    """An arm that declares a product which does not exist must not pass silently.

    It is not evidence of a good treatment; it is evidence that cannot be judged.
    """
    import check_treatment_applied as cta
    rounds = tmp_path / "results" / "rounds" / "fake"
    rounds.mkdir(parents=True)
    (rounds / "arm.json").write_text(json.dumps(
        {"meta": {"proposer": {"product_file": "examples/prompts/nope.txt"}}}), encoding="utf-8")

    real_root = cta.ROOT
    try:
        cta.ROOT = str(tmp_path)
        rows = cta.scan()
    finally:
        cta.ROOT = real_root
    assert len(rows) == 1
    assert rows[0]["verdict"] == "missing", rows[0]
    assert "does not exist" in rows[0]["detail"]


def test_rearrangement_of_baseline_words_is_not_a_treatment():
    """A different word order, same content: looks instrumented, carries nothing."""
    shuffled = ("{q}\nThen write the final number alone on the last line prefixed with "
                "'Answer:'.\nSolve step by step, writing each arithmetic step on its own line, ")
    r = treatment_delta(BASE, shuffled)
    assert r["verdict"] == "empty", r
    assert "only the baseline" in r["detail"]


def test_main_exit_code_is_non_zero_when_an_arm_is_empty(monkeypatch):
    """The tool's whole purpose is to be un-ignorable. Assert the exit code."""
    import check_treatment_applied as cta
    rc_empty = cta.main([])
    assert rc_empty == 1, f"empty arm must exit 1, got {rc_empty}"
    monkeypatch.setattr(cta, "scan", lambda: [
        {"verdict": "real", "product": "x.txt", "detail": "42 tokens", "evidence": "e.json"}])
    assert cta.main([]) == 0, "all-real arms must exit 0"


def test_content_tokens_drop_stopwords_but_keep_cjk():
    assert content_tokens("the and of answer") == {"answer"}
    assert "错" in content_tokens("这个算法错了")
