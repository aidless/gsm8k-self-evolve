# tests/test_run_proposer_arm.py
"""Guard tests for the round-5 Task 6 proposer-substitution arm runner.

Frozen protocol (authoritative): ``results/rounds/round5/PREREG-round5.md`` §6 — the optional
proposer arm is capped at **400 calls** (``heldout40`` × 5 policies × 2) and must never be
substituted with other data.  ``paper/PLAN-NOVELTY.md`` Task 6 pins the model (``qwen2.5:7b``),
the dataset (``examples/heldout40.json``) and the headline comparison (the proposer's product vs
``cot-zero``).

These tests lock the **refusals**, i.e. the budget guard must be able to fail (workspace rule 7:
a gate with no negative test is decoration).  Every refusal asserted here happens BEFORE the
preflight probe and therefore before any model call, so this file is offline and spends no budget.
``--dry-run`` is passed as a second safety net: if a guard ever stopped firing, the invocation
would return after preflight instead of starting the arm.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.run_proposer_arm as arm  # noqa: E402


def run_main(monkeypatch, *argv):
    """Invoke the runner's main() with argv; return its exit code (0 when it returns normally)."""
    monkeypatch.setattr(sys, "argv", ["run_proposer_arm.py", *argv])
    try:
        arm.main()
    except SystemExit as exc:
        code = exc.code
        return 0 if code is None else code
    return 0


def test_prereg_budget_formula_matches_arm_panel():
    """400 = heldout40 × 5 policies × 2 repeats, with the panel actually implemented."""
    cases = json.loads((ROOT / "examples" / "heldout40.json").read_text(encoding="utf-8"))["cases"]
    assert len(cases) == 40
    assert len(arm.PANEL) == 5
    assert len(cases) * len(arm.PANEL) * 2 == arm.CALL_CAP_PREREG == 400


def test_headline_pair_is_product_vs_cotzero_and_panel_carries_both():
    assert arm.PRODUCT_POLICY == "textgrad"
    assert arm.HEADLINE_CHALLENGER == arm.PRODUCT_POLICY
    assert arm.HEADLINE_INCUMBENT == "cot-zero"
    assert arm.PRODUCT_POLICY in arm.PANEL and "cot-zero" in arm.PANEL


def test_budget_guard_refuses_cap_violation_before_any_call(monkeypatch, tmp_path):
    """40 × 5 × 3 = 600 > 400 must be refused (exit 2), not silently truncated."""
    code = run_main(monkeypatch, "--repeats", "3", "--dry-run",
                    "--skip-preflight", "--out", str(tmp_path / "a.json"))
    assert code == 2


def test_cap_cannot_be_raised_above_the_preregistered_cap(monkeypatch, tmp_path):
    code = run_main(monkeypatch, "--cap", "500", "--dry-run",
                    "--skip-preflight", "--out", str(tmp_path / "b.json"))
    assert code == 2


def test_variable_call_policy_is_refused(monkeypatch, tmp_path):
    """reflect-retry spends 2-3 calls/question, so a fixed cell grid cannot bound the budget."""
    assert "reflect-retry" in arm.VARIABLE_CALL_POLICIES
    code = run_main(monkeypatch, "--limit", "1", "--dry-run", "--skip-preflight",
                    "--policies", "direct,step-calc,cot-zero,few-shot,textgrad,reflect-retry",
                    "--out", str(tmp_path / "c.json"))
    assert code == 4


def test_missing_headline_policy_is_refused(monkeypatch, tmp_path):
    code = run_main(monkeypatch, "--limit", "1", "--dry-run", "--skip-preflight",
                    "--policies", "direct,step-calc,few-shot",
                    "--out", str(tmp_path / "d.json"))
    assert code == 4


def test_non_heldout_dataset_is_refused(monkeypatch, tmp_path):
    code = run_main(monkeypatch, "--dataset", "examples/gsm8k40.json", "--limit", "1",
                    "--dry-run", "--skip-preflight", "--out", str(tmp_path / "e.json"))
    assert code == 5


def test_planned_call_count_printed_matches_grid(monkeypatch, tmp_path, capsys):
    """The plan (and therefore the cap arithmetic) is printed before any model call."""
    code = run_main(monkeypatch, "--limit", "2", "--dry-run", "--skip-preflight",
                    "--out", str(tmp_path / "f.json"))
    assert code == 0
    out = capsys.readouterr().out
    assert "PLANNED CALLS: 20" in out
    assert "2 questions × 5 policies × 2 repeats" in out
