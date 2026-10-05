"""Enforcement gate for results/NONCITABLE.json.

Why this file exists. The registry's own note used to claim that its entries were
"machine-checked by scripts/emit_trajectory.py:is_citable()". That script was never
in the repository -- git has no commit adding it and only a stale .pyc remained --
so the registry was an honest record that depended on a human remembering to read
it. A registry whose whole purpose is to stop a number from being cited cannot be
enforced only by memory. This gate makes the linkage machine-checkable.

What it checks, per entry:

  1. the path exists in the registry's declared form -- a file, a *.QUARANTINE.md
     sidecar, or a `#cell` fragment identifying one (policy, question) cell inside
     an otherwise-valid result file;
  2. the entry's own `reason` is non-empty and specific (a stated exclusion rule or
     an invalidation cause), not a bare path;
  3. `declared_in` names a file that exists in the shipped set, so an entry cannot
     point at a declaration nobody will read;
  4. no shipped document may CITE an entry's path while describing it as usable.
     The check is textual and deliberately narrow: it only fires when a document
     references the path in a context that also asserts it is valid, since most
     documents legitimately mention a non-citable path to explain why it is not
     citable.

Counter-proofs are in tests/test_noncitable_gate.py: each of the four checks has a
counter-proof that injects the violation and asserts a non-zero exit.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "results" / "NONCITABLE.json"
SHIPPED_DOC_SUFFIXES = {".md"}
EXCLUDE_DIRS = {"docs", ".git", "__pycache__", ".pytest_cache", "dist", ".superpowers"}

# A document asserting a path is usable, e.g. "results/.../x.json is valid evidence".
CITING_CONTEXT = re.compile(
    r"(is\s+valid\s+evidence|may\s+be\s+cited|cite\s+this|safe\s+to\s+cite"
    r"|可引用|可作为证据)",
    re.IGNORECASE,
)


def shipped_documents(root: Path | None = None) -> list[Path]:
    root = root or ROOT
    out = []
    for p in root.rglob("*.md"):
        rel = p.relative_to(root)
        if any(part in EXCLUDE_DIRS for part in rel.parts):
            continue
        out.append(p)
    return sorted(out)


def check(registry_path: Path = REGISTRY, root: Path = ROOT) -> tuple[list[str], list[str]]:
    """Return (errors, notes). Empty errors means the registry is coherent."""
    errors: list[str] = []
    notes: list[str] = []

    if not registry_path.exists():
        return ["registry missing: %s" % registry_path], notes

    reg = json.loads(registry_path.read_text(encoding="utf-8"))
    entries = reg.get("entries") or []
    if not entries:
        return ["registry has no entries"], notes

    for i, e in enumerate(entries, 1):
        raw = e.get("path", "")
        tag = "entries[%d] %s" % (i, raw or "<no path>")

        if not raw:
            errors.append("%s: missing 'path'" % tag)
            continue

        # 1) the declared target must exist, allowing a #cell fragment.
        base = raw.split("#", 1)[0]
        frag = raw.split("#", 1)[1] if "#" in raw else None
        target = root / base
        if not target.exists():
            errors.append("%s: declared target does not exist: %s" % (tag, base))
        elif frag:
            # The fragment must name a cell that the file actually contains.
            text = target.read_text(encoding="utf-8", errors="replace")
            if '"%s"' % frag not in text:
                errors.append(
                    "%s: cell %r is not present in %s; the exclusion names "
                    "something the file does not contain" % (tag, frag, base))
            else:
                notes.append("%s: cell %r found in %s" % (tag, frag, base))
        else:
            notes.append("%s: target exists" % tag)

        # 2) a reason must state a rule or a cause, not merely repeat the path.
        # Both failure modes report under the same phrase, because from a reader's
        # point of view "too short to explain anything" and "too long but explains
        # nothing" are one defect.
        reason = (e.get("reason") or "").strip()
        no_cause_msg = (
            "%s: reason does not state a cause or an exclusion rule (%d chars); it "
            "must say WHY, so that a future reader can tell a measurement from an "
            "artifact" % (tag, len(reason)))
        if len(reason) < 40:
            errors.append(no_cause_msg)
        elif not re.search(r"(rule|because|cause|non-converg|invalidat|fail|error|"
                           r"transport|loop|规则|因为|成因|不收敛|失败)", reason, re.I):
            errors.append(no_cause_msg)

        # 3) declared_in must point at a shipped document that exists.
        declared = (e.get("declared_in") or "").strip()
        if not declared:
            errors.append("%s: missing 'declared_in'" % tag)
        elif re.match(r"(?i)^(this registry|the registry)\b", declared):
            # A self-reference is a legitimate declaration: the entry IS the
            # declaration. It resolves to this file.
            notes.append("%s: declared_in is this registry" % tag)
        else:
            first = declared.split()[0].strip("`")
            first = first.split(":")[0]
            if not (root / first).exists():
                errors.append(
                    "%s: declared_in points at %s, which does not exist in the "
                    "shipped set" % (tag, first))

    # 4) no shipped document may assert that a registered path is usable.
    for entry in entries:
        raw = (entry.get("path") or "").split("#", 1)[0]
        tag = "entries: %s" % (raw or "<no path>")
        if not raw:
            continue
        for doc in shipped_documents(root):
            text = doc.read_text(encoding="utf-8", errors="replace")
            for lineno, line in enumerate(text.splitlines(), 1):
                if raw in line and CITING_CONTEXT.search(line):
                    errors.append(
                        "%s: %s:%d cites the non-citable path %s while "
                        "asserting it is usable; an entry in this registry and a "
                        "claim that it may be cited cannot both stand"
                        % (tag, doc.relative_to(root), lineno, raw))
    return errors, notes


def main() -> int:
    errors, notes = check()
    for n in notes:
        print("  ok  %s" % n)
    if errors:
        print("\nNONCITABLE GATE FAIL (%d):" % len(errors))
        for e in errors:
            print("  FAIL %s" % e)
        return 1
    print("\nNONCITABLE GATE PASS: every registry entry names an existing target, "
          "states a cause or rule, points at a shipped declaration, and no shipped "
          "document cites it as usable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())