# NONCITABLE registry — what it is, and what enforces it

`results/NONCITABLE.json` lists artifacts that must not appear in any claim, ledger
entry, table or trajectory row. Two forms are recognised: an artifact path, or an
artifact path with a `#cell` fragment naming one (policy, question) cell inside an
otherwise-valid result file.

## The registry used to claim more than it had

Its own `note` read:

> Both are machine-checked by `scripts/emit_trajectory.py:is_citable()`; neither
> depends on anyone remembering to read a neighbouring document.

**That was false.** `git log --all -- scripts/emit_trajectory.py` returns nothing:
the script was never committed. What remained was
`scripts/__pycache__/emit_trajectory.cpython-312.pyc`, a stale bytecode file with
no source. So the registry was an honest record that depended entirely on a human
reading it — which is the weakest form a "must not cite" list can take.

The `note` now says so, in those words, rather than leaving the false claim in place.

## What enforces it now

`tools/check_noncitable.py` (exit 0 pass / exit 1 fail). For every entry it checks:

1. **the declared target exists.** A path that names nothing is a dead exclusion. A
   `#cell` fragment must name a cell the file actually contains, so an entry cannot
   exclude something that was never there. The single exception is a target this
   repository itself excludes — see *Targets that are absent by design* below.
2. **the reason states a cause or an exclusion rule.** An entry that says only "do
   not cite this" gives a reader nothing to tell a measurement from an artifact.
   Both "too short to explain anything" and "long but explains nothing" report
   under the same phrase, because they are one defect.
3. **`declared_in` resolves.** A declaration nobody will read is not a
   declaration. A self-reference ("this registry") resolves to the registry.
4. **no shipped document asserts that a registered path is usable.** The check is
   textual and deliberately narrow: it fires only when a `.md` file mentions the
   path in the same sentence that calls it valid evidence or citable. Documents
   that mention a non-citable path *to explain why it cannot be used* pass, which
   is most legitimate mentions.

## Targets that are absent by design (`locally_absent`)

Two real entries name targets that are in **no clone**, including a fresh one:
the Track B runtime datasets `results/rounds/round4/inputs/svamp.json` and
`results/rounds/round4/inputs/asdiv.json`, excluded wholesale by `.gitignore`
because the upstream licences (ASDiv CC-BY-NC-4.0; MultiArith unclear) forbid
redistribution. Only the result JSONs are shipped. The `asdiv.json` entry
(`#asdiv-1304`) differs from `#chal-513` in one way that its `runs[0].note`
records: the excluded question was removed from the run set *before* the
retained run, so the shipped result JSON cannot even show it failing — the
non-termination evidence lives in `TRANSFER_RECORD.md` boundary 7 instead.

Before this exception, that entry — and three others — failed the gate on every
fresh clone:

```
NONCITABLE GATE FAIL (4):
  FAIL entries[2] …proposer-arm-qwen25-7b.json: declared target does not exist
  FAIL entries[3] …transfer-cotzero-svamp.json: declared target does not exist
  FAIL entries[4] …transfer-cotzero-multiarith.json: declared target does not exist
  FAIL entries[5] …inputs/svamp.json#chal-513: declared target does not exist
```

and `tests/test_noncitable_gate.py::test_the_real_registry_passes` failed with
it, so `.github/workflows/verify.yml` was red on every push. **A gate that reports
a missing-artifact defect for its own exclusion list is a gate nobody can keep
green**, and the fix people reach for is to delete the exclusions. The three
shippable targets were fixed the honest way — committed, so the exclusion is
reviewable. The uncommittable one needed a rule.

`locally_absent` is that rule, and it is honoured only when **all** of:

- **this repository's own `.gitignore` excludes the path** — asked of `git
  check-ignore`, not taken from the entry. An entry that could declare itself
  ignored would turn the exception into a blanket escape hatch for any missing
  artifact. Fails closed: no git, not a repo, or a timeout all answer "not ignored".
- **`locally_absent.why` states a cause** — same test as `reason`, so "it is not
  here" does not qualify.
- **`locally_absent.reviewable_from` names at least one file that is present here** —
  so the exclusion stays openable without the absent file. For the `chal-513`
  entry that is the shipped SVAMP result (which records the cell's `TimeoutError`
  and latency), `TRANSFER_RECORD.md`, and `scripts/transfer_subset.py`.

Any of the three missing, or an entry with no `locally_absent` at all, is reported
exactly as before. Each condition has its own counter-proof, plus one for the case
that matters most: a plainly missing path, in the very same ignored directory, is
**still** an error.

## One path, several runs (`schema_version` 2)

A bare path cannot distinguish two runs of the same script, and the registry got
that wrong in a way that was visible in the artifacts: the entries for
`transfer-cotzero-svamp.json` and `transfer-cotzero-multiarith.json` said
*"Deleted rather than retained"*, which described the 2026-10-04 transport storm
— while the files on disk are the 2026-10-05 reruns, which the `#chal-513` entry
describes as *"retained rather than deleted"*. The registry contradicted both
itself and the artifact it pointed at.

`schema_version: 2` gives every path-valued entry a `runs` list, so each run is
recorded with its own label and `status` (`retained` / `deleted`) under one
coherent reason. The exclusion itself did not change: both runs of both files stay
non-citable. What changed is that the record now matches the file.


## What the gate deliberately does not do

It does not judge whether an exclusion is **substantively** justified. Adding a
coherent, well-reasoned entry for a file that is in fact perfectly valid will pass
this gate. That is by design: whether an artifact should be excluded is a research
judgement, and a gate that second-guessed it would either be bypassed or would
start blocking legitimate work. The gate enforces that every exclusion is
*traceable and explainable*, not that it is *correct*.

## Counter-proofs

`tests/test_noncitable_gate.py` builds each violation in a tmp directory and calls
`check()` with an injected registry path and root, then asserts a non-empty error
list. Injecting the paths matters: running the script from elsewhere still reads the
real registry, because its `ROOT` comes from `__file__`, so a "run it from /tmp"
counter-proof proves nothing.

The four violations that must fail: a target that does not exist; a `#cell` fragment
naming an absent cell; a reason with no cause; a `declared_in` pointing at nothing; a
document citing the path as usable evidence; an empty registry (a silent way to
disable the gate).

Run it:

```bash
python3 tools/check_noncitable.py
python3 -m pytest -q tests/test_noncitable_gate.py
```