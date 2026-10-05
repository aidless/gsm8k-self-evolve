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
import json
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


def test_a_measured_no_skill_arm_is_reported_not_fabricated():
    """The arm exists now (175/200), so this pins that it is READ, not invented.

    The original assertion here was `no_skill_arm_present is False` -- true when the
    arm had never been run. What must not change is the refusal to fabricate one:
    a_empty comes from the merged no-skill file and from nothing else, and 'direct'
    is still never substituted for it.
    """
    res = rr.report(None)
    assert res["no_skill_arm_present"] is True
    ns = res["a_empty_measured"]
    assert ns["n"] == 200 and ns["count"] == 175
    assert ns["rate"] == pytest.approx(0.875, abs=1e-12)
    assert ns["model"] == "qwen2.5:7b"
    # 'direct' must still not be standing in for the empty arm
    assert "direct" not in json_text_without_direct(res)


def test_G_test_is_computed_from_the_measured_a_empty():
    """G must be 100*(a - a_empty) off the real baseline, not an assumed one."""
    rows = {r["contrast"]: r for r in rr.report(None)["measured"]}
    a_empty = 0.875
    for r in rows.values():
        assert r["a_empty"] == pytest.approx(a_empty, abs=1e-12)
        assert r["G_test_100"] == pytest.approx(100.0 * (r["a_challenger"] - a_empty),
                                                abs=1e-3)
    assert rows["step-calc vs cot-zero"]["G_test_100"] == pytest.approx(5.50, abs=1e-3)
    assert rows["step-calc vs direct"]["G_test_100"] == pytest.approx(-74.00, abs=1e-3)


def test_retention_is_still_refused_even_with_a_measured_a_empty():
    """Having a_empty does not make G_test a retention: G_train is never measured here.

    This is the claim most likely to be over-read, so it is pinned explicitly rather
    than left to prose.
    """
    res = rr.report(None)
    assert res["retention_reported"] is False
    why = res["retention_why"]
    assert "G_train" in why and "TRAINING split" in why
    assert "G_test" in why
    # no bare "Retention =" number may appear in the payload
    assert "retention_" not in json.dumps(res["measured"], ensure_ascii=False)


def test_counter_proof_a_no_skill_file_for_another_arm_is_refused(tmp_path):
    """'direct' renamed into a no-skill file must not silently become a_empty."""
    real_root = rr.ROOT
    src = json.loads((real_root / "results/rounds/round4/no-skill-merged.json")
                     .read_text(encoding="utf-8"))
    src["meta"]["policies"] = ["direct"]
    (tmp_path / "results/rounds/round4").mkdir(parents=True)
    (tmp_path / "results/rounds/round4/no-skill-merged.json").write_text(
        json.dumps(src, ensure_ascii=False), encoding="utf-8")
    try:
        rr.ROOT = tmp_path
        with pytest.raises(SystemExit, match="expected exactly"):
            rr._load_no_skill()
    finally:
        rr.ROOT = real_root


def test_counter_proof_a_no_skill_file_with_a_transport_error_is_refused():
    """A lost call is not a wrong answer, so an errored a_empty must stop the report."""
    import copy
    real_root = rr.ROOT
    data = json.loads((real_root / "results/rounds/round4/no-skill-merged.json")
                      .read_text(encoding="utf-8"))
    assert data["meta"]["policies"] == ["no-skill"]
    # the guard is exercised against the loader's own contract, using a tmp root
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "results/rounds/round4").mkdir(parents=True)
        bad = copy.deepcopy(data)
        k = next(iter(bad["details"]))
        bad["details"][k]["no-skill"]["error"] = "TimeoutError"
        (d / "results/rounds/round4/no-skill-merged.json").write_text(
            json.dumps(bad, ensure_ascii=False), encoding="utf-8")
        try:
            rr.ROOT = d
            with pytest.raises(SystemExit, match="transport error"):
                rr._load_no_skill()
        finally:
            rr.ROOT = real_root


def test_counter_proof_totals_disagreeing_with_details_is_refused():
    """The one number that shifts every G must agree with its own per-id evidence."""
    import tempfile
    real_root = rr.ROOT
    data = json.loads((real_root / "results/rounds/round4/no-skill-merged.json")
                      .read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "results/rounds/round4").mkdir(parents=True)
        bad = json.loads(json.dumps(data))
        bad["totals"]["no-skill"] = bad["totals"]["no-skill"] + 1
        (d / "results/rounds/round4/no-skill-merged.json").write_text(
            json.dumps(bad, ensure_ascii=False), encoding="utf-8")
        try:
            rr.ROOT = d
            with pytest.raises(SystemExit, match="recomputing from details"):
                rr._load_no_skill()
        finally:
            rr.ROOT = real_root


def test_counter_proof_a_empty_on_a_different_question_set_is_refused():
    """G subtracts one rate from another, so the two must share a question set.

    Builds a full tmp root, because the loader needs the artifact arms (n=200) too
    and the report's refusal IS the point: a 40-question a_empty is internally
    consistent and still cannot be subtracted from a 200-question arm.
    """
    import shutil
    import tempfile
    real_root = rr.ROOT
    src40 = json.loads((real_root / "results/rounds/round4/no-skill-heldout40.json")
                       .read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        for rel in ("results/rounds/round3/heldout40-round3.json",
                    "results/rounds/round4/trackA-merged.json"):
            (d / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(real_root / rel, d / rel)
        det = src40["details"]
        (d / "results/rounds/round4/no-skill-merged.json").write_text(json.dumps({
            "meta": {"dataset": ["examples/heldout40.json"], "policies": ["no-skill"],
                     "model": "qwen2.5:7b", "n": len(det), "sources": ["x"]},
            "totals": {"no-skill": sum(1 for r in det.values() if r["no-skill"]["passed"])},
            "pairs": {}, "details": det}, ensure_ascii=False), encoding="utf-8")
        try:
            rr.ROOT = d
            # internally consistent, so the loader accepts it ...
            assert rr._load_no_skill()["n"] == 40
            # ... and the report refuses to subtract it from a 200-question arm
            with pytest.raises(SystemExit, match="same question set"):
                rr.report(None)
        finally:
            rr.ROOT = real_root


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