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
     an otherwise-valid result file. The one exception is a target the repository
     itself excludes (a runtime dataset under a .gitignore'd inputs/ directory),
     which is honoured only when the ignore rule, a stated cause and at least one
     reviewable evidence file are all present -- see _absent_target_verdict();
  2. the entry's own `reason` is non-empty and specific (a stated exclusion rule or
     an invalidation cause), not a bare path;
  3. `declared_in` names a file that exists in the shipped set, so an entry cannot
     point at a declaration nobody will read;
  4. no shipped document may CITE an entry's path while describing it as usable.
     The check is textual and deliberately narrow: it only fires when a document
     references the path in a context that also asserts it is valid, since most
     documents legitimately mention a non-citable path to explain why it is not
     citable.

Why check 1 needs its exception at all. Before schema_version 2 every entry had to
name a file in the checkout, so four entries failed the gate on any fresh clone --
including one whose target is a dataset that is never committed by design. A gate
that reports a missing-artifact defect for its own exclusion list is a gate nobody
can keep green, and the fix people reach for is to delete the exclusions. So the
exception is deliberately narrow: it is keyed on `git check-ignore`, a fact the
entry cannot assert about itself, and it requires the exclusion to name evidence
that IS in the checkout. A path that is merely missing stays an error.
"""
from __future__ import annotations

import json
import re
import subprocess
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

# What a stated cause looks like. Shared by `reason` and `locally_absent.why`,
# because "explain nothing" and "explain nothing in a different field" is one defect.
CAUSE = re.compile(
    r"(rule|because|cause|non-converg|invalidat|fail|error|transport|loop"
    r"|licen[cs]e|gitignore|never committed|fetched at runtime"
    r"|规则|因为|成因|不收敛|失败|许可)",
    re.IGNORECASE,
)


def states_a_cause(text: str) -> bool:
    """True when `text` is specific enough to explain something AND names a cause.

    Two failure modes collapse into one verdict because from a reader's point of
    view they are one defect: too short to explain anything, and long but
    explaining nothing.
    """
    text = (text or "").strip()
    return len(text) >= 40 and bool(CAUSE.search(text))


def git_ignored(root: Path, rel: str) -> bool:
    """True only if this repository's own ignore rules exclude `rel`.

    Deliberately asked of git rather than taken from the registry entry: an entry
    that could declare itself ignored would turn the exception into a blanket
    escape hatch for any missing artifact. Fails closed -- any problem answering
    the question (no git, not a repo, timeout) returns False, which leaves the
    entry an error.
    """
    try:
        p = subprocess.run(
            ["git", "-C", str(root), "-c", "safe.directory=*", "check-ignore", "-q",
             "--", rel],
            capture_output=True, timeout=20)
    except Exception:
        return False
    return p.returncode == 0


def _absent_target_verdict(tag: str, entry: dict, base: str,
                           root: Path) -> tuple[list[str], str | None]:
    """Verdict for a declared target that is absent from this checkout.

    Returns (errors, note). `locally_absent` is honoured only when all of:

      * the repository's own .gitignore excludes the path (git_ignored);
      * `locally_absent.why` states a cause, not merely "it is absent";
      * `locally_absent.reviewable_from` names at least one file that IS present
        here, so the exclusion stays reviewable without the absent file.

    Every failure path returns an error. An entry without `locally_absent`, or
    with one that cannot be checked, is reported exactly as before.
    """
    missing = "%s: declared target does not exist: %s" % (tag, base)

    la = entry.get("locally_absent")
    if not isinstance(la, dict):
        return [missing], None

    why = str(la.get("why") or "").strip()
    if not states_a_cause(why):
        return ["%s, and locally_absent.why does not state a cause (%d chars); an "
                "absent target needs a reason a reader can check" % (missing, len(why))], None

    if not git_ignored(root, base):
        return ["%s, and locally_absent is not honoured because this repository does "
                "not ignore that path; 'absent by design' has to be backed by a "
                ".gitignore rule, not asserted by the entry" % missing], None

    reviewable = [str(p).strip() for p in (la.get("reviewable_from") or []) if str(p).strip()]
    gone = [p for p in reviewable if not (root / p).exists()]
    if not reviewable or gone:
        return ["%s, and locally_absent names no reviewable evidence in this "
                "checkout (reviewable_from=%s); an exclusion nobody can open is the "
                "weak form of 'must not cite' that this registry exists to avoid"
                % (missing, gone or "empty")], None

    note = ("%s: target absent from this checkout by the repository's own ignore "
            "rule; %s. Reviewable from %s" % (tag, la.get("not_present_in", "not shipped"),
                                               ", ".join(reviewable)))
    return [], note


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
            absent_errors, absent_note = _absent_target_verdict(tag, e, base, root)
            if absent_errors:
                errors.extend(absent_errors)
            elif absent_note:
                notes.append(absent_note)
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
        if not states_a_cause(reason):
            errors.append(
                "%s: reason does not state a cause or an exclusion rule (%d chars); it "
                "must say WHY, so that a future reader can tell a measurement from an "
                "artifact" % (tag, len(reason)))

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
    print("\nNONCITABLE GATE PASS: every registry entry names an existing target (or a "
          "target this repository excludes by its own ignore rule, with a stated "
          "cause and reviewable evidence), states a cause or rule, points at a "
          "shipped declaration, and no shipped document cites it as usable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())