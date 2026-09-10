# Security Policy

## Zero tolerance for secrets

Never commit secrets: no API keys (`sk-`), no GitHub tokens (`ghp_`),
no AWS keys (`AKIA`), no bearer tokens, no `*.key` / private-key material.
The private key is never published; only `signed/agent-self.pub.hex`
(public key, hex) ships.

## Report a vulnerability

Open a GitHub Security Advisory for this repo, or contact the maintainer
listed in `LICENSE`. Do not post suspected secrets in public issues —
report privately and we will rotate/remove.

## Publish exclusion (pointer)

What ships vs what stays local is defined in
`OPEN_SOURCE_EXCLUSION.md` (machine-enforced by `tools/check_publish.py`):

- `docs/`, `.superpowers/`, `results/**/*.log`, `*.key` are excluded;
- `*.json` evidence is retained; history is never rewritten.
