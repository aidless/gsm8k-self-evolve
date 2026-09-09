# gsm8k-self-evolve

Self-evolving agent strategy, from prompt to proof: a two-round autonomous strategy evolution on GSM8K-style math word problems, verified on a blind held-out set.

## Evolution chain

```
direct (0.15) ──round 1──> concise-reason ──round 2──> step-calc = STABLE
```

| Stage | Strategy | Held-out score | Evidence |
|---|---|---|---|
| baseline | `direct` | 0.125 (5/40) | `results/heldout-result.json` |
| round 1 | `concise-reason` | 0.780 (156/200) | `results/heldout-result.json` + batch files |
| round 2 | **`step-calc`** | **0.925 (185/200)** | `results/heldout-round2-result.json` + `results/heldout-batch2-result.json` |

## Headline result

Merged blind held-out, **200 questions**, paired comparison:

- concise-reason: 156/200 (0.780)
- **step-calc: 185/200 (0.925)**
- paired better:worse = **33:4**, exact two-sided binomial McNemar **p = 1.08e-06**
- ledger identity holds: `185 − 156 = 33 − 4`
- train / held-out-1 / held-out-2 question sets are pairwise disjoint (40 / 40 / 160)

## What is step-calc?

The evolved strategy forces **one arithmetic step per line** (explicit intermediate calculations instead of merged mental math). It generalizes: the effect replicated on held-out questions the evolution loop never saw, with an 8.25:1 paired win ratio.

## Verify everything yourself

```bash
python3 verify_evidence.py
```

This recomputes, from the raw files in this repo (no trust in any summary):

1. SHA-256 of all 5 signed artifacts (candidate + evaluator + 3 datasets)
2. canonical manifest digest == recorded `bundle.sha256`
3. Ed25519 signature over the envelope (same `canonical_payload` spec as the signer)
4. merged 200-question exact McNemar from per-question outcomes + ledger identity
5. pairwise disjointness of the three question sets

Requires only Python 3 + `cryptography` (`pip install cryptography`).

## Honest scope notes

- The promotion signature is **self-signed** (`signer=agent-self`). It gives you **integrity + auditability** (tamper-evident, key-attributed), **not** independent third-party endorsement. It is recorded as such in the bundle (`signer_note`).
- Small-sample lesson from this run: round-2 batch 1 (40 questions) showed better=3/worse=0, p=0.25 — *not significant*. Same effect at 160 questions: better=30/worse=4, p=6.2e-06. **A non-significant small sample is not evidence of no effect**; expand before judging.
- Rollback material for round 1 is preserved under `.evo/before-round2/`.

## Layout

```
.evo/active.json              # stable strategy definition (step-calc prompt)
.evo/version-registry.json    # provisional -> stable transition + 5 evidence keys
.evo/bundle.json              # signed manifest (hashes + stats + disjoint check)
.evo/signed-bundles/          # Ed25519 envelope (self-signed, expires 2027-09-08)
.evo/trusted-keys/agent-self.pub  # raw 32-byte Ed25519 public key (NO private key)
.evo/runs/ .evo/history/      # both evolution rounds, machine-readable
.evo/before-round2/           # round-1 rollback snapshot
examples/                     # evaluator + train(40) + heldout1(40) + heldout2(160)
results/                      # raw per-question outcomes, both batches
scripts/                      # round runners, held-out runners, promote script
verify_evidence.py            # independent end-to-end verifier
```
