# FINAL ACCEPTANCE — gsm8k-self-evolve P1-CLOSE (2026-09-10)

Base commit: `6040d15135dc6f4c99e386254ad27ee8abb8f747` (P1-HARDEN).
Close commit: see `git log --oneline -1` after P1-CLOSE (additive: PHASE_LOG.md + this file only).

## Gates (re-verified at close, cwd=gsm8k-self-evolve)

1. `git status --short` → empty (clean); `git log --oneline -3` head = P1-HARDEN.
2. `python3 -m pytest -q` → `10 passed` (no gate self-match recurrence; no test edits needed).
3. `python3 tools/check_publish.py` → PASS [1/5]..[5/5] then `PUBLISH GATE PASS`.

## Known honesty case (expected, not a defect)

- `python3 tools/verify_evidence_chain.py` → `PASS [1/5] bundle.sha256 == sha256(canonical manifest)`
  then `FAIL: artifact hash mismatch for gsm8k_evaluator.py`.
- `git show f80af2f:examples/gsm8k_evaluator.py | sha256sum` →
  `4a23f69463293b380bfd7a52be5f9e616af3d02f6e822f7be721b95015eb400e`
  (matches the documented expected value verbatim).
- Recorded as the round3-additive-evolution honest FAIL. History files
  (results/, signed/, registry/, examples/) untouched.

## Scope compliance

- Additive only: PHASE_LOG.md (P1-CLOSE section) + FINAL_ACCEPTANCE.md.
- No push, no remotes created, other repos untouched. Task10 push stays BLOCKED.
