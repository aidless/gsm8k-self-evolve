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
