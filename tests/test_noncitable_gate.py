"""The NONCITABLE registry must be machine-enforced, not remembered.

Why this file exists. The registry's note used to claim its entries were
"machine-checked by scripts/emit_trajectory.py:is_citable()". That script was never
in the repository -- git has no commit adding it, only a stale .pyc -- so the
registry was an honest record that depended on a human reading it. tools/check_noncitable.py
replaces that claim with something real, and this file pins it.

Every test calls check() with an INJECTED registry path and root, so a violation is
built in a tmp dir and must produce a non-empty error list. Running the script from
another directory is not a counter-proof: its ROOT is derived from __file__, so it
would read the real registry and pass regardless.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _gate():
    spec = importlib.util.spec_from_file_location(
        "check_noncitable_under_test", ROOT / "tools" / "check_noncitable.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def gate():
    return _gate()


CAUSE = ("INVALIDATED because the endpoint returned transport failures on 840 of 1000 "
         "cells, so the totals conflate lost calls with wrong answers; those are not "
         "measurements and the failure mode is documented.")
RULE = ("EXCLUDED CELL under a rule stated before the subset was examined: a cell is "
        "dropped iff the model provably fails to terminate on that question, because "
        "the output loops and never returns.")


def _sandbox(tmp_path: Path, entries: list[dict], docs: dict[str, str] | None = None):
    """Build a minimal repo the gate can be pointed at."""
    (tmp_path / "results").mkdir(parents=True, exist_ok=True)
    reg = tmp_path / "results" / "NONCITABLE.json"
    reg.write_text(json.dumps({"schema_version": 1, "note": "n", "entries": entries}),
                   encoding="utf-8")
    for rel, body in (docs or {}).items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    return reg, tmp_path


def test_the_real_registry_passes(gate):
    """The shipped state must be clean, or the gate is noise."""
    errors, _ = gate.check()
    assert errors == [], errors


def test_a_coherent_entry_passes(gate, tmp_path):
    (tmp_path / "results").mkdir(parents=True)
    (tmp_path / "results" / "x.json").write_text("{}", encoding="utf-8")
    reg, root = _sandbox(tmp_path, [{"path": "results/x.json", "reason": CAUSE,
                                     "declared_in": "this registry"}])
    errors, _ = gate.check(reg, root)
    assert errors == [], errors


def test_counter_proof_missing_target(gate, tmp_path):
    reg, root = _sandbox(tmp_path, [{"path": "results/absent.json", "reason": CAUSE,
                                     "declared_in": "this registry"}])
    errors, _ = gate.check(reg, root)
    assert any("does not exist" in e for e in errors), errors


def test_counter_proof_reason_without_a_cause(gate, tmp_path):
    """An entry that only says 'not citable' tells a reader nothing about why."""
    (tmp_path / "results").mkdir(parents=True)
    (tmp_path / "results" / "x.json").write_text("{}", encoding="utf-8")
    reg, root = _sandbox(tmp_path, [{"path": "results/x.json",
                                     "reason": "Do not cite this file.",
                                     "declared_in": "this registry"}])
    errors, _ = gate.check(reg, root)
    assert any("does not state a cause" in e for e in errors), errors


def test_counter_proof_declared_in_points_at_nothing(gate, tmp_path):
    (tmp_path / "results").mkdir(parents=True)
    (tmp_path / "results" / "x.json").write_text("{}", encoding="utf-8")
    reg, root = _sandbox(tmp_path, [{"path": "results/x.json", "reason": CAUSE,
                                     "declared_in": "docs/nowhere.md section 3"}])
    errors, _ = gate.check(reg, root)
    assert any("declared_in points at" in e for e in errors), errors


def test_cell_fragment_must_exist_in_the_named_file(gate, tmp_path):
    """A #cell entry must name a cell the file actually contains."""
    def build(dirpath: Path, cell: str):
        (dirpath / "results").mkdir(parents=True, exist_ok=True)
        (dirpath / "results" / "in.json").write_text(
            json.dumps({"cases": [{"id": "chal-513"}]}), encoding="utf-8")
        reg = dirpath / "results" / "NONCITABLE.json"
        reg.write_text(json.dumps({"schema_version": 1, "note": "n", "entries": [
            {"path": "results/in.json#%s" % cell, "reason": RULE,
             "declared_in": "this registry"}]}), encoding="utf-8")
        return reg, dirpath

    reg, root = build(tmp_path / "ok", "chal-513")
    errors, notes = gate.check(reg, root)
    assert errors == [], errors
    assert any("cell 'chal-513' found" in n for n in notes), notes

    reg2, root2 = build(tmp_path / "bad", "chal-999")
    errors2, _ = gate.check(reg2, root2)
    assert any("not present in" in e for e in errors2), errors2


def test_counter_proof_a_document_citing_it_as_usable(gate, tmp_path):
    """The registry's purpose is that the path is not cited; assert that."""
    (tmp_path / "results").mkdir(parents=True)
    (tmp_path / "results" / "x.json").write_text("{}", encoding="utf-8")
    reg, root = _sandbox(
        tmp_path,
        [{"path": "results/x.json", "reason": CAUSE, "declared_in": "this registry"}],
        docs={"REPORT.md": "Per results/x.json, the effect is valid evidence of X.\n"})
    errors, _ = gate.check(reg, root)
    assert any("cites the non-citable path" in e for e in errors), errors


def test_a_document_mentioning_it_to_explain_exclusion_is_fine(gate, tmp_path):
    """Most legitimate mentions say WHY it cannot be used; the gate must allow those."""
    (tmp_path / "results").mkdir(parents=True)
    (tmp_path / "results" / "x.json").write_text("{}", encoding="utf-8")
    reg, root = _sandbox(
        tmp_path,
        [{"path": "results/x.json", "reason": CAUSE, "declared_in": "this registry"}],
        docs={"REPORT.md": "results/x.json is registered in NONCITABLE.json because the "
                          "endpoint failed; its totals are therefore not a measurement.\n"})
    errors, _ = gate.check(reg, root)
    assert errors == [], errors


def test_empty_registry_is_an_error(gate, tmp_path):
    """An empty registry is a silent way to disable the gate."""
    reg, root = _sandbox(tmp_path, [])
    errors, _ = gate.check(reg, root)
    assert errors, "an empty registry must not pass"


# ---------------------------------------------------------------------------
# The `locally_absent` exception: a target the repository itself excludes.
#
# Why this needs its own counter-proofs. The exception exists because the real
# registry names one target that is absent from every clone BY DESIGN (a runtime
# dataset under a .gitignore'd inputs/ directory). Without an exception, that entry
# failed the gate on every fresh clone -- and the fix people reach for when a gate
# cannot be kept green is to delete the exclusions. So the exception is deliberately
# narrow, and every one of its four conditions is pinned below by a counter-proof
# that injects the violation and asserts a non-empty error list.
# ---------------------------------------------------------------------------

import subprocess  # noqa: E402  (kept next to the tests that need it)


def _git_repo(path: Path, ignore: str | None = None) -> Path:
    """A real git repo -- the exception is keyed on git, so the tests need one."""
    subprocess.run(["git", "init", "-q", str(path)], check=True, capture_output=True)
    if ignore is not None:
        (path / ".gitignore").write_text(ignore + "\n", encoding="utf-8")
    return path


ABSENT_WHY = ("The declared target is a runtime dataset fetched at run time and never "
              "committed, because its upstream licence forbids redistribution; only the "
              "result JSON is shipped.")
REVIEWABLE = ["results/kept.json"]


def _absent_sandbox(tmp_path: Path, sub: str, *, ignore: str | None, entry_patch: dict):
    """A repo whose ignored inputs/ dir is missing, plus one kept evidence file."""
    root = _git_repo(tmp_path / sub, ignore)
    (root / "results").mkdir(parents=True, exist_ok=True)
    (root / "results" / "kept.json").write_text("{}", encoding="utf-8")
    entry = {"path": "results/inputs/gone.json#cell-1", "reason": RULE,
             "declared_in": "this registry",
             "locally_absent": {"why": ABSENT_WHY, "not_present_in": "any clone",
                                "reviewable_from": list(REVIEWABLE)}}
    entry.update(entry_patch)
    reg = root / "results" / "NONCITABLE.json"
    reg.write_text(json.dumps({"schema_version": 2, "note": "n", "entries": [entry]}),
                   encoding="utf-8")
    return reg, root


def test_locally_absent_is_honoured_when_the_repository_ignores_the_target(gate, tmp_path):
    """The one legitimate case: git says the path is excluded, and it says why."""
    reg, root = _absent_sandbox(tmp_path, "ok", ignore="results/inputs/", entry_patch={})
    errors, notes = gate.check(reg, root)
    assert errors == [], errors
    assert any("absent from this checkout by the repository's own ignore rule" in n
               for n in notes), notes


def test_counter_proof_locally_absent_is_not_honoured_without_an_ignore_rule(gate, tmp_path):
    """Self-declared 'absent by design' must not survive without a real .gitignore."""
    reg, root = _absent_sandbox(tmp_path, "noignore", ignore=None, entry_patch={})
    errors, _ = gate.check(reg, root)
    assert any("does not ignore that path" in e for e in errors), errors


def test_counter_proof_locally_absent_needs_a_cause(gate, tmp_path):
    """An absent target needs a reason, exactly as a present one does."""
    reg, root = _absent_sandbox(
        tmp_path, "nocause", ignore="results/inputs/",
        entry_patch={"locally_absent": {"why": "it is not here", "not_present_in": "any clone",
                                        "reviewable_from": list(REVIEWABLE)}})
    errors, _ = gate.check(reg, root)
    assert any("locally_absent.why does not state a cause" in e for e in errors), errors


def test_counter_proof_locally_absent_must_name_evidence_that_exists(gate, tmp_path):
    """The exclusion has to stay reviewable: evidence that is itself absent proves nothing."""
    reg, root = _absent_sandbox(
        tmp_path, "noevidence", ignore="results/inputs/",
        entry_patch={"locally_absent": {"why": ABSENT_WHY, "not_present_in": "any clone",
                                        "reviewable_from": ["results/never-shipped.json"]}})
    errors, _ = gate.check(reg, root)
    assert any("names no reviewable evidence" in e for e in errors), errors


def test_counter_proof_locally_absent_needs_reviewable_evidence_at_all(gate, tmp_path):
    """An empty reviewable_from is the same defect in a quieter form."""
    reg, root = _absent_sandbox(
        tmp_path, "emptyevidence", ignore="results/inputs/",
        entry_patch={"locally_absent": {"why": ABSENT_WHY, "not_present_in": "any clone",
                                        "reviewable_from": []}})
    errors, _ = gate.check(reg, root)
    assert any("names no reviewable evidence" in e for e in errors), errors


def test_a_plainly_missing_path_is_still_an_error(gate, tmp_path):
    """The exception must not become the general answer to 'the file is not here'.

    Same ignored directory, same missing file -- the only difference from the passing
    case above is that the entry carries no locally_absent block at all."""
    root = _git_repo(tmp_path / "plain", ignore="results/inputs/")
    (root / "results").mkdir(parents=True, exist_ok=True)
    reg = root / "results" / "NONCITABLE.json"
    reg.write_text(json.dumps({"schema_version": 2, "note": "n", "entries": [
        {"path": "results/inputs/gone.json#cell-1", "reason": RULE,
         "declared_in": "this registry"}]}), encoding="utf-8")
    errors, _ = gate.check(reg, root)
    assert any("declared target does not exist" in e for e in errors), errors


def test_git_ignored_fails_closed_outside_a_git_repo(tmp_path):
    """A non-repo checkout answers 'is it ignored?' with 'no', not with 'yes'."""
    mod = _gate()
    (tmp_path / "results").mkdir()
    (tmp_path / "results" / "x.json").write_text("{}", encoding="utf-8")
    assert mod.git_ignored(tmp_path, "results/x.json") is False
    assert mod.git_ignored(tmp_path, "results/never-created.json") is False

# ---------------------------------------------------------------------------
# scripts/transfer_subset.py: the subset figure must not be quotable as a trend.
# ---------------------------------------------------------------------------

def _subset():
    spec = importlib.util.spec_from_file_location(
        "transfer_subset_under_test", ROOT / "scripts" / "transfer_subset.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _cell(passed, latency=3.0, error=None, parsed=1.0):
    d = {"passed": passed, "latency": latency, "details": {"parsed": parsed}}
    if error:
        d["error"] = error
    return d


def _incomplete(details):
    return {"schema_version": 2, "INCOMPLETE": True,
            "why": "transport failures present", "error_counts": {"TimeoutError": 2},
            "meta": {"policies": ["step-calc", "cot-zero"], "n": len(details)},
            "details": details}


def test_subset_reports_how_far_p_is_from_the_threshold():
    """A p one cell from 0.05 must say so, not print a bare number."""
    sub = _subset()
    det = {}
    for i in range(30):
        det["b%02d" % i] = {"step-calc": _cell(False), "cot-zero": _cell(True)}
    for i in range(16):
        det["w%02d" % i] = {"step-calc": _cell(True), "cot-zero": _cell(False)}
    det["loop"] = {"step-calc": _cell(False, 0.0, "TimeoutError"),
                   "cot-zero": _cell(False, 0.0, "TimeoutError")}
    rep = sub.subset_report(_incomplete(det), ["loop"], ("step-calc", "cot-zero"))
    assert rep["n_subset"] == 46
    assert rep["better"] == 30 and rep["worse"] == 16
    assert rep["p"] > 0.05
    assert rep["cells_to_flip_for_significance"] == 1, rep


def test_counter_proof_subset_refuses_a_question_that_still_errors():
    """Dropping a DIFFERENT question must not launder the erroring one."""
    sub = _subset()
    det = {"ok": {"step-calc": _cell(True), "cot-zero": _cell(True)},
           "loop": {"step-calc": _cell(False, 0.0, "TimeoutError"),
                    "cot-zero": _cell(False, 0.0, "TimeoutError")}}
    with pytest.raises(SystemExit, match="still carry a transport error"):
        sub.subset_report(_incomplete(det), [], ("step-calc", "cot-zero"))


def test_counter_proof_subset_refuses_an_unknown_drop_id():
    sub = _subset()
    det = {"a": {"step-calc": _cell(True), "cot-zero": _cell(True)}}
    with pytest.raises(SystemExit, match="not in the file"):
        sub.subset_report(_incomplete(det), ["ghost"], ("step-calc", "cot-zero"))
