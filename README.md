# GSM8K Self-Evolve: direct → concise-reason → step-calc

Two rounds of evaluation-gated prompt-policy evolution on **standard GSM8K test
items** (240 questions redistributed verbatim from the official test split,
verified disjoint from the GSM8K train split), run on cloud (Qwen2.5:7b via
Ollama, temperature 0), ending in a **stable** `step-calc` policy backed by a
merged 200-question blind held-out set and an Ed25519-signed evidence bundle.
Every number below is recomputable from this repo — run
`python tools/verify_evidence_chain.py`; question provenance is re-verifiable
with `python tools/verify_question_provenance.py`.

## TL;DR (English)

A two-round, **fail-closed** prompt-policy evolution on GSM8K. Round 2's `step-calc`
policy scores **185/200 (0.925)** on a blind held-out set vs **156/200 (0.780)** for
round 1; exact McNemar **p = 1.08e-06**; ledger identity `185−156 = 33−4` holds;
question sets are pairwise disjoint (240/240 verbatim official GSM8K **test** items,
zero overlap with train).

**But the honest headline is narrower, and the repo says so everywhere:** the robust
effect is *CoT-style prompting ≫ number-only answering* (four model families,
p ≈ 1e-9…1e-48). The **self-evolution-specific** gain over standard zero-shot CoT is
**not detected** (`step-calc` 184/200 vs `cot-zero` 186/200, p = 0.80, n=200) and did
not replicate on three further models — an honest null, not proof of equivalence.

Round 5 preregistered an ablation of the promotion **decision rule** on 800 permutation
nulls (zero model calls): the five-key gate's false-positive rate is **0.0125** vs
0.4125 for "promote any positive gain" and 0.9825 for best-of-8 selection pressure
(paired exact McNemar p ≈ 9.4e-97 / 5.0e-234). A self-reflexive correction is reported
alongside: the gate is **not** significantly better than a plain unpaired test
(p = 0.754), so the ablation certifies *having an effective α=0.05 significance test*,
not the five-key structure.

Why this repo is worth reading: **every claim above — including the ones that weaken
the headline — is recomputable from raw files in this repository**
(`tools/verify_evidence_chain.py`, `scripts/audit_gate_rules.py`), with one
deliberately documented FAIL on HEAD explained in place rather than hidden.

```bash
pip install -r requirements.txt
python tools/verify_evidence_chain.py    # 5-check chain; exits 1 on HEAD by design (see below)
python tools/verify_question_provenance.py
python -m pytest -q                      # 117 tests
python scripts/audit_gate_rules.py        # recomputes all 340 round-5 figures from pool rows
python tools/check_publish.py             # publication gate
```

**Paper**: `paper/DRAFT.md` (full anonymised draft), `paper/RESULTS.md`,
`paper/CLAIM_LEDGER.md` (every claim with a `file:line` anchor and a status),
`paper/SELF_ASSESSMENT.md` (TMLR four-dimension self-scoring, 3.45/4).

## Result

| Stage | Policy | Train (40) | Held-out |
|---|---|---|---|
| seed baseline | `direct` (number only) | 0.15 | 0.125 (40 q) |
| round 1 (provisional) | `concise-reason` (≤2 sentences + `Answer:`) | 0.65 | 0.780 (200 q) |
| round 2 (**stable**) | `step-calc` (one arithmetic step per line + `Answer:`) | 0.95 | **0.925 (200 q)** |

Head-to-head on the merged blind held-out (200 q):

- step-calc **185/200 (0.925)** vs concise-reason **156/200 (0.780)**
- paired discordant **better:worse = 33:4**, exact two-sided binomial McNemar **p = 1.08e-06**
- ledger identity holds: 185−156 = 33−4 = 29

Key IDs: stable version `eecacc0312d7` · bundle `step-calc@ad35903f5cb4`
(`sha256 = ad35903f5cb4…f2edbc685d1`).

## Method (what actually happened)

1. **Round 1** — incumbent `direct` vs mutations `{concise-reason, double-check,
   reworded-direct}` on train-40. `concise-reason` won (0.65 vs 0.15,
   McNemar better=20/worse=0, p≈1.9e-06) → provisional.
   `double-check` scored *below* baseline (0.10): a bare "re-check" instruction
   with a number-only output constraint hurts.
2. **Round 2** — incumbent `concise-reason`, mutations `{step-calc,
   rounding-aware, rectify}` (designed against round-1 failure modes:
   merged mental arithmetic, rounding traps, truncated outputs).
   `step-calc` won train 38/40 vs 30/40 (better=9/worse=1, p≈0.022) → provisional.
3. **Blind held-out** — two disjoint batches (40 + 160), both disjoint from
   train and from each other, never touched by the evolve loop. Batch-1 alone
   (better=3/worse=0, p=0.25) was *underpowered*, not negative; batch-2
   (better=30/worse=4, p≈6.2e-06) settled it. Merged p = 1.08e-06.
4. **Stable promotion** — 5 evidence keys re-derived in
   `scripts/promote_to_stable.py`: statistics, hidden-set disjointness,
   zero safety violations, rollback availability, valid bundle signature →
   `step-calc` transitioned provisional → stable in `registry/`.

## Honest semantics (read before citing)

- The bundle signature is **self-signed** (`signer=agent-self`). It gives
  **integrity + auditability** (tamper-evident, key-attributed), **not**
  independent third-party endorsement.
- Held-out batch-2 stores authoritative paired counts (per-question details
  were not persisted for that batch); batch-1 stores full per-question pairs.
  The verifier recomputes batch-1 pairs from scratch and asserts the global
  ledger identity, so a miscount in either batch would break verification.
- 40-question single runs carry ≈±10% noise on this setup (observed baseline
  drift 0.65→0.75 on re-runs). The `min_gain=0.02` gate in `evo.json` is
  therefore meaningful only with the large-sample held-out backstop used here.
- **Question provenance (verified 2026-09-12):** all 240 questions
  (`gsm8k40` + `heldout40` + `heldout-batch2-160`) match the official GSM8K
  **test** split verbatim (240/240) and have **zero** overlap with the GSM8K
  **train** split; their positions are spread across the split, so the subset
  is not a biased prefix. They are standard items, not self-authored — but they
  are a 240-of-1319 **subset**, so do **not** read any number here as a
  "full GSM8K test" score. Re-verify: `tools/verify_question_provenance.py`;
  attribution: `THIRD_PARTY_NOTICES.md`.
- **Run-to-run variance is now quantified** (2026-09-12: 3 repeats / 360 calls,
  qwen2.5:7b on heldout40): per-policy accuracy spread ≤ 0.025 and **zero
  significance-verdict flips across repeats**. Read any single 40-question
  number within ≈±0.025–0.05; the qualitative verdicts are stable. (The older
  ≈±10% estimate from round 1 is not reproduced by this measurement; both are
  recorded in `results/rounds/round4/ROUND4-VARIANCE.md`.)

## Reproduce

```bash
# 1. verify the whole chain (stdlib + cryptography only)
pip install -r requirements.txt
python tools/verify_evidence_chain.py   # expect ALL CHECKS PASSED

# 2. re-run evaluation (needs Ollama + qwen2.5:7b; engine paths are cloud-local)
# single held-out pass, e.g. step-calc on batch-1 (see scripts/run_heldout_round2.py)
```

The evolve loop itself ran under the `evoagent` engine
(auditable, evaluation-gated self-improvement loop), which is **not** part of
this repo; `scripts/run_evolve_round2.py` documents the exact invocation.
`examples/gsm8k_evaluator.py` + `scripts/run_heldout*.py` are self-contained
given an Ollama endpoint (`EVO_OLLAMA_URL`, `EVO_MODEL` env overrides).

## Layout

```
evo.json / seed.json / active.json      evolve config, seed, promoted candidate
examples/                               evaluator (6 policies) + train/held1/held2 sets
scripts/                                evolve / held-out / stable-promotion runners
results/runs/                           full round-1 + round-2 evolve reports
results/heldout-*.json                  blind held-out results (batches 1+2)
results/rollback-before-round2/         round-1 originals (rollback available)
results/history/                        incumbent history snapshots
registry/version-registry.json          provisional → stable transitions with evidence
signed/bundle.json                      manifest + sha256 + held-out evidence
signed/*.envelope.json                  Ed25519 self-signed envelope
signed/agent-self.pub.hex               trusted public key (hex; private key never published)
tools/verify_evidence_chain.py          independent 5-check re-verification
```

## Round 3 — negative result (heldout-40 gate: STOP)

Borrowed-iteration round on branch `round3-borrowed-iteration`: two challengers
(`reflect-retry`, `textgrad-prompt`) vs stable incumbent `step-calc` on a
fresh blind held-out set (n=40, backend qwen2.5:7b). Source of truth:
`results/rounds/round3/heldout40-round3.json` (note: the file is named
`heldout40-round3.json`, not `heldout-40.json`); narrative record:
`results/rounds/round3/NEGATIVE.md`. Incumbent `step-calc` scored 36/40.

| challenger | challenger score | better | worse | exact McNemar p | gain | mean latency ratio | gate_pass |
|---|---|---|---|---|---|---|---|
| reflect-retry | 36/40 | 1 | 1 | 1.0 | 0.0 | 12.207/5.257 = 2.322 | false |
| textgrad-prompt | 37/40 | 2 | 1 | 1.0 | 0.025 | 1.043 | false |

Gate rule: p < 0.05 AND gain >= 0.02 AND latency_ok (ratio <= 2.0) → run
batch2-160 / promote only if merged p < 0.05 with ledger identity holding.
reflect-retry fails gain, significance, and latency independently; textgrad-prompt
passes gain and latency but fails significance (p = 1.0). Both gate_pass = false
→ STOP: no promotion, batch2-160 never contacted, `step-calc` stays stable.
All paired counts above were recomputed from per-question details in
`heldout40-round3.json` (McNemar p = 1.0 for both; ledger holds).

Scope honesty: these n=40 numbers belong to the round-3 held-out set only.
Do not mix them with Round-1/2 scores (train-40; merged 200-q blind held-out
185/200, p = 1.08e-06). Cross-set comparison is invalid.

## Round 4 — true-baseline comparison (inconclusive)

Round 4 (`round4-true-claims`, preregistered in
`results/rounds/round4/PREREG-round4.md`) puts the stable policy `step-calc`
against true baselines on the standard blind held-out set (n=200,
qwen2.5:7b, temperature 0), paired per question:

| policy | correct | p (vs step-calc) | verdict |
|---|---|---|---|
| `direct` | 27 | — | weak strawman baseline |
| `step-calc` | 184 | — | incumbent (Round-2 stable) |
| `cot-zero` | 186 | 0.80 | no significant difference |
| `few-shot` | 179 | 0.40 | no significant difference |

Headline gate (p < 0.05 AND gain ≥ 0.02 AND lat_ratio ≤ 2.0) was **not met**
for either `step-calc` vs `cot-zero` (gain +0.010) or `step-calc` vs
`few-shot` (gain −0.025) → preregistered outcome **(iii) inconclusive**.

**Honest reading:** `step-calc` is statistically indistinguishable from
standard zero-shot CoT here. The 0.125 → 0.925 jump reported in Round 2 is
**mostly the `direct` → CoT-style prompt jump**, not a self-evolution-specific
gain over a standard CoT baseline. `direct` (number-only) was a weak
strawman; `cot-zero` was not included as a control in Round 2.

Boundaries: "no significant difference" is **not** proof of equivalence
(no equivalence margin was preregistered; n=200 is underpowered for
±2-question effects). Full record: `results/rounds/round4/ROUND4-TRACKA-RESULT.md`.

### Round 4 — Track C: cross-model validation

The same gate was then re-run on three further model families (heldout40,
n=40, temperature 0), per `PREREG-round4.md`:

| model (family) | direct | step-calc | concise-reason | cot-zero | few-shot |
|---|---|---|---|---|---|
| qwen2.5:7b (Alibaba) · n=200 | .135 | .920 | — | .930 | .895 |
| gemma3:4b (Google) | .025 | .850 | .775 | **.900** | .450 |
| qwen2:7b (Alibaba) | .050 | .875 | **.925** | .850 | .850 |
| llama3.1:8b (Meta) | .000 | .900 | .875 | **.950** | .700 |

- `step-calc` vs `cot-zero` shows **no significant advantage on any of the four
  models** (p = 0.804 / 0.500 / 1.000 / 0.500).
- The Round-2 self-evolve gain (`step-calc` ≫ `concise-reason`) **did not
  replicate** on any of the three new models (p ≥ 0.45, inconsistent sign).
- The only robust effect is **CoT-style prompting ≫ number-only (`direct`)**
  (p ≈ 1e-9…1e-48, gain +0.70…+0.95 across all four models).

Boundaries: n=40 for the three new models is underpowered; "not replicated" ≠
"proven absent"; the qwen2.5:7b row is a different (n=200) set and must not be
compared across sets for significance. Full record:
`results/rounds/round4/ROUND4-TRACKC-RESULT.md`.

### Round 4 — Track B: transfer to new datasets (data axis)

The frozen `step-calc` vs `direct` was also paired over three external
arithmetic word-problem sets (runtime-fetched, never vendored; qwen2.5:7b,
temperature 0), per `PREREG-round4.md`:

| dataset | direct | step-calc | McNemar p | gain |
|---|---|---|---|---|
| SVAMP (1000) | 647 | 920 | 2.8e-65 | +0.273 |
| MultiArith (180) | 87 | 180 | 2.0e-28 | +0.517 |
| ASDiv (2249) | 1589 | 2026 | 1.2e-84 | +0.194 |

The preregistered generalization rule fired (SVAMP `p < 0.05` AND `gain > 0`
on all three sets). **Honest reading:** this is `direct` (the number-only
trivial baseline) once again, not standard CoT — it confirms the robust
effect "CoT-style ≫ number-only generalizes across datasets" and adds
nothing to the Track A null (`step-calc` ≈ `cot-zero`, p = 0.80). ASDiv:
56 non-numeric-answer rows excluded at fetch (disclosed in
`inputs/asdiv.exclusions.json`; inputs never committed — ASDiv is
CC-BY-NC-4.0, MultiArith license unclear). Full record:
`results/rounds/round4/TRANSFER_RECORD.md`.

## Round 5 — decision-rule ablation: where does the gate's power come from?

Round 4's honest null (`step-calc` ≈ `cot-zero`) left one claim unverified: *why* does
this gate reject false gains? Round 5 preregisters
(`results/rounds/round5/PREREG-round5.md`, frozen before any run) an ablation of the
**promotion decision procedure itself**, measured on the same null pool for every rule.

**The null**: for a real paired pool's `d` discordant questions, flip each
challenger/incumbent label independently with probability 0.5. The true treatment effect
is then identically 0 while the discordance structure is preserved. `SEED=20260912`,
4 source pools × 200 nulls = **800 null pools**, **zero model calls**.

| rule | what it decides | false-positive rate (800 null pools) | Wilson 95% |
|---|---|---|---|
| **R1 `gate`** | **this repo's five-key gate** (blind, paired exact McNemar p<0.05 **and** gain ≥ 0.02) | **10 / 800 = 0.0125** | [0.0068, 0.0229] |
| R3 `unpaired` | two-proportion test p<0.05 **and** gain ≥ 0.02 | 12 / 800 = 0.0150 | [0.0086, 0.0260] |
| R5 `loose` | R1 with α = 0.20 | 33 / 800 = 0.04125 | [0.0295, 0.0574] |
| R6 `no-stat` | gain ≥ 0.02, significance test removed | 217 / 800 = 0.27125 | [0.2416, 0.3031] |
| R2 `point` | gain > 0, no test at all | 330 / 800 = 0.4125 | [0.3789, 0.4470] |
| **R7 `bestofk`** | k=8 candidates, promote the best by point estimate | **786 / 800 = 0.9825** | [0.9708, 0.9896] |

Preregistered verdict branch **(i) — "gate value established"**: the Wilson intervals of
R1 and R2/R7 do not overlap with R1 below, and on the *same* 800 null pools the paired
exact McNemar agrees in direction — R1 vs R2 **b=0, c=320, p ≈ 9.4e-97**; R1 vs R7@8
**b=0, c=776, p ≈ 5.0e-234**. Every per-pool promote bit is committed in
`results/rounds/round5/decisions.jsonl`, so a third party can recount `b`/`c` directly
without rerunning the pipeline.

### The self-reflexive correction (do not skip this)

**R1 is *not* significantly better than R3**, which also controls error but uses an
*unpaired* test: 10/800 vs 12/800, overlapping intervals, paired exact McNemar
**b=4, c=6, p = 0.754 — indistinguishable**. The measurable lever is **the α of the
significance test**: R5 (α=0.20) is 3× worse than R1 (b=0, c=23, p ≈ 2.4e-07).

> So the ablation certifies **"there is an effective significance test at α=0.05"** —
> *not* the five-key conjunction, and *not* the pairing. Error control is a property of
> the decision rule (including its test), not of the gate existing.

### Honest boundaries (disclosed with every report of these numbers)

1. **Nulls come from relabelling, not independent sampling.** A source pool's 200 nulls
   share that pool's questions; Wilson intervals are a conservative descriptive bound.
   The operative claim rests on the paired McNemar, not on the Wilson overlap.
2. **R4 is a definitional control, not a finding.** On the six non-blind selection-set
   pools, R1 refuses all six *by definition* (it requires `blind=True`); R4 promotes 2/6.
   Denominator 6. **No R4 false-positive rate is claimed** — there is no non-blind null
   set, and none is invented.
3. **TPR denominator = 1.** Only one positive pool exists (`cot-zero` vs `direct`), so
   every rule scores 1/1. That clause is a non-vacuity guard with **no discriminating
   power**; it must not be cited as R1 beating R2/R7 on true positives.
4. **The comparison is between decision *procedures*, not systems.** R1–R7 are idealised
   re-implementations of procedures described in public work; **no such system is run,
   reproduced, or beaten here**.
5. R2's expected FPR is `(1 − P(tie))/2 = 0.4364` **by construction** — that is what
   "no error control" means — never reported as a discovery.

Audit: `python scripts/audit_gate_rules.py` recomputes all 340 figures from the pool rows
(never from `ablation.json`) and exits non-zero on any drift; a deliberate one-bit tamper
was used to prove the audit is not vacuous. Rerunning `scripts/ablation_gate.py` leaves
`ablation.json` byte-identical.

## Round 5 — proposer substitution: a null arm

Would the conclusion survive a different proposer? The TextGrad/Reflexion-shaped
propositional artifact was run head-to-head with four other policies on the blind
held-out-40, backend Qwen3.8-27B-AWQ (self-hosted vLLM), 400 valid cells.

Headline (`textgrad` as challenger, `cot-zero` as incumbent): **b=1, c=2, exact McNemar
p = 1.0, gain = −0.025** — the artifact does not beat standard zero-shot CoT.

**This arm was rescoped as a NULL arm (2026-10-01).** The prompt body actually injected
turned out to be, byte for byte, `scripts/textgrad_rewrite.py:BASE_PROMPT` plus a newline
— the first line is provenance metadata, not directional guidance. So the arm supports
only *"a semantically empty artifact does not beat the incumbent"* — a control sanity
check. **It must not be reported as "textual-gradient guidance does not work."** It does
not carry the Round 5 novelty claim, which rests on the decision-rule ablation.

The first run was invalidated and quarantined on record: the serving process was
SIGTERMed by an external party at call 140/400 and the old runner mis-recorded 260
transport failures as data. The runner was fixed (transport failure ≠ data, resume with
retry, circuit breaker, attempts accounting), the budget was amended to dual limits
(≤400 valid cells, ≤800 attempts), and run 2 passed all acceptance gates: valid=400,
failed=0, all latencies > 0, 198/200 (question × policy) pairs judged identically across
repeats.

Boundaries: single backbone (so this is one observation on a new-generation model, not a
claim across models — and 27B vs the 7B/4B/8B runs confounds generation with scale);
AWQ-INT4 quantization is part of the instrument; a `qwen2.5:7b` partial run halted by
platform policy (263/400) is **not citable** and is retained only as an audit trace.

## What to believe, in one paragraph

The recomputable claim of this repo is **narrower than the round-2 headline**: the
robust effect is *CoT-style prompting ≫ number-only answering* (reproduced across four
model families, p ≈ 1e-9…1e-48); the **self-evolution-specific** gain over standard zero-shot
CoT is **not detected** (p = 0.80, n=200; not replicated on three further models), which is
an honest null, not a proof of equivalence; and the round-5 ablation locates the gate's
rejecting power in *having a significance test at α=0.05*, not in the five-key structure.
The value of this repo is that every one of those statements — including the ones that
weaken the headline — is recomputable from raw files in this repository.

## Known honest FAIL on HEAD

`python tools/verify_evidence_chain.py` exits 1 on the current HEAD by design:
`PASS [1/5] bundle.sha256 == sha256(canonical manifest)` then
`FAIL: artifact hash mismatch for gsm8k_evaluator.py`. The evaluator gained +70/−2 lines
after the promotion commit, so HEAD no longer matches the hash the bundle certifies.
The documented clean value is the one at the promotion commit:

```bash
git show f80af2f:examples/gsm8k_evaluator.py | sha256sum
# 4a23f69463293b380bfd7a52be5f9e616af3d02f6e822f7be721b95015eb400e  (matches the bundle)
```

Third-party verification should check out the promotion commit, or wait for the evaluator
to be re-versioned and the bundle re-signed. See `FINAL_ACCEPTANCE.md`, `PHASE_LOG.md`,
and claim C7 in `paper/CLAIM_LEDGER.md`.

## License

MIT — see `LICENSE`.
