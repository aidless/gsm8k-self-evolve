# Security Policy

## Supported Versions

Security fixes are applied to the current default branch. Archived versions are
not patched.

## Zero tolerance for secrets

Never commit secrets: no API keys (`sk-`), no GitHub tokens (`ghp_`),
no AWS keys (`AKIA`), no bearer tokens, no `*.key` / private-key material.
The private key is never published; only `signed/agent-self.pub.hex`
(public key, hex) ships. `tools/check_publish.py` enforces this mechanically
and runs in CI.

## Reporting a Vulnerability

**Please do not open a public issue for security problems.**

Use GitHub's private reporting channel:
**Security → Report a vulnerability** (https://github.com/aidless/gsm8k-self-evolve/security/advisories/new),
or contact the maintainer directly. If you have found a leaked credential,
report it privately and it will be rotated/removed.

Please include:

- what the issue is and which component is affected
- steps to reproduce, or a proof-of-concept
- the impact you believe it has

## Response

A human-readable acknowledgement within a few business days, best effort.
Triage and a fix timeline depend on severity; no SLA is promised. Confidentiality
is maintained for reporters throughout.

## Scope

This repository is a research artifact: code, data, and pre-registration documents. Reports about dependencies with a published CVE
are welcome and will be tracked; issues in upstream services are out of scope.

Reports about the integrity of published evidence, hashes, or manifests are valued:
the repositories here carry SHA-256 manifests, and a broken recomputation is a security issue too.

## Publish exclusion (what ships vs what stays local)

Defined in `OPEN_SOURCE_EXCLUSION.md` and enforced mechanically by
`tools/check_publish.py`, which runs in CI:

- `docs/`, `.superpowers/`, `results/**/*.log`, `*.key` are excluded;
- `*.json` evidence is retained; **history is never rewritten**.
