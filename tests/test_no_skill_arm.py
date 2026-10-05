"""The no-skill arm must be measured, not substituted -- and must be parsed on its own rule.

Why this file exists. The SANKEN-style retention form (arXiv:2609.39148) computes
Retention(s) = G_test(s) - G_train(s) with G relative to a_empty, the no-skill
baseline. This repo has never measured it: every round contrasts artifact vs
artifact. ``scripts/retention_report.py`` already refuses to substitute ``direct``
for it, because ``direct`` is still an answer-format instruction and would bias
every retention downward. That refusal is correct and is what made this arm worth
building.

Two things can go wrong, and both produce a number that looks fine:

1. Declaring ``no-skill`` as a policy but letting it fall through
   extract_number's non-reasoning branch, which takes the FIRST number in the
   output. On a free-form answer the first number is usually one the model quoted
   back from the question, so the arm scores near zero for a parsing reason. Since
   a_empty is subtracted from every G, that inflation reports LOW retention for
   arms that did retain -- the same shape of error as the transport failures
   already quarantined twice in this repo, but produced by the parser.

2. Declaring ``no-skill`` inside REASONING_POLICIES to reuse the last-line rule,
   which presumes the policy asked for a final "Answer:" line. This arm asks for
   nothing, so the model is free to end on a sentence fragment; the last line is
   then not necessarily where the answer sits.

Each test below carries its counter-proof: the rule must be able to FAIL.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _evaluator():
    """Load examples/gsm8k_evaluator.py as a module without importing the package."""
    spec = importlib.util.spec_from_file_location(
        "gsm8k_evaluator_under_test", ROOT / "examples" / "gsm8k_evaluator.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def ev():
    return _evaluator()


def test_no_skill_policy_exists_and_sends_the_question_alone(ev):
    """The arm must carry no instruction at all -- that is what makes it a_empty."""
    assert "no-skill" in ev.PROMPTS, "the no-skill arm is not defined"
    rendered = ev.PROMPTS["no-skill"].format(q="How many apples?")
    assert rendered == "How many apples?"
    for leak in ("Answer:", "step by step", "final number", "Return only"):
        assert leak not in rendered, (
            f"the no-skill prompt leaks an instruction ({leak!r}); it would stop "
            "being a no-skill arm and would bias every retention downward"
        )


def test_no_skill_is_not_in_the_reasoning_policies_that_presume_a_final_line(ev):
    """Counter-proof: the arm is free-form, so the last-line convention must not apply."""
    assert "no-skill" not in ev.REASONING_POLICIES, (
        "no-skill gives no format instruction; putting it in REASONING_POLICIES "
        "makes extract_number read the last line as the answer, which presumes an "
        "'Answer:' convention this arm never asked for"
    )


def test_no_skill_parses_the_last_number_not_the_first(ev):
    """The whole point: a free-form answer's FIRST number is usually quoted back."""
    answer = (
        "Jimmy has $2 more than twice the money Ethel has. "
        "Ethel has $8, so Jimmy has 8 * 2 + 2 = 18."
    )
    assert ev.extract_number(answer, "direct") == 2.0, (
        "the existing first-number branch must stay as it is for the instructed "
        "policies; if this changed, direct's historical numbers moved"
    )
    assert ev.extract_number(answer, "no-skill") == 18.0, (
        "no-skill must take the last number: on free-form output the first one is "
        "a number the model quoted from the question"
    )


def test_the_two_branches_would_disagree_so_the_rule_is_load_bearing(ev):
    """Non-empty proof: if both branches agreed, the fix would be untestable."""
    output = "First I note 12 apples are mentioned, then the total is 30."
    first = ev.NUM_RE.findall(output.replace(",", ""))[0]
    last = ev.NUM_RE.findall(output.replace(",", ""))[-1]
    assert first != last, "the fixture no longer separates the two branches"
    assert ev.extract_number(output, "no-skill") == float(last)
    assert ev.extract_number(output, "no-skill") != float(first)


def test_no_skill_returns_none_when_the_model_produced_no_number(ev):
    """A wrong-format answer must score unparsed, not silently as zero-with-answer."""
    assert ev.extract_number("I am not sure how to answer this.", "no-skill") is None


def test_reasoning_policies_keep_their_existing_behaviour(ev):
    """The arm's own rule must not leak into the policies that already have one."""
    for policy in ("step-calc", "cot-zero", "few-shot", "rectify"):
        assert policy in ev.REASONING_POLICIES
        out = "12 plus 18 is 30.\nAnswer: 30"
        assert ev.extract_number(out, policy) == 30.0


def _merge_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "merge_no_skill_arm_under_test", ROOT / "scripts" / "merge_no_skill_arm.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fake_run(n: int, passed: int, with_error: bool = False, totals_override=None) -> dict:
    details = {}
    for i in range(n):
        row = {"no-skill": {"passed": i < passed, "latency": 1.0,
                            "details": {"parsed": 1.0 if i < passed else None}}}
        if with_error and i == 0:
            row["no-skill"]["error"] = "URLError"
        details["q%03d" % i] = row
    return {"meta": {"dataset": "d.json", "policies": ["no-skill"],
                     "model": "qwen2.5:7b", "n": n, "sources": []},
            "totals": totals_override or {"no-skill": passed},
            "pairs": {}, "details": details}


def test_merge_recomputes_totals_from_details_and_rejects_a_lying_file(tmp_path):
    """A hand-edited totals must not pass as evidence."""
    mod = _merge_module()
    good = tmp_path / "good.json"
    good.write_text(json.dumps(_fake_run(40, 27)), encoding="utf-8")
    assert mod.verify_source(good)["totals"]["no-skill"] == 27

    lying = tmp_path / "lying.json"
    lying.write_text(json.dumps(_fake_run(40, 27, totals_override={"no-skill": 999})),
                     encoding="utf-8")
    with pytest.raises(AssertionError, match="totals"):
        mod.verify_source(lying)


def test_merge_refuses_a_file_whose_cells_carry_a_transport_error(tmp_path):
    """Counter-proof: the fail-closed contract must survive the merge step too."""
    mod = _merge_module()
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(_fake_run(40, 20, with_error=True)), encoding="utf-8")
    with pytest.raises(AssertionError, match="transport error"):
        mod.verify_source(bad)


def test_merge_rejects_a_file_whose_policy_is_not_the_no_skill_arm(tmp_path):
    """Substituting another policy's file would be the substitution the report refuses."""
    mod = _merge_module()
    d = _fake_run(40, 27)
    d["meta"]["policies"] = ["direct"]
    for row in d["details"].values():
        row["direct"] = row.pop("no-skill")
    d["totals"] = {"direct": 27}
    other = tmp_path / "other.json"
    other.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(AssertionError, match="policies"):
        mod.verify_source(other)
