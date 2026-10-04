#!/usr/bin/env python3
"""Was the treatment actually applied?

An arm that injects nothing still loses to the incumbent. So "our X did not beat
the baseline" is not evidence about X unless X was present in the arm. This tool
is the check that separates those two cases, and it exits non-zero when a
proposer-style arm ships an empty treatment.

The round-5 case it exists for: results/rounds/round5/proposer-arm-qwen38-27b-run2.json
compares a `textgrad` policy against `cot-zero` and reports b=1, c=2, p=1.0. The
product it shipped (examples/prompts/textgrad-prompt.txt) has a body identical to
BASE_PROMPT plus a trailing newline. The comparison is well-formed and carries no
information about the hypothesis.

Run it before citing any arm result that involved a rewritten or injected prompt:

    python tools/check_treatment_applied.py            # scans results/rounds/*/
    python tools/check_treatment_applied.py --json out.json

Exit 0 = every declared proposer product carries a real treatment.
Exit 1 = at least one is empty; do not cite that arm.
"""

import argparse
import json
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

# A prompt file is judged against the body it is supposed to be replacing. The
# baseline is located from the runner that produced the arm, not guessed.
STOPWORDS = frozenset("""
a an the and or but if then of to in on at by for with from as is are was were be
been being it its this that these those not no do does did can could should would
may might must will shall we you they he she i me my our your their so than there
here when where which who whom what how why all any both each few more most other
some such only own same too very just also into over under about after before
between during without within across per one two
""".split())


def content_tokens(text):
    if not text:
        return set()
    out = set()
    for raw in text.split():
        w = "".join(ch for ch in raw.lower() if ch.isalnum() or ch in "-_")
        if not w:
            continue
        for ch in w:
            if "一" <= ch <= "鿿":
                out.add(ch)
        if w not in STOPWORDS and len(w) > 1:
            out.add(w)
    return out


def split_header(text):
    """A provenance line at the top is metadata, not treatment.

    Files in this repo begin with a brace-escaped JSON header, e.g.
    {{"rewritten_from": "step-calc", "oracle": "train-only", "frozen": true}}
    Strip it before measuring, or a null arm looks like it injected content.
    """
    lines = text.splitlines(keepends=True)
    if lines and lines[0].lstrip().startswith("{{"):
        return lines[0], "".join(lines[1:])
    return "", text


def treatment_delta(baseline, injected):
    """Measure what the injected prompt adds beyond the baseline body.

    Returns a verdict dict. `verdict` is one of:
      real   -- the body carries content the baseline does not
      empty  -- the body adds nothing: a null arm, or a file that does not exist
    A provenance header is stripped before measuring, so metadata cannot make an
    empty treatment look instrumented.
    """
    _, inj_body = split_header(injected)

    # Normalised comparison, then a content check. Deliberately two rules and not
    # five: an earlier version had separate branches for "trailing whitespace"
    # and "one trailing newline", both of which the normalised comparison already
    # catches. Unreachable rules are indistinguishable from missing ones until
    # someone relaxes the one that is actually load-bearing.
    if inj_body.strip() == baseline.strip():
        verdict, detail = "empty", "injected body == baseline body (modulo whitespace)"
    else:
        added = content_tokens(inj_body) - content_tokens(baseline)
        # A rearrangement of the baseline's own words adds no treatment, however
        # different it looks character by character.
        verdict = "real" if added else "empty"
        detail = (f"{len(added)} content tokens beyond the baseline" if added
                  else "body differs but reuses only the baseline's own content words")
    return {
        "verdict": verdict,
        "detail": detail,
        "added_content_tokens": len(content_tokens(inj_body) - content_tokens(baseline)),
    }


def baseline_prompt_for(policy):
    """The baseline a rewritten product was derived from, if the repo names one."""
    if policy in ("textgrad", "textgrad-prompt", "textgrad_rewrite"):
        src = os.path.join(ROOT, "scripts", "textgrad_rewrite.py")
        if os.path.exists(src):
            txt = open(src, encoding="utf-8").read()
            m = re.search(r'BASE_PROMPT\s*=\s*\((.*?)\)\s*\n', txt, re.S)
            if m:
                return eval("(" + m.group(1) + ")"), src
    return None, None


def scan(rounds_dir="results/rounds"):
    """Find every arm that declares an injected prompt product, and judge it."""
    found = []
    base_dir = os.path.join(ROOT, rounds_dir)
    if not os.path.isdir(base_dir):
        return found
    for dirpath, _dirs, files in os.walk(base_dir):
        for fn in sorted(files):
            if not fn.endswith(".json"):
                continue
            path = os.path.join(dirpath, fn)
            try:
                data = json.load(open(path, encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            for rec in _walk_dicts(data):
                rel = rec.get("product_file") or rec.get("prompt_file")
                if not rel:
                    continue
                prod = os.path.join(ROOT, rel)
                if not os.path.exists(prod):
                    found.append({"evidence": os.path.relpath(path, ROOT),
                                  "product": rel, "verdict": "missing",
                                  "detail": "declared product file does not exist"})
                    continue
                injected = open(prod, encoding="utf-8").read()
                rewritten_from = rec.get("rewritten_from") or "textgrad"
                baseline, base_src = baseline_prompt_for(rewritten_from)
                if baseline is None:
                    found.append({"evidence": os.path.relpath(path, ROOT),
                                  "product": rel, "verdict": "unknown",
                                  "detail": f"no baseline prompt known for {rewritten_from!r}"})
                    continue
                res = treatment_delta(baseline, injected)
                res.update({"evidence": os.path.relpath(path, ROOT), "product": rel,
                            "baseline": os.path.relpath(base_src, ROOT)})
                found.append(res)
    return found


def _walk_dicts(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from _walk_dicts(v)
    elif isinstance(o, list):
        for v in o:
            yield from _walk_dicts(v)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="write the report here")
    ap.add_argument("--allow-empty", action="store_true",
                    help="report only; do not exit non-zero. For inspecting, not for citing.")
    a = ap.parse_args(argv)

    rows = scan()
    if not rows:
        print("no arm declares an injected prompt product; nothing to judge (exit 0)")
        return 0

    print(f"{'verdict':10} {'product':46} detail")
    print("-" * 110)
    for r in rows:
        print(f"{r['verdict']:10} {r['product']:46} {r['detail']}")
        if r.get("evidence"):
            print(f"{'':10} {'':46}   via {r['evidence']}")

    bad = [r for r in rows if r["verdict"] in ("empty", "missing")]
    unknown = [r for r in rows if r["verdict"] == "unknown"]
    print()
    if bad:
        print(f"DO NOT CITE: {len(bad)} arm(s) shipped an empty or missing treatment.")
        for r in bad:
            print(f"  - {r['product']}: {r['detail']}")
        print("An arm that injects nothing still loses to the incumbent, so its loss "
              "says nothing about the hypothesis.")
    if unknown:
        print(f"UNDECIDED: {len(unknown)} arm(s) have no known baseline to compare against.")
    if not bad and not unknown:
        print(f"ALL {len(rows)} arm(s) carry a real treatment.")

    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump({"rows": rows, "citable": not bad}, fh, indent=2, ensure_ascii=False)
    if bad and not a.allow_empty:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
