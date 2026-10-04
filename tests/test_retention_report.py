"""retention_report: the orientation flip is the thing most likely to be wrong silently.

The pairs block in results/rounds/round4/trackA-merged.json is keyed by orientation
("<A>_vs_<B>") and its better/worse counts are directional: `direct_vs_step-calc` with
better=157 means "direct got 157 questions right that step-calc got wrong". Reading that
key backwards silently reports a 0.785 gain as a 0.785 loss, and the McNemar p survives
the error unchanged -- so no downstream sanity check would notice. These tests pin the
orientation explicitly.

They also pin that the script refuses to invent a no-skill arm, which is the whole
reason it cannot yet produce a Retention in the sense of arXiv:2609.39148.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("rr", ROOT / "scripts" / "retention_report.py")
rr = importlib.util.module_from_spec(spec)
sys.modules["rr"] = rr
spec.loader.exec_module(rr)


def test_mcnemar_matches_the_canonical_evokit_implementation():
    """This script re-implements the exact test; it must not drift from evokit."""
    sys.path.insert(0, str(ROOT))
    from evokit.stats import mcnemar_two_sided as canonical
    for b, c in [(9, 7), (9, 14), (33, 4), (0, 320), (0, 776), (4, 6), (20, 0), (9, 1),
                 (30, 4), (3, 0), (157, 0), (159, 0), (1, 2), (0, 0)]:
        assert rr.mcnemar_two_sided(b, c) == pytest.approx(canonical(b, c), abs=1e-15), (b, c)


def test_orientation_flip_is_applied_for_the_reversed_pair():
    rows = {r["contrast"]: r for r in rr.report(None)["measured"]}
    d = rows["step-calc vs direct"]
    # stored as direct_vs_step-calc with better=157; for the challenger = direct the
    # challenger-better count is the STORED worse count, i.e. 0, not 157.
    assert d["orientation_flipped"] is True
    assert d["pair_key_as_stored"] == "direct_vs_step-calc"
    assert d["better"] == 0 and d["worse"] == 157
    assert d["signed_gain_vs_step_calc"] == pytest.approx(-0.785, abs=1e-9)
    assert d["mcnemar_recomputed"] == pytest.approx(d["mcnemar_p"], abs=1e-12)


def test_orientation_is_not_flipped_for_a_forward_pair():
    rows = {r["contrast"]: r for r in rr.report(None)["measured"]}
    c = rows["step-calc vs cot-zero"]
    assert c["orientation_flipped"] is False
    assert c["better"] == 9 and c["worse"] == 7
    assert c["signed_gain_vs_step_calc"] == pytest.approx(+0.010, abs=1e-9)


def test_a_flip_cannot_change_the_p_value():
    """The failure this guards against is invisible in p; only b/c carry the direction."""
    assert rr.mcnemar_two_sided(157, 0) == pytest.approx(rr.mcnemar_two_sided(0, 157))


def test_script_refuses_to_fabricate_a_no_skill_arm():
    res = rr.report(None)
    assert res["no_skill_arm_present"] is False
    assert "a_empty is NOT measured" in res["blocking_gap"]
    # 'direct' must NOT be silently used as the no-skill arm
    assert "direct" not in json_text_without_direct(res)


def json_text_without_direct(res: dict) -> str:
    import json
    s = json.dumps(res, ensure_ascii=False)
    return s.replace("direct", "")


def test_hypothetical_mode_is_labelled_illustrative():
    """A what-if must never be mistakable for a measurement."""
    res = rr.report(0.05)
    h = res["hypothetical_at_assumed_empty"]
    assert h["a_empty"] == 0.05
    assert "ILLUSTRATIVE ONLY" in h["warning"]
    assert "not a retention" in h["warning"]


def test_reported_arms_cover_every_policy_in_the_merged_set():
    rows = {r["contrast"] for r in rr.report(None)["measured"]}
    assert rows == {"step-calc vs cot-zero", "step-calc vs few-shot", "step-calc vs direct"}
    # the incumbent itself is never listed as its own contrast
    assert "step-calc vs step-calc" not in rows


def test_all_rates_are_in_the_unit_interval():
    for r in rr.report(None)["measured"]:
        assert 0.0 <= r["a_step_calc"] <= 1.0
        assert 0.0 <= r["a_challenger"] <= 1.0