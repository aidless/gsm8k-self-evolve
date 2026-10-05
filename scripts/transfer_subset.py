"""Recompute a paired contrast over the cells of an INCOMPLETE run that are clean.

Why this file exists. results/rounds/round4/transfer-cotzero-svamp.json finished all
1000 questions but tripped the fail-closed gate in scripts/run_round4.py: one
question, chal-513, makes qwen2.5:7b loop forever under the cot-zero prompt
(done_reason='length' at every token cap tried, never terminates), so two cells carry
TimeoutError and the runner emitted no totals and no pairs. The file is deliberately
retained as the evidence for that exclusion rather than deleted.

That leaves a number a reader will still want: what the contrast looks like over the
999 questions where both arms answered. It is a SUBSET figure, not a run result,
and this script says so in its own output rather than leaving the distinction to the
reader.

What it does and does not do:

  * it recomputes both arms' counts, the discordant split, exact McNemar, gain and
    latency from the per-id `details` -- it never reads a recorded aggregate;
  * it refuses to run on a COMPLETE file. If the runner produced totals, those are
    the authoritative numbers and a subset view would only invite a reader to quote
    the smaller one. A complete file must be read directly;
  * it prints, next to p, how many cells one would have to flip to cross p < 0.05,
    because a p that sits one or two cells from the threshold is the easiest
    number in this repository to misread as a trend;
  * it requires the excluded cells to be named, so the subset is never silently
    smaller than the file.

Usage:
    python3 scripts/transfer_subset.py
    python3 scripts/transfer_subset.py --drop chal-513
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from evokit.stats import mcnemar_two_sided  # noqa: E402

ALPHA = 0.05


def subset_report(data: dict, drop: list[str], policies: tuple[str, str],
                  alpha: float = ALPHA) -> dict:
    x, y = policies
    details = data["details"]
    bad = sorted(q for q in drop if q not in details)
    if bad:
        raise SystemExit("dropped questions are not in the file: %s" % bad)
    cells = {q: row for q, row in details.items() if q not in drop}
    errs = {q: [p for p in policies if cells[q][p].get("error")]
            for q in cells}
    dirty = sorted(q for q, v in errs.items() if v)
    if dirty:
        raise SystemExit(
            "these questions still carry a transport error and cannot enter the "
            "subset: %s" % dirty[:10])

    n = len(cells)
    passed = {p: {q for q, row in cells.items() if row[p]["passed"]} for p in policies}
    lat = {p: [row[p].get("latency", 0.0) for row in cells.values()] for p in policies}
    better = len(passed[y] - passed[x])
    worse = len(passed[x] - passed[y])
    p = mcnemar_two_sided(better, worse)
    mean_lat = {p_: (sum(lat[p_]) / n if n else 0.0) for p_ in policies}

    # How far is p from the threshold? A "flip" moves one discordant cell from one
# side to the other: the pair (better, worse) is re-partitioned, keeping d fixed,
# because flipping one cell changes only which arm it favours, not whether it is
# discordant. So we search b' > b with c' = d - b' and report how many cells must
# change sides.
    d = better + worse
    needed = None
    for b2 in range(better + 1, d + 1):
        if mcnemar_two_sided(b2, d - b2) < alpha:
            needed = b2 - better
            break
    if needed is None:
        for b2 in range(better, -1, -1):
            if mcnemar_two_sided(b2, d - b2) < alpha:
                needed = better - b2
                break

    return {
        "n_subset": n, "n_file": len(details), "dropped": sorted(drop),
        "totals": {p_: len(passed[p_]) for p_ in policies},
        "rates": {p_: (len(passed[p_]) / n if n else 0.0) for p_ in policies},
        "better": better, "worse": worse, "d": better + worse,
        "p": p, "gain": (len(passed[y]) - len(passed[x])) / n if n else 0.0,
        "mean_latency": mean_lat,
        "lat_ratio": (mean_lat[y] / mean_lat[x]) if mean_lat[x] else None,
        "cells_to_flip_for_significance": needed,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="results/rounds/round4/transfer-cotzero-svamp.json")
    ap.add_argument("--drop", action="append", default=None,
                    help="question id to exclude; repeatable")
    ap.add_argument("--drop-file", default="results/NONCITABLE.json",
                    help="read the #cell exclusions from this registry")
    ap.add_argument("--alpha", type=float, default=ALPHA)
    a = ap.parse_args()

    drop = list(a.drop or [])
    reg = ROOT / a.drop_file
    if reg.exists() and not a.drop:
        # A cell exclusion may be recorded against EITHER the result file or the
        # input file that defines the question (the registry points at the input,
        # because that is where the question id lives and where the exclusion can be
        # checked against the shipped copy). Both are accepted, and both drop the
        # WHOLE question from the paired comparison: the exclusion is a property of
        # the question under the model, not of one arm.
        result_rel = Path(a.file).as_posix()
        stem = Path(a.file).stem                      # transfer-cotzero-svamp
        input_names = set()
        for cand in ROOT.rglob(f"{stem.removeprefix('transfer-cotzero-')}.json"):
            try:
                input_names.add(cand.resolve().relative_to(ROOT).as_posix())
            except ValueError:
                continue
        for e in json.loads(reg.read_text(encoding="utf-8")).get("entries", []):
            base, _, frag = (e.get("path") or "").partition("#")
            if not frag:
                continue
            if base == result_rel or base in input_names or \
                    base.endswith(f"inputs/{stem.removeprefix('transfer-cotzero-')}.json"):
                drop.append(frag)
    drop = sorted(set(drop))

    path = ROOT / a.file
    data = json.loads(path.read_text(encoding="utf-8"))
    if not data.get("INCOMPLETE"):
        print("This file is COMPLETE (it has authoritative totals).")
        print("A subset view of a complete run would only invite quoting the smaller")
        print("number; read the file's own totals instead:")
        print("  python3 -c \"import json;d=json.load(open('%s'));"
              "print(d['totals'],d['pairs'])\"" % a.file)
        raise SystemExit(2)

    policies = tuple(data["meta"]["policies"])
    rep = subset_report(data, drop, (policies[0], policies[1]), a.alpha)

    print("SUBSET VIEW (not a run result)")
    print("file      : %s" % a.file)
    print("status    : INCOMPLETE %s" % json.dumps(data.get("error_counts", {}),
                                                  ensure_ascii=False))
    print("dropped   : %s" % (rep["dropped"] or "(none named)"))
    print("n         : %d of %d" % (rep["n_subset"], rep["n_file"]))
    print()
    for p_ in policies:
        print("  %-10s %4d / %d = %.4f   mean latency %.3fs"
              % (p_, rep["totals"][p_], rep["n_subset"], rep["rates"][p_],
                 rep["mean_latency"][p_]))
    print()
    print("  better (%s wins) = %d    worse = %d    d = %d"
          % (policies[1], rep["better"], rep["worse"], rep["d"]))
    print("  exact McNemar p = %.16g" % rep["p"])
    print("  gain (%s - %s) = %+.4f"
          % (policies[1], policies[0], rep["gain"]))
    print("  latency ratio (%s / %s) = %.4f"
          % (policies[1], policies[0], rep["lat_ratio"]))
    print()
    if rep["p"] < a.alpha:
        print("  p < %.2f : SIGNIFICANT on this subset." % a.alpha)
    else:
        k = rep["cells_to_flip_for_significance"]
        if k:
            print("  p >= %.2f : NOT significant. Flipping as few as %d cell(s) the other"
                  % (a.alpha, k))
            print("  way would cross the threshold, so this must not be written up as")
            print("  a trend, a near-miss, or a directional finding.")
        else:
            print("  p >= %.2f : NOT significant, and the discordant split is too"
                  % a.alpha)
            print("  lopsided for a small flip to cross the threshold either.")
    print()
    print("Reminder: this is the %d questions where BOTH arms terminated. The run as a"
          % rep["n_subset"])
    print("whole has no totals, because %s recorded %d cell(s) with a transport"
          % (rep["dropped"][0] if rep["dropped"] else "an excluded question",
             len(rep["dropped"])))
    print("error and the gate refused to aggregate. Quote this as a subset or not at all.")


if __name__ == "__main__":
    main()