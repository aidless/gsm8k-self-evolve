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
   exclude something that was never there.
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