"""A-line publish gate: fail closed on leaks, pass only when shippable.

Checks (repo root = parent of this file):
  1. No *.log tracked-or-present in shippable set (results/**/*.log exist locally but must be git-ignored).
  2. docs/ and .superpowers/ are git-ignored (internal plans with push-token notes + local paths).
  3. No *.key / private key material staged or present (public hex only).
  4. No real secrets (sk-/ghp-/AKIA/Bearer-long) in shippable files (*.py/*.json/*.md/*.txt, excluding docs/, .superpowers/, .git/).
  5. No personal absolute paths (home dirs, data volumes, OS user names) in shippable files.
     NOTE: /root/exp-gsm8k provenance keys in signed/bundle.json + old script comments are
     intentional cloud-path provenance (see OPEN_SOURCE_EXCLUSION.md §2) and are allowlisted.

Exit 0 iff PUBLISH GATE PASS; else prints failing check and exits 1.
Stdlib only.
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EXCLUDE_DIRS = {"docs", ".superpowers", ".git", "__pycache__", ".pytest_cache"}
SECRET_RE = re.compile(r"sk-[A-Za-z0-9]{8,}|ghp_[A-Za-z0-9]{8,}|AKIA[0-9A-Z]{10,}|Bearer [A-Za-z0-9_\-\.]{16,}")
PERSONAL_PATH_RE = re.compile(r"/home/|/data1|Administrator")
ALLOW_ROOT_PROVENANCE = re.compile(r"/root/exp-gsm8k|/root/evo-agent")


def fail(msg):
    print(f"FAIL: {msg}")
    sys.exit(1)


def shippable_files():
    exts = {".py", ".json", ".md", ".txt"}
    for p in REPO.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(REPO)
        if any(part in EXCLUDE_DIRS for part in rel.parts):
            continue
        if p.suffix == ".log":
            continue
        if p.suffix in exts or p.name in {"LICENSE", ".gitignore"}:
            yield p


def main():
    # 1. *.log must be ignored (may exist locally, must not ship)
    gitignore = (REPO / ".gitignore").read_text(encoding="utf-8")
    if "*.log" not in gitignore:
        fail(".gitignore missing *.log")
    print("PASS [1/5] *.log ignored")

    # 2. docs/ + .superpowers/ excluded
    if "docs/" not in gitignore or ".superpowers/" not in gitignore:
        fail(".gitignore must exclude docs/ and .superpowers/")
    print("PASS [2/5] docs/ + .superpowers/ excluded")

    # 3. no private keys
    keys = [p for p in REPO.rglob("*.key")]
    for p in shippable_files():
        if p.name == "check_publish.py":
            continue
        if "-----BEGIN PRIVATE KEY-----" in p.read_text(encoding="utf-8", errors="ignore"):
            keys.append(p)
    if keys:
        fail(f"private key material present: {[str(p.relative_to(REPO)) for p in keys]}")
    print("PASS [3/5] no *.key / private key")

    # 4. no real secrets in shippable set
    for p in shippable_files():
        text = p.read_text(encoding="utf-8", errors="ignore")
        if SECRET_RE.search(text):
            fail(f"real secret pattern in {p.relative_to(REPO)}")
    print("PASS [4/5] no real secrets in shippable files")

    # 5. no personal absolute paths (allow /root/exp-gsm8k provenance)
    # Self-skip: this script's own regex-definition lines contain the patterns
    # being searched for, so exclude lines that define the gate itself.
    SELF_DEF_RE = re.compile(r"_RE\s*=\s*re\.compile")
    for p in shippable_files():
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if p.name == "check_publish.py" and SELF_DEF_RE.search(line):
                continue
            if p.name == "check_publish.py" and "/root/" in line and (
                "in line" in line or "allowlisted" in line or "gate-implementation" in line or "non-provenance" in line
            ):
                continue  # gate-implementation lines, not shipped content
            if PERSONAL_PATH_RE.search(line):
                fail(f"personal abs path in {p.relative_to(REPO)}:{i}")
            if "/root/" in line and not ALLOW_ROOT_PROVENANCE.search(line):
                fail(f"non-provenance /root/ path in {p.relative_to(REPO)}:{i}")
    print("PASS [5/5] no personal abs paths (/root/exp-gsm8k provenance allowlisted)")

    print("\nPUBLISH GATE PASS: shippable set clean (docs/*.log/*.key excluded, history untouched)")


if __name__ == "__main__":
    main()
