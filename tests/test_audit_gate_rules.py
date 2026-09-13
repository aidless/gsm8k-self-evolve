"""Bite-proof for the round-5 independent audit (``scripts/audit_gate_rules.py``).

A reproducibility gate that can never fail is decoration, not evidence.  These tests prove the
gate is non-vacuous in two directions:

1. ``test_audit_exits_zero_on_committed_artefacts`` — the audit recomputes every auditable figure
   from the source modules and the committed ``pools.json`` and passes (exit 0) on the committed
   ``ablation.json``.
2. ``test_audit_flags_flipped_verdict_branch`` and
   ``test_audit_flags_changed_pooled_fpr_fraction`` — a deliberately corrupted copy of
   ``ablation.json`` (a flipped ``verdict_branch``, and a hand-edited pooled FPR fraction) makes
   the same audit exit non-zero and name the drifted field, the committed value and the
   recomputed value.

The corruption is applied to an in-memory copy serialised to a temp file, so the committed
``ablation.json`` is never touched.  No sandbox escalation, no model calls, no branch/push.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "scripts" / "audit_gate_rules.py"
ABLATION = ROOT / "results" / "rounds" / "round5" / "ablation.json"


def _run_audit(ablation_path=None):
    cmd = [sys.executable, str(AUDIT)]
    if ablation_path is not None:
        cmd.append(str(ablation_path))
    return subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)


def _write_corrupt(tmpdir, mutate):
    data = json.loads(ABLATION.read_text(encoding="utf-8"))
    mutate(data)
    out = Path(tmpdir) / "ablation.json"
    out.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return out


def test_audit_exits_zero_on_committed_artefacts():
    proc = _run_audit()
    assert proc.returncode == 0, (
        f"audit must exit 0 on the committed artefacts\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}")
    assert "AUDIT PASS" in proc.stdout
    # spot-check the headline recomputed figures the audit prints (independent of ablation.json)
    assert "R1=0.0125" in proc.stdout
    assert "verdict_branch = 'i'" in proc.stdout


def test_audit_flags_flipped_verdict_branch():
    with tempfile.TemporaryDirectory() as d:
        def mutate(data):
            data["verdict_branch"] = "ii" if data["verdict_branch"] != "ii" else "iii"
            data["verdict"]["verdict_branch"] = data["verdict_branch"]
        corrupt = _write_corrupt(d, mutate)
        proc = _run_audit(corrupt)
        assert proc.returncode != 0, (
            f"audit returned 0 on a flipped verdict_branch (the gate is vacuous)\n"
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}")
        assert "verdict_branch" in proc.stdout
        assert "recomputed='i'" in proc.stdout       # the audit re-derives 'i', the copy says 'ii'


def test_audit_flags_changed_pooled_fpr_fraction():
    with tempfile.TemporaryDirectory() as d:
        def mutate(data):
            # committed pooled R2 rate is 330/800 = 0.4125; nudge it by hand.
            data["fpr"]["pooled"]["R2"]["rate"] = 0.5
        corrupt = _write_corrupt(d, mutate)
        proc = _run_audit(corrupt)
        assert proc.returncode != 0, (
            f"audit returned 0 on a hand-edited pooled FPR fraction (the gate is vacuous)\n"
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}")
        assert "fpr.pooled.R2.rate" in proc.stdout
        assert "committed=0.5" in proc.stdout
        assert "recomputed=0.4125" in proc.stdout