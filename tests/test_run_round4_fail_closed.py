"""run_round4 must refuse to aggregate a run that lost cells to transport failure.

Why this test exists: on 2026-10-04 the SVAMP transfer run (step-calc vs cot-zero) lost
840 of 1000 cells to URLError while ollama was being starved. run_one() correctly records
a transport failure as passed=False, but the aggregator counted those as WRONG ANSWERS and
emitted totals {'step-calc': 146, 'cot-zero': 148} over n=1000 -- a fabricated 0.146
accuracy for a policy that scores 0.920 on the same model in the same session. Nothing in
the output said the run was broken. That is the same failure mode already quarantined once
for the round-5 Qwen3.8-27B arm (results/rounds/round5/proposer-arm-qwen38-27b.QUARANTINE.md,
registered in results/NONCITABLE.json); it was still live in this runner.

These tests pin the fail-closed behaviour, and -- per this repo's gate discipline -- each
one carries the counter-proof that the gate CAN fail: a healthy run must pass it, and an
injected transport error must not.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# The dataset is built HERE, in tmp, not read from the repo. The real
# results/rounds/round4/inputs/multiarith.json is excluded from the publishable
# set (see OPEN_SOURCE_EXCLUSION.md), so a clean clone does not contain it --
# and a test that passes only because the author happens to have a full local
# checkout is a test that reports "136 passed" to the clone that cannot run it.
CASES = [
    {"id": "t1", "input": "If I have 3 apples and buy 4 more, how many do I have?",
     "expected": "7"},
    {"id": "t2", "input": "A shirt costs 5 dollars. How much do 4 shirts cost?",
     "expected": "20"},
]


def _dataset(tmp_path: Path) -> Path:
    p = tmp_path / "tiny.json"
    p.write_text(json.dumps({"cases": CASES}), encoding="utf-8")
    return p


def _run(dataset: Path, out: Path, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ, **(env_extra or {}))
    return subprocess.run(
        [sys.executable, "scripts/run_round4.py", "--dataset", str(dataset),
         "--policies", "step-calc,cot-zero", "--out", str(out), "--limit", "2",
         "--model", "qwen2.5:7b"],
        capture_output=True, text=True, cwd=str(ROOT), env=env, timeout=900,
    )


@pytest.mark.slow
def test_healthy_run_produces_totals_and_pairs(tmp_path):
    """Counter-proof 1: the gate must NOT block a good run (else it is decorative)."""
    out = tmp_path / "ok.json"
    r = _run(_dataset(tmp_path), out)
    assert r.returncode == 0, r.stderr
    d = json.loads(out.read_text(encoding="utf-8"))
    assert "totals" in d and "pairs" in d
    assert "INCOMPLETE" not in d
    assert set(d["totals"]) == {"step-calc", "cot-zero"}
    assert d["pairs"]["step-calc_vs_cot-zero"]["ledger_ok"] is True


@pytest.mark.slow
def test_transport_failure_blocks_aggregation(tmp_path):
    """Counter-proof 2: injecting a dead endpoint MUST make the run fail loudly."""
    out = tmp_path / "bad.json"
    r = _run(_dataset(tmp_path), out,
             env_extra={"EVO_OLLAMA_URL": "http://127.0.0.1:1/api/generate"})
    assert r.returncode != 0, "a run with transport errors must not exit 0"
    assert "REFUSING TO AGGREGATE" in r.stderr
    d = json.loads(out.read_text(encoding="utf-8"))
    assert d.get("INCOMPLETE") is True
    # the whole point: no aggregate numbers at all
    assert "totals" not in d and "pairs" not in d
    assert d["error_counts"], "error_counts must be recorded"
    # partial details survive so --resume can retry exactly the failed cells
    assert d.get("details"), "partial details must be written for resume"


def test_error_cells_are_rejected_by_the_gate_logic_not_just_the_exit_code():
    """Static guard: the gate must be in the aggregator, not bolted onto the exit path."""
    src = (ROOT / "scripts" / "run_round4.py").read_text(encoding="utf-8")
    assert "REFUSING TO AGGREGATE" in src
    assert "INCOMPLETE" in src
    # the check must read the recorded error field, which run_one() propagates
    assert 'row[pol].get("error")' in src
    # and it must fire BEFORE totals is computed
    gate_at = src.index("REFUSING TO AGGREGATE")
    totals_at = src.index("totals = {pol:")
    assert gate_at < totals_at, "the fail-closed check must precede aggregation"


def test_run_one_still_propagates_errors_for_the_incremental_consumer():
    """Additive contract: run_paired_incremental.py relies on the error key."""
    src = (ROOT / "scripts" / "run_round4.py").read_text(encoding="utf-8")
    assert '"error": type(exc).__name__' in src
    assert 'res["error"] = str(err)' in src


def test_no_test_reads_a_dataset_that_the_publish_gate_excludes():
    """A test that needs an unpublished file is a test a clean clone cannot run."""
    # Assembled at runtime so this guard does not match its own source.
    needle = "round4" + "/" + "inputs" + "/"
    for f in sorted((ROOT / "tests").glob("test_*.py")):
        text = f.read_text(encoding="utf-8")
        for n, line in enumerate(text.splitlines(), 1):
            if needle in line and not line.lstrip().startswith("#"):
                raise AssertionError(
                    f"{f.name}:{n} reads {needle}, which "
                    "OPEN_SOURCE_EXCLUSION.md keeps out of the publishable set; "
                    "build the fixture in tmp_path instead"
                )