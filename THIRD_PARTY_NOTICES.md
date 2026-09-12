# Third-party notices (Round-3 borrowed iteration)

Borrowed code is vendored under `third_party/<project>/` with its upstream
LICENSE file intact, per each license's redistribution condition.
Ideas-only sources (no code copied) are marked as such.

| Project | License | Used as | Code copied? |
|---|---|---|---|
| noahshinn/reflexion | MIT | verbal self-reflection retry loop (`reflect-retry`) | yes, adapted, see `third_party/reflexion/` |
| zou-group/textgrad | MIT | textual-gradient prompt rewrite (`textgrad-prompt`) | concept + minimal reimplementation, see `third_party/textgrad/NOTICE` |
| stanfordnlp/dspy | MIT | GEPA-style reflective candidate proposal (stretch) | only if Task 9 runs |
| NousResearch/hermes-agent-self-evolution | NOASSERTION (no LICENSE file) | gate-design ideas only | **no — ideas only, zero code** |

## Datasets redistributed in this repository

| Dataset | License | Used as | Attribution |
|---|---|---|---|
| openai/grade-school-math (GSM8K) | MIT | 240 questions redistributed verbatim under `examples/{gsm8k40,heldout40,heldout-batch2-160}.json` (test split) | Copyright (c) 2021 OpenAI — MIT License; upstream `LICENSE` applies to the redistributed question text |

Provenance of the redistributed items is verified and reproducible by
`python3 tools/verify_question_provenance.py` (240/240 match the official GSM8K
**test** split; 0 overlap with the GSM8K **train** split; spread across the
split, no positional clustering). Record: `results/rounds/round4/QUESTION_PROVENANCE.json`.
The MIT condition (retain the copyright notice) is satisfied by this section;
the full upstream license text is at
<https://github.com/openai/grade-school-math/blob/master/LICENSE>.
