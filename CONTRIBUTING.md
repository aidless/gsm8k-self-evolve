# Contributing

Thanks for your interest in improving this repository.

## Scope

This is a research artifact. Changes that affect **research claims, statistics, or
paper text** are not accepted as routine pull requests: they need to be discussed in
an issue first, because a claim change requires re-running the evidence pipeline and
regenerating the manifest, not just editing prose.

Contributions that fit the ordinary flow:

- bugs in the code or the verification scripts
- reproducibility problems (a recomputation that fails, a missing dependency, an
  unclear instruction)
- documentation that contradicts the code
- additional tests and negative-control fixtures
- translation and formatting

## Getting set up

```bash
git clone https://github.com/aidless/gsm8k-self-evolve.git
cd gsm8k-self-evolve
pip install -r requirements.txt
```

## Verifying your change

There is no `make check` and no `python3 verify_evidence.py` in this repository; three
real gates exist, and they do not all exit 0:

```bash
python3 -m pytest -q                    # unit + negative-control tests
python scripts/audit_gate_rules.py      # recomputes all 340 round-5 figures from the pool rows
python tools/check_publish.py           # publication gate (secrets, absolute paths, history)
python tools/verify_evidence_chain.py   # 5-check chain; exits 1 on HEAD BY DESIGN
```

`tools/verify_evidence_chain.py` exits 1 on the current `main` because
`examples/gsm8k_evaluator.py` was edited after it was promoted into the signed bundle.
That is a documented, reproducible failure, not a transient one: the bundle records the
evaluator hash as `4a23f69463293b380bfd7a52be5f9e616af3d02f6e822f7be721b95015eb400e`
(`git show f80af2f:examples/gsm8k_evaluator.py | sha256sum`), and the working-tree copy
hashes to something else. See the "Known honest FAIL on HEAD" section of `README.md`.

A pull request that does not state how it was verified will not be reviewed.

## Claim-changing changes

Open an issue that states, in order:

1. the current claim and where it is stated (file and field)
2. the new evidence, and how it was produced (script, seed, environment)
3. what changes in the manuscript, appendix, or evidence manifest as a result

Research changes are landed only after the evidence recomputes and the manifests
match. Expect the review to ask for the recomputation output.

## Commit messages

One logical change per commit. Reference the issue. No unrelated reformatting in the
same commit.

## History

This repository's `main` was rebuilt once, in October 2026, to bring the research
history and the governance files onto one line of commits. That history was never
rewritten afterwards. If you cloned before that point, your `origin/main` points at an
unrelated root commit; discard the local copy and clone again rather than trying to
merge:

```bash
rm -rf gsm8k-self-evolve && git clone https://github.com/aidless/gsm8k-self-evolve.git
```
