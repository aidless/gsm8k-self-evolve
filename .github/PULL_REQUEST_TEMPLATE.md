## What

One or two sentences.

## Why

What breaks or is missing without this. Link the issue if there is one.

## How

The approach you took, and anything a reviewer should know to evaluate it.

## Verification

- [ ] Tests or checks added or updated for this change
- [ ] `python3 -m pytest -q` and `python scripts/audit_gate_rules.py` pass locally
      (`tools/check_publish.py` too; `tools/verify_evidence_chain.py` passes 5/5 on
      `main` — it hashes the preserved signed artifacts, see the README section
      "Signed artifacts, and why one of them is a preserved copy")
- [ ] No secrets, credentials, or personal data in the diff

## Notes for reviewers

Anything you deliberately left out, or evidence that should be re-checked.
