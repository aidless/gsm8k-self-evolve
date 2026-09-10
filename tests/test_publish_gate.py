"""Regression tests for tools/check_publish.py (publish gate).

Additive-only: mirrors the gate's key assertions so CI catches regressions.
Stdlib + pytest only. Read-only: never touches results//signed//registry//examples/.
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATE = REPO / "tools" / "check_publish.py"


def load_gate():
    spec = importlib.util.spec_from_file_location("check_publish", GATE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_gitignore_excludes_docs_log_superpowers():
    text = (REPO / ".gitignore").read_text(encoding="utf-8")
    assert "*.log" in text, ".gitignore must ignore *.log"
    assert "docs/" in text, ".gitignore must exclude docs/"
    assert ".superpowers/" in text, ".gitignore must exclude .superpowers/"


def test_shippable_set_excludes_internal_dirs_and_logs():
    gate = load_gate()
    files = list(gate.shippable_files())
    assert files, "shippable set must be non-empty"
    for p in files:
        rel = p.relative_to(REPO)
        assert not any(part in gate.EXCLUDE_DIRS for part in rel.parts), f"leak: {rel}"
        assert p.suffix != ".log", f"log file in shippable set: {rel}"


def test_no_private_key_material():
    gate = load_gate()
    keys = [p for p in REPO.rglob("*.key")]
    assert keys == [], f"*.key files present: {keys}"
    # NOTE: build the marker by concatenation so this test file itself
    # does not contain the literal gate pattern (avoid self-match).
    marker = "-----BEGIN PRIVATE " + "KEY-----"
    for p in gate.shippable_files():
        if p.name == "check_publish.py":
            continue
        if p.name == "test_publish_gate.py":
            # self-skip: assertion source line, not shipped secret
            text = "\n".join(
                ln for ln in p.read_text(encoding="utf-8", errors="ignore").splitlines()
                if "marker =" not in ln and "BEGIN PRIVATE" not in ln
            )
        else:
            text = p.read_text(encoding="utf-8", errors="ignore")
        assert marker not in text, f"private key in {p}"


def test_no_real_secrets_in_shippable_files():
    gate = load_gate()
    for p in gate.shippable_files():
        text = p.read_text(encoding="utf-8", errors="ignore")
        assert not gate.SECRET_RE.search(text), f"secret pattern in {p.relative_to(REPO)}"


def test_license_exists_and_mit():
    lic = REPO / "LICENSE"
    assert lic.is_file(), "LICENSE must exist"
    assert "MIT License" in lic.read_text(encoding="utf-8", errors="ignore")


def test_publish_gate_script_passes():
    r = subprocess.run(
        [sys.executable, str(GATE)], capture_output=True, text=True, cwd=str(REPO)
    )
    assert r.returncode == 0, f"check_publish.py failed:\n{r.stdout}\n{r.stderr}"
    assert "PUBLISH GATE PASS" in r.stdout
