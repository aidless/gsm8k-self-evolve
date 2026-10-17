# Signed artifacts — byte-exact copies

This directory holds byte-exact copies of the files the signed evidence
bundle (`../bundle.json`) attests to. `tools/verify_evidence_chain.py`
check [2/5] hashes the copies here, not the working-tree files.

## Why a copy is needed for `gsm8k_evaluator.py`

The bundle pins five artifacts. Four of them (`active.json`,
`examples/gsm8k40.json`, `examples/heldout40.json`,
`examples/heldout-batch2-160.json`) are unchanged in the working tree and
are still hashed in place.

`examples/gsm8k_evaluator.py` is the exception, and it is a **legitimate**
one: the evaluator kept growing after the bundle was signed. Rounds 3–5
added new policies (`reflect-retry`, `textgrad-prompt`, `cot-zero`, a
frozen few-shot baseline, a vLLM backend) as **additive** changes —
`OPEN_SOURCE_EXCLUSION.md` §3 records the diff as `+70/−2` lines with the
original `step-calc` / `concise-reason` code paths untouched (they take the
same branch). The working-tree copy therefore no longer equals the artifact
that produced the published numbers, and hashing it could only ever report a
mismatch — which is what it did, on every run since publication.

The signed version is the round-2 evaluator, 3,892 bytes, policies
`direct / concise-reason / double-check / step-calc / rounding-aware /
rectify` only. Its bytes are preserved here so the bundle stays verifiable
without freezing the evaluator forever.

## Provenance

```
manifest records  4a23f69463293b380bfd7a52be5f9e616af3d02f6e822f7be721b95015eb400e
this file         sha256 = 4a23f69463293b380bfd7a52be5f9e616af3d02f6e822f7be721b95015eb400e
```

The same bytes are independently obtainable from history:

```bash
git show f80af2f:examples/gsm8k_evaluator.py | sha256sum
# -> 4a23f69463293b380bfd7a52be5f9e616af3d02f6e822f7be721b95015eb400e
```

`f80af2f` is the commit that published the evidence chain
("GSM8K self-evolve evidence chain: direct -> concise-reason -> step-calc
(stable)", 2026-09-09). Keeping the copy in-tree means verification works
from a tarball or a shallow clone, where `git show` would not.

## What this does *not* claim

- It does **not** claim the working-tree `examples/gsm8k_evaluator.py`
  equals the signed artifact. It does not, by design.
- It does **not** claim the rounds-3–5 additions are behaviour-neutral in
  general — only that they did not alter the round-1/2 policy paths, which
  is what `OPEN_SOURCE_EXCLUSION.md` §3 records.
- It is **not** a check that cannot fail: corrupting this file makes
  check [2/5] fail (the `mutation-control` CI job perturbs a hashed
  artifact and requires a non-zero exit).
