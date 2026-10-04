# Changelog

All notable changes to this repository are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Evidence chain is now reproducible from a clean checkout. `tools/verify_evidence_chain.py`
  is the verification entry point and prints which of its five checks fail.
- `scripts/audit_gate_rules.py` recomputes all 340 round-5 figures from the pool rows and
  fails if any differs from the committed `ablation.json`.
- `tools/check_publish.py` rejects secrets, personal absolute paths, and rewritten history.
- Round 5: 800-case proposal/verification log at
  `results/rounds/round5/decisions.jsonl`, plus the full ablation table in `README.md`.
- Length-versus-gain analysis (`scripts/complexity_vs_gain.py`) and the SANKEN-style
  retention report (`scripts/retention_report.py`).
- Governance baseline: LICENSE, security policy, code of conduct, contributor and
  support guides, issue and pull-request templates, CODEOWNERS, changelog, dependabot,
  and `.editorconfig` added. No research content changed.

### Changed

- **`main` was rebuilt once.** The research history and the governance files arrived on
  two unrelated roots; they are now one line of commits. History was not rewritten after
  that point. Clone again rather than merging if you cloned earlier — see the History
  section of `CONTRIBUTING.md`.

### Fixed

- `scripts/run_round4.py` no longer counts a transport error as a wrong answer. A run in
  which any cell failed to reach the model now refuses to aggregate: it writes an
  `INCOMPLETE` record with the per-error counts, keeps the partial details for `--resume`,
  and exits non-zero without producing `totals` or `pairs`. Previously an ollama outage
  silently produced plausible-looking accuracy figures.
- Result metadata records dataset paths relative to the repository instead of the
  absolute path of whichever machine ran the experiment.
