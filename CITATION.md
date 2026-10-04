# Citation

## Citing this repository

No DOI has been minted for this repository yet. Until one exists, cite the commit that
you actually used -- the whole point of this repo is that its numbers are recomputable, so
a citation without a commit is not reproducible:

```bibtex
@misc{aidless_gsm8k_self_evolve,
  author       = {Liu, Zewen},
  title        = {GSM8K Self-Evolve: fail-closed, gate-audited prompt-policy evolution},
  howpublished = {\url{https://github.com/aidless/gsm8k-self-evolve}},
  note         = {Commit \texttt{<sha>}; numbers recomputable via
                 \texttt{python tools/verify\_evidence\_chain.py}},
  year         = {2026}
}
```

**Do not cite the round-2 headline alone.** The recomputable claim of this repository is
narrower -- see "What to believe, in one paragraph" in `README.md`. In particular:

- the robust effect is CoT-style prompting >> number-only answering;
- the self-evolution-specific gain over standard zero-shot CoT is **not detected**
  (p = 0.80, n = 200) -- an honest null, not proof of equivalence;
- the round-5 ablation certifies *having an effective alpha = 0.05 significance test*,
  not the five-key gate structure.

## Citing the paper

The anonymised draft lives in `paper/DRAFT.md`, with `paper/RESULTS.md` for full results
and `paper/CLAIM_LEDGER.md` for every claim plus its `file:line` anchor and status.
**It has not been submitted to a venue; do not cite it as published work.**

## Licensing

Code is MIT (`LICENSE`). Data, documentation, and pre-registration artifacts are released
under CC-BY-4.0 -- <https://creativecommons.org/licenses/by/4.0/>.

## Verifying before you cite

```bash
pip install -r requirements.txt
python tools/verify_evidence_chain.py   # note: exits 1 on HEAD by design -- see README
python tools/verify_question_provenance.py
python scripts/audit_gate_rules.py      # recomputes all 340 round-5 figures
```

The `verify_evidence_chain.py` exit code is documented rather than hidden: the evaluator
gained +70/-2 lines after the promotion commit, so HEAD no longer matches the hash the
signed bundle certifies. The clean value is at the promotion commit
(`git show f80af2f:examples/gsm8k_evaluator.py | sha256sum`).
