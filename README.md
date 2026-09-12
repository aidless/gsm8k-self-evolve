# GSM8K Self-Evolve: direct → concise-reason → step-calc

Two rounds of evaluation-gated prompt-policy evolution on **standard GSM8K test
items** (240 questions redistributed verbatim from the official test split,
verified disjoint from the GSM8K train split), run on cloud (Qwen2.5:7b via
Ollama, temperature 0), ending in a **stable** `step-calc` policy backed by a
merged 200-question blind held-out set and an Ed25519-signed evidence bundle.
Every number below is recomputable from this repo — run
`python tools/verify_evidence_chain.py`; question provenance is re-verifiable
with `python tools/verify_question_provenance.py`.

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
- **All headline numbers are single runs** (temperature 0, no seed control):
  run-to-run variance is **not quantified**. Large effects (p≈1e-6) are
  unaffected; precise magnitudes are not claimed.

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

## License

MIT — see `LICENSE`.
