"""A-line local release packager: archive the shippable set only.

Runs the publish gate first (fail closed), then archives
check_publish.shippable_files() into dist/gsm8k-self-evolve-shippable.zip
and writes a SHA-256 manifest (dist/SHA256SUMS).

Stdlib only. Read-only with respect to evidence: never touches
results/, signed/, registry/, examples/. Produces a build artifact under
dist/ (git-ignored); the packaging steps are reproducible from this script.
"""
import hashlib
import subprocess
import sys
import zipfile
from pathlib import Path

# Same directory as check_publish.py; reuse its shippable_files() so the
# archive stays locked to the gate's single source of truth (no drift).
import check_publish as gate

REPO = Path(__file__).resolve().parent.parent
DIST = REPO / "dist"
ARCHIVE = DIST / "gsm8k-self-evolve-shippable.zip"


def main():
    # 1. Fail closed: publish gate must pass before we package anything.
    r = subprocess.run(
        [sys.executable, str(REPO / "tools" / "check_publish.py")],
        capture_output=True, text=True, cwd=str(REPO),
    )
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr)
        sys.exit(1)
    print(r.stdout.strip())

    # 2. Collect the shippable set (already excludes internal dirs + *.log).
    files = sorted(gate.shippable_files(), key=lambda p: str(p.relative_to(REPO)))

    # 3. Zip with preserved relative paths; record per-file sha256.
    DIST.mkdir(exist_ok=True)
    rows = []
    with zipfile.ZipFile(ARCHIVE, "w", zipfile.ZIP_DEFLATED) as z:
        for p in files:
            rel = p.relative_to(REPO)
            z.write(p, rel)
            rows.append((hashlib.sha256(p.read_bytes()).hexdigest(), str(rel)))

    (DIST / "SHA256SUMS").write_bytes(
        b"\n".join(f"{h}  {rel}".encode() for h, rel in rows) + b"\n"
    )
    archive_sha = hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()

    print(f"\nRELEASE PACKAGED: {ARCHIVE}")
    print(f"files: {len(rows)}")
    print(f"archive sha256: {archive_sha}")
    print("excluded by gate: internal dirs, *.log, *.key, pycache — not shipped")


if __name__ == "__main__":
    main()