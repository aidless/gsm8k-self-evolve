# Fail-Closed Auditable Promotion Gates for Self-Evolving Prompt Policies: A Cross-Model Boundary Result

> **Draft status.** Repository-level reconstruction assembled from verified
> evidence (see `paper/CLAIM_LEDGER.md`, claims C1–C30). Anonymised for
> double-blind review. Every number is recomputable from the artefacts listed
> in Appendix A. Bibliographic details of the arXiv references in §2 are cited
> by identifier only and **must be verified against the primary sources before
> submission**.

## Abstract

Self-improving language-model agents increasingly *select* their own prompts,
tools, or policies by evaluating candidates and keeping the winner. The
evidence that justifies such a promotion is usually reported as a single
accuracy comparison, which makes it impossible to tell a real improvement from
prompt-selection noise. We present a **fail-closed, auditable promotion gate**
for evaluation-gated prompt self-evolution: candidates are promoted only when a
five-key joint condition holds — an exact paired McNemar test on a blind
held-out set that is provably disjoint from the selection set, zero safety
violations, an available rollback, and a cryptographically signed evidence
bundle that binds the exact artefacts evaluated. The gate is deliberately
*self-signed*: it provides integrity and auditability, not third-party
endorsement, and we say so explicitly. We then use the gate as a
measurement instrument and report what it finds. To turn our differentiation
from the self-improvement literature from an *assertion* into a *measurement*,
we ablate the promotion decision itself: on identical permutation-null data the
five-key gate attains a false-promotion rate of 0.0125, versus 0.4125 for a
point-estimate rule and 0.9825 for best-of-8 selection pressure — a comparison
of decision procedures, not of the corresponding systems, which we do not run.
An unpaired test at the same α is indistinguishable from the gate (0.0150), so
the measured protection comes from the significance test itself, not from the
five-key structure.
On standard GSM8K test items, the gate
accepts a genuine large gain (185/200 vs 156/200, exact McNemar
p = 1.08e-06), rejects a negative result, and — the result this paper is
really about — **rejects the claim that the self-evolved policy is better than
standard zero-shot chain-of-thought**. Across four model families the
self-evolved policy shows no detectable difference from zero-shot CoT
(p = 0.80 / 0.50 / 1.00 / 0.50; directions mixed; no equivalence test was run,
so these are non-detections rather than demonstrations of equivalence), and its
original gain over the incumbent does not detectably replicate on any of the
three additional models. The only robust effect we
observe is that CoT-style prompting beats number-only answering. We quantify
run-to-run variance (three repeats; accuracy spread ≤ 0.025; zero
significance-verdict flips) and verify that all questions are official GSM8K
**test** items with zero overlap with the GSM8K **train** split. We argue that
gates which cannot fail — and reports which do not show them failing — are the
actual obstacle to progress in self-improving systems.

## 1. Introduction

Self-improvement loops for language agents are now common: a system proposes a
new prompt, tool description, or control policy; evaluates it; and promotes it
if the score improves. The promotion decision is the scientifically load-bearing
step, and in many reported systems it is a single accuracy number on a single
model, computed once, with no stated mechanism for *rejecting* a candidate
(Fang et al., 2025, survey the evaluation practice of self-evolving agents).

That design has two failure modes. First, when the candidate is only slightly
better, the difference is frequently indistinguishable from evaluation noise;
without a paired significance test, selectors promote noise. Second, even a
correct test is unverifiable after the fact if one cannot reconstruct what was
evaluated, on which items, with which code, and whether the losing candidate
could have been restored.

This paper makes two contributions.

**(1) A fail-closed auditable gate.** We specify and implement a promotion
procedure whose default answer is *no*. Promotion requires a five-key joint
condition (§3.3) combining an exact paired test, blind held-out disjointness,
safety, rollback availability, and a signed artefact-binding bundle, with an
append-only registry recording every transition and an independent verifier that
recomputes the entire chain from repository files rather than trusting cached
claims. A decision-rule ablation (§5.6) isolates the source of this behaviour:
on permutation-null data the gate's false-promotion rate is 0.0125 versus 0.4125
(point estimate) and 0.9825 (best-of-8) — while an unpaired test at the same α
is indistinguishable from the gate, so the differentiation the literature lacks
is a significance test, not this gate's five-key structure.

**(2) A boundary result obtained by using the gate honestly.** We apply the gate
to a concrete system and report the outcome even though it is unflattering: the
policy that the self-evolution loop selected and promoted does **not**
significantly outperform standard zero-shot chain-of-thought, on any of four
model families, and its advantage over the weaker incumbent does not detectably replicate
beyond the model on which the evolution ran. The only robust effect in the data
is that CoT-style prompting substantially beats number-only answering.

We consider the second contribution to be the more useful one. A gate is only
credible if it can reject, and a field learns more from a well-measured boundary
than from another reported improvement.

**Scope.** Our experiments use GSM8K (Cobbe et al., 2021) test items on locally
served 4B–8B models at temperature 0, plus one remote AWQ-INT4-quantised 27B
arm (§5.7). We do not claim state-of-the-art
accuracy, and we do not claim that prompt self-evolution is ineffective: our
claims are comparative and bounded, as stated in §7.

## 2. Related Work

**Self-improving and self-evolving agents.** Self-Refine-style self-critique
(Madaan et al., 2023) and Reflexion (Shinn et al., 2023) improve outputs by iterative verbal feedback
without weight updates. TextGrad (Yuksekgonul et al., 2024; arXiv:2406.07496)
treats textual feedback as a gradient-like signal for optimising prompts and
solutions. REMO (arXiv:2508.18749) and SPHERE (arXiv:2503.04813) report
meta-optimisation and self-evolution of reasoning pipelines, and arXiv:2508.07407
surveys the landscape. Reflections and surveys alike focus on *producing*
improvement; the gate mechanism by which a candidate is accepted or rejected —
paired significance, blind disjointness, signed artefact binding, rollback —
is not their object of study. We therefore take these works as adjacent
context, not as prior art for the gate. §5.6 evaluates idealised
decision procedures — abstract baselines constructed for the comparison, not
re-implementations of those systems — head-to-head on identical
permutation-null data, making the contrast measurable rather than asserted: a
same-corpus ablation in which our
five-key gate (R1) and the decision procedures those works imply (a point
estimate, an unpaired test, a relaxed threshold, and best-of-k selection
pressure) are evaluated head-to-head on identical permutation-null data. The
gate attains a false-promotion rate of 0.0125 versus 0.4125 (point estimate) and
0.9825 (best-of-8), a paired exact McNemar p of 2⁻³¹⁹ on the former comparison.
This is a comparison of **decision procedures**, not of those systems
themselves: we do not run, reproduce, or claim to beat REMO, SPHERE, or
TextGrad (§7).

**Evaluation discipline.** Paired significance testing for classifier-style
comparisons dates to McNemar (1947); we use the exact two-sided binomial form
rather than the χ² approximation because discordant counts are often small.
Preregistration is standard in empirical sciences and increasingly discussed in
machine learning; we preregistered the design of the cross-model study
(§4.3) before running it. Cryptographic signing of experimental artefacts is
routine in supply-chain security (Ed25519; RFC 8032) but uncommon in
self-improvement pipelines; we use it here strictly for tamper-evidence and
attribution, and we do not present it as trust infrastructure.

**Boundary and negative results.** Our headline finding is a boundary result:
a self-evolved prompt policy not exceeding a standard CoT baseline. We note
that the *combination* of (i) a gate that can reject, (ii) an explicit
preregistered decision rule with a no-promotion branch, and (iii) a
cross-model replication attempt is, to our knowledge, unusual in the reported
self-evolution literature, where the typical artefact is a successful run.

## 3. Method: The Fail-Closed Auditable Gate

We describe the gate as a specification; each mechanism is anchored to the
implementation (§Appendix A) and to a verified claim in the claim ledger.

### 3.1 Exact paired testing with a ledger identity

Candidates and incumbents are compared on the **same questions under the same
configuration**, and only discordant pairs are tested:

```
mcnemar_two_sided(b, c) = min(1, 2 · Σ_{i=0..min(b,c)} C(n,i) / 2^n),  n = b + c
```

where `b` counts questions the challenger passes and the incumbent fails, and
`c` the converse. In addition, every promotion and every merge asserts the
**ledger identity**

```
total_challenger − total_incumbent == b − c
```

which ties three independently recorded quantities (two totals and the paired
net gain) together, so that either a miscount or a hand-edit breaks an
assertion rather than passing silently.

### 3.2 Blind held-out disjointness

Selection, validation, and test item sets must be pairwise disjoint by
question identifier. The loop never sees held-out items. Disjointness is
recomputed from the item identifiers at verification time (§3.6), not merely
asserted.

### 3.3 The five-key joint promotion gate

A candidate is promoted from *provisional* to *stable* only if **all five**
keys are true:

| key | condition |
| --- | --- |
| `statistical_passed` | merged blind held-out exact McNemar p < α and gain ≥ ε |
| `hidden_passed` | held-out sets pairwise disjoint from the selection set |
| `safety_passed` | zero safety violations across all runs |
| `rollback_available` | the pre-promotion artefact is archived and restorable |
| `bundle_signature_valid` | the evidence bundle verifies under the pinned key |

In this study's domain the four non-statistical keys are structural:
`hidden_passed` and `safety_passed` encode checks that no run of this benchmark
can fail (held-out disjointness holds by construction; arithmetic word problems
contain no tool actions or safety-relevant behaviour class), and rollback and
signature are enforced by the registry and bundle machinery (§3.5–3.6). The
ablation of §5.6 treats them as constants by construction; the gate's measured
content is the statistical key.

The conjunction is the fail-closed property: any missing or false key yields
no promotion. A registry records the transition with all evidence.

### 3.4 Self-signed evidence bundles (integrity, not endorsement)

On promotion we build a manifest containing the SHA-256 of every artefact
actually evaluated (candidate configuration, evaluator, and each item set),
the held-out statistics, and the disjointness check; we then compute a
canonical-JSON digest and sign it with Ed25519 under the signer name
`agent-self`. We state plainly — in the manifest itself and in our
documentation — that this provides **integrity and auditability, not
independent third-party endorsement**. The private key is never published; only
the public key is committed.

### 3.5 An append-only version registry

Every state transition (`register`, `transition`, and rejection events) is
appended to a registry with its evidence. Rejections are first-class records:
our registry contains an explicit `provisional-rejected` entry, so the history
of what was tried and refused survives alongside the promotions.

### 3.6 Independent re-verification and rollback

A separate verifier, written independently of the promotion script, recomputes
the entire chain from repository files: (1) the bundle digest binds the
manifest; (2) all artefact hashes match the committed files; (3) the merged
paired statistics and the ledger identity are recomputed from per-question
results; (4) item sets are disjoint; (5) the Ed25519 envelope verifies and is
unexpired. The verifier trusts no cached claim. Verification is defined at the promotion
commit: because the evaluator was later extended (Appendix A), the verifier run
at the repository head reports the documented expected artefact-hash mismatch
for that one file, while the promotion-time verification passed all five
checks. Rollback is guaranteed by archiving the pre-promotion artefacts.

## 4. Experimental Setup

### 4.1 Backends

All runs use temperature 0 through a local Ollama endpoint; Ollama exposes no
seed control, which we record as a limitation (§7). The primary backend is
Qwen2.5-7B. The cross-model study (§5.4) additionally uses Gemma3-4B,
Qwen2-7B, and Llama-3.1-8B.

### 4.2 Question sets and provenance

The study uses 240 items in three files: a 40-item selection set (`gsm8k-01`–`40`,
used only for rounds 1–2 candidate selection) and a 200-item blind held-out set
composed of `held-01`–`40` and `held2-001`–`160`. The held-40 subset doubles as
the item set for the round-3 rejection round (§5.2), the cross-model study
(§5.4), the variance study (§5.5) and the proposer-substitution arm (§5.7); it
is disjoint from the selection set and was never used to select candidates. We verify provenance programmatically against the official
GSM8K release: **240/240 items match the GSM8K test split verbatim, 0 items
overlap the GSM8K train split, and their positions are spread across the split**
(mean position 644.7 against a uniform expectation of 659.0; quartiles
344 / 630 / 947; 126 items in the first half and 114 in the second), which
rules out a biased prefix selection. The redistributed question text carries the upstream MIT licence notice, and
the study's own released artefacts (gate implementation, ablation scripts, run
logs, provenance records) will state their licence in the anonymized repository.
Because the items are standard test items,
our comparisons are commensurable with the GSM8K literature; because they are a
240-of-1319 subset, we do not report them as a full-test score (§7). The
redistributed question text is attributed under its MIT licence.

### 4.3 Preregistration

The cross-model design was preregistered before execution: the model list,
the item set, the policy set, the headline comparisons, the gate thresholds,
and an explicit expansion rule (extend to a larger item set only if a headline
pair shows p < 0.2 and |gain| ≥ 0.02). The preregistration also enumerates an
exhaustive three-outcome decision rule for the headline test — accept,
mandatory narrative revision, or inconclusive — and we report which branch we
landed in rather than only the numbers.

## 5. Results

### 5.1 The gate accepts a true gain

Two rounds of prompt-policy evolution on the 40-item selection set produced
`concise-reason` (from `direct`) and then `step-calc` (from `concise-reason`),
each with a significant paired gain at the selection level (20:0, p = 1.9e-06;
and 9:1, p = 0.022). On the **blind** merged 200-item held-out set, `step-calc`
scored 185/200 (0.925) against `concise-reason` at 156/200 (0.780), with
discordant pairs 33:4 and exact McNemar **p = 1.08e-06**; the ledger identity
holds (185 − 156 = 33 − 4 = 29). The five keys were satisfied and the version
transitioned to *stable* with a signed bundle.

### 5.2 The gate rejects a negative result

A subsequent round proposed two challengers against the stable incumbent on
the 40-item held-out subset of the blind set (disjoint from the selection set;
the same items later reused in §5.4–§5.7). Both failed: `reflect-retry` tied 1:1 (p = 1.0) and
was moreover 2.32× slower; `textgrad-prompt` was 2:1 (p = 1.0). Both have
`gate_pass = false`. The registry records an explicit rejection, and the
incumbent remains stable. The gate's default answer held.

### 5.3 The self-evolved policy does not beat zero-shot CoT

We then asked the question the earlier rounds had not: does the promoted policy
beat a *standard* baseline? Round 2 had compared against `direct` (number-only
answering), which turns out to be a weak comparison. On the merged 200-item
blind set at Qwen2.5-7B:

| policy | correct / 200 | row − `step-calc` (b:c = row-only : step-only) |
| --- | --- | --- |
| `direct` | 27 (0.135) | gain −0.785 (b:c 0:157), p ≈ 1.1e-47 |
| `step-calc` (promoted) | 184 (0.920) | — |
| `cot-zero` (zero-shot CoT) | 186 (0.930) | gain +0.010 (b:c 9:7), **p = 0.804** |
| `few-shot` (frozen 4-shot) | 179 (0.895) | gain −0.025 (b:c 14:9), **p = 0.405** |

The gate fails both headline comparisons. This is the preregistered
**inconclusive** branch: no significant advantage, and no significant
disadvantage, relative to standard CoT.

Two provenance notes reconcile these numbers with earlier ones. The promoted
policy's 184/200 here and 185/200 in §5.1 are two independent temperature-0
runs on the same blind set, within the §5.5 spread. The Round-2 headline
"0.125 → 0.925" compared different item sets (a 40-item and the 200-item set)
and must not be read as a same-set effect size; the same-set comparison is
Table 2 (0.135 → 0.920), which supports the same conclusion.

### 5.4 Cross-model validation

*(gain = `step-calc` − the named baseline; positive favours the promoted policy. b:c = discordant pairs.)*

We repeated the comparison on three further model families (40-item blind set).
The self-evolved policy is statistically indistinguishable from zero-shot CoT
on **every** model tested:

| model | `step-calc` vs `cot-zero` | `step-calc` vs `concise-reason` |
| --- | --- | --- |
| Qwen2.5-7B (n=200) | p = 0.804, gain −0.010 (b:c 7:9) | Round 2: p = 1.08e-06, gain +0.145 (b:c 33:4) |
| Gemma3-4B (n=40) | p = 0.500, gain −0.050 (b:c 0:2) | p = 0.453, gain +0.075 (b:c 5:2) |
| Llama3.1-8B (n=40) | p = 0.500, gain −0.050 (b:c 0:2) | p = 1.000, gain +0.025 (b:c 3:2) |
| Qwen2-7B (n=40) | p = 1.000, gain +0.025 (b:c 4:3) | p = 0.688, gain +0.050 (b:c 4:2) |

Two things follow. First, the non-significance of the CoT comparison replicates
across all four models (directions mixed: gains −0.050 to +0.050; discordant
counts are small relative to n — see Table 3). Second, the original gain of the
evolved policy over the weaker incumbent **does not detectably replicate** on
any of the three new models. The only effect that is large and consistent
everywhere is `direct` vs any CoT-style policy: on the 200-item set, exact
p ≤ 3.6e-42 (b:c (3,155)–(0,159); the CoT-style policies lead by 0.760–0.795);
on the three 40-item sets, p ranges from 7.6e-5 to 7.3e-12 (lead 0.425–0.950).
This is the established chain-of-thought effect (Wei et al., 2022; Kojima et
al., 2022) — a baseline sanity check, not a discovery of this paper.

Applying the preregistered expansion rule, no headline pair reached the
weak-signal threshold (all p ≥ 0.45), so the study was not extended — we report
the null rather than spending more compute to re-test it.

### 5.5 Run-to-run variance

All headline numbers above are single runs. To bound this, we repeated the
three headline policies three times on the same 40 items at Qwen2.5-7B (360
generations):

| policy | repeat 1 | repeat 2 | repeat 3 | spread |
| --- | --- | --- | --- | --- |
| `concise-reason` | 0.850 | 0.850 | 0.850 | 0.000 |
| `cot-zero` | 0.950 | 0.950 | 0.950 | 0.000 |
| `step-calc` | 0.900 | 0.925 | 0.925 | 0.025 |

Every significance verdict was stable across repeats (zero flips): the
`step-calc` vs `cot-zero` p-values were 0.625 / 1.00 / 1.00. Single 40-item
numbers should therefore be read within roughly ±0.025–0.05; we also observed a
one-question difference between cloud and local runs of the same model on the
same items, of the same magnitude. We additionally note that an earlier
informal "≈±10%" drift estimate from the first round was **not** reproduced
here; we record both rather than quietly replacing the older figure.

### 5.6 Decision-rule ablation: the gate suppresses false promotions

The results above show the gate *behaving* correctly (accepting a true gain,
rejecting a negative and a null). They do not isolate *which part* of the gate
produces the fail-closed behaviour, nor whether the differentiation from the
self-improvement literature is real rather than asserted. We therefore run a
decision-rule ablation (preregistered, `results/rounds/round5/PREREG-round5.md`):
we re-implement seven idealised promotion **decision procedures** — our
five-key gate (R1), a point-estimate rule (R2, promote iff gain > 0), an
unpaired two-proportion test (R3), the gate's paired test computed on the
non-blind selection set (R4), a relaxed significance threshold (R5, α = 0.20),
the gate with the significance test removed but the magnitude criterion kept
(R6), and best-of-k selection pressure (R7, promote the best of k = 8 candidates
by point estimate) — and evaluate each on the **same** permutation-null data.

Nulls are constructed by, for each discordant item of a real paired pool,
independently swapping the challenger/incumbent labels with probability 0.5
(seed fixed, `SEED = 20260912`), so the true effect is identically zero while
the discordance structure is preserved. Four source pools × 200 nulls give 800
null pools, decided in each pool's own declared `(challenger, incumbent)`
orientation; everything is recomputed by a script from the committed pool
artefact with **zero model calls**.

| rule | semantics (abridged) | false-promotion rate (n = 800) |
| --- | --- | --- |
| R1 `gate` (ours) | five keys: blind paired exact McNemar p < 0.05 **and** gain ≥ 0.02 | **0.0125** (10 / 800) |
| R2 `point` | promote iff gain > 0 (no test) | 0.4125 (330 / 800) |
| R3 `unpaired` | unpaired two-proportion test, p < 0.05 and gain ≥ 0.02 | 0.015 (12 / 800) |
| R5 `loose` | gate with α = 0.20 | 0.04125 (33 / 800) |
| R6 `no-stat` | gate minus the significance test, magnitude criterion kept | 0.27125 (217 / 800) |
| R7 `best-of-8` | promote the point-estimate best of 8 candidates | **0.9825** (786 / 800) |

(R4 is omitted from the table: as a definitional contrast it has no
false-promotion rate; see the caveats below.)

The preregistered verdict device lands in **branch (i), "gate value
established"**: (i) the Wilson 95% intervals are disjoint with R1 below —
WilsonUpper95(R1) = 0.022856 < WilsonLower95(R2) = 0.37888 < WilsonLower95(R7@8) =
0.97084 — and (ii) a paired exact McNemar test on the same 800 nulls, pairing by
(source pool, null index), agrees in the same direction: R1 vs R2 has
discordant counts 0 vs 320, p = 2⁻³¹⁹ ≈ 9.3634e-97; R1 vs R7@8 has 0 vs 776,
p = 2⁻⁷⁷⁵ ≈ 5.0321e-234; the direction is unanimous across all four source
pools. Under best-of-8 selection pressure, the point-estimate rule promotes
nearly every null, while the five-key gate holds its false-promotion rate at
0.0125 — a valid significance test at α = 0.05, not the population of
candidates, is what resists the noise (pairing itself contributes no measurable
protection; see below).

A fourth comparison sharpens the verdict. R1 is **not** significantly better
than R3, another error-controlled rule: the plain *unpaired* two-proportion
test holds 0.0150 (12/800) against R1's 0.0125 (10/800), the Wilson intervals
overlap ([0.00680, 0.02286] vs [0.00860, 0.02603]), and the paired exact
McNemar on the same 800 nulls gives b = 4, c = 6 (p = 0.754): the two rules are
indistinguishable on these nulls. Pairing therefore contributes no measurable
protection. The measurable lever is the test's *size*: R5 (the same gate at
α = 0.20) rises to 0.0413, significantly worse than R1 (b = 0, c = 23,
p ≈ 2.38e-7). The ablation therefore certifies that **having a valid
significance test at α = 0.05** is what suppresses false promotions — not the
five-key conjunction, and not the pairing.

Three caveats bound this result. First, the nulls from one source pool share
that pool's questions, so they are **not independent Bernoulli trials**; the
Wilson interval is a conservative descriptive bound, and the operative check is
the paired McNemar. Second, the true-positive denominator is **one** (a single
positive pool), so TPR = 1/1 for every rule is an anti-vacuity sanity guard
with no discriminating power and must not be read as a TPR ranking. Third,
R4 — the gate's paired test computed on the non-blind selection set — is a
**definitional** contrast, not a finding: R1 refuses all six non-blind
selection-set pools recorded across rounds 1–3 (the pools of §5.1–§5.2 with
`blind = false`) by
construction (it requires the set to be blind), R4 promotes 2/6, and no R4
false-promotion rate is claimed (a non-blind null set does not exist).

### 5.7 Proposer-substitution arm: the verdict does not depend on the proposer

The optional proposer-substitution arm (Task 6 in the round-5 preregistration;
the backbone swap and a first-run invalidation with re-execution are recorded
in a dated amendment, AMENDMENT-2 incl. Revision 1) compares a text-critique
proposer (our own implementation in the style of TextGrad/Reflexion — not
either original system): the zero-shot CoT answer rewritten against a critique
prompt. It is compared against standard zero-shot CoT on the same blind
40-item set, at temperature 0,
two replicates, on Qwen3.8-27B served in AWQ-INT4 quantisation. The five prompt
conditions are `direct`, `step-calc`, `cot-zero`, `few-shot` and the proposer
product; all 400 recorded cells (40 items × 5 conditions × 2 replicates) are
valid, with zero transport failures and per-cell serving latencies of
6.0–366.5 s.

On replicate 1 the proposer product scores 37/40 against 38/40 for zero-shot
CoT (exact McNemar b = 1, c = 2, p = 1.0, gain −0.025): the proposer product
does not beat the standard baseline. The replicates agree: 198 of the 200
item-by-condition pairs return the same verdict in both replicates (the two
disagreements are in `few-shot`, 34 vs 36 passes). The first run was invalidated
after a post-run latency audit found 260 cells with zero recorded latency —
transport failures that the then-current runner had recorded as data; the run
was quarantined, the runner fixed, and the 140 cells that had genuinely reached
the model were re-verified cell-wise and carried over into the re-execution
(the two runs are identical on those cells, as the amendment requires). The only robust ordering remains chain-of-thought-style prompting ≫
number-only answering (3/40 vs 34–38/40). In this single arm, one alternative
proposer and one new-generation backbone leave the gate's conclusion unchanged;
we do not generalize beyond that.

## 6. Discussion

The gate's value is not that it accepts improvements; it is that it refuses.
We observed it refuse in two distinct ways: a negative result (a challenger
that failed significance: §5.2) and a non-improvement (a promoted policy that
failed to beat a standard baseline: §5.3). In both cases the honest default —
no promotion, no claim — required an explicit mechanism, and the mechanism
made the refusal auditable rather than rhetorical.

The cross-model result reframes what prompt-level self-evolution achieved here.
The loop did what it was asked to do: it found a prompt that substantially beat
its incumbent. What it did not do is find a prompt that beats the obvious
baseline a practitioner would use for free. Reporting only the first fact —
which the field's typical artefact format encourages — would have produced a
paper claiming an improvement that the second fact dissolves.

We therefore suggest a minimal reporting standard for promotion decisions in
self-improving systems: state the decision rule; preregister it; include a
standard, non-strawman baseline; show the gate rejecting at least once; and
make the evaluated artefacts and item sets independently recomputable.

A final observation concerns what any gate claim can mean. A gate's claimed
value decomposes into three measurements: *coverage* (does it see every event
it governs?), *error control* (does it decide correctly when the correct answer
is known by construction?), and *benefit* (does the system do better with the
gate than without?). Each requires different evidence — a denominator, a
constructed null, and an ablation with adequate power, respectively — and
conflating them lets implementation invariants be reported as measurements: our
own R4 contrast (§5.6) is definitional in exactly this way. Only error control
is certifiable from data we can construct, and §5.6 certifies it (0.0125 vs
0.4125/0.9825). A companion study applies the same decomposition to approval
gates in multi-agent tool execution and occupies the complementary cells: its
coverage zero is derived and falsifiable but does not discriminate between
mechanisms, its success benefit is undetected, and its error control is not
measurable without ground-truth safety labels (manuscript in preparation).

## 7. Limitations

- **Scope of the negative claim.** "No significant difference" is not proof of
  equivalence. We preregistered no equivalence margin, and n = 40 for three of
  the four models is underpowered for small effects. We therefore claim
  *non-replication* at the tested sample sizes, not *absence*.
- **Subset, not full split.** The evaluation uses 240 of the 1319 GSM8K test
  items. No number in this paper should be read as a full-test GSM8K score, and
  cross-subset comparisons are invalid.
- **Backends.** Locally served 4B–8B instruction models, plus one remote
  AWQ-INT4-quantised 27B arm (§5.7); nothing here licenses
  a claim about frontier models or about transfer to other task families. The
  preregistered transfer study across SVAMP, MultiArith and ASDiv was **not**
  run; we note in particular that its preregistered success rule compared only
  against the number-only baseline, which §5.3 shows to be a strawman, so
  executing it as written would produce an uninformative "success". It must be
  amended (adding a CoT baseline) before it is worth running.
- **Determinism.** Temperature 0 without seed control. We quantified
  run-to-run variance (§5.5) at one model and one item set; the variance study
  is itself three repeats of 40 items, not a distribution.
- **Pretraining contamination.** The backbones' pretraining corpora almost
  certainly include GSM8K test items; "zero overlap with the train split"
  rules out leakage in our own loop, not memorisation by the models.
  Memorisation would push both arms of any comparison toward the same ceiling,
  compressing detectable differences and further lowering power — it biases
  the study toward the nulls we report rather than against them, but it makes
  the absolute success numbers uninterpretable as reasoning ability.
- **Signatures.** Self-signed and integrity-only; the signer is the same agent
  that produced the result. This is an audit mechanism, not a trust boundary.
- **Decision procedures, not systems.** The decision-rule ablation (§5.6)
  compares idealised promotion *decision procedures* — abstract baselines
  constructed for the comparison; no published system is re-implemented, run,
  reproduced or beaten, and the baselines' FPRs are properties of the
  constructed rules, not of REMO, SPHERE, TextGrad, or any other system.
- **Preregistration coverage.** The cross-model study (§5.4), the decision-rule
  ablation (§5.6) and its proposer-substitution arm (§5.7, as amended) were
  preregistered; Rounds 1–3 were not, and are reported as exploratory.
- **Proposer-substitution arm (§5.7).** One backbone (Qwen3.8-27B, AWQ-INT4,
  self-hosted), one item set, one proposer type. A single observation, not a
  cross-backbone trend; it is not numerically comparable to the 4B–8B results in
  §5.4, and AWQ-INT4 quantisation is part of the instrument. The arm's first
  execution was invalidated by an external termination of the serving process
  and re-executed under a budget amendment; the quarantined first-run artefact
  is retained as incident evidence: no aggregate number in this paper comes
  from it, and the 140 cells salvaged from it were re-verified cell-wise and
  reused as documented in the amendment. The earlier partial run on a
  superseded backbone (`qwen2.5:7b`) is likewise not reported.

## 8. Conclusion

We presented a fail-closed, auditable promotion gate for evaluation-gated
prompt self-evolution, and used it to measure rather than to advertise. The
gate accepts a large genuine gain and rejects both a negative result and a
non-improvement. Under that gate, the self-evolved policy does not significantly
beat standard zero-shot chain-of-thought on any of four model families, its
original gain over a weaker incumbent does not replicate, and the only robust
effect is that CoT-style prompting beats number-only answering. A decision-rule
ablation on permutation-null data isolates *why* the gate behaves this way:
its false-promotion rate is 0.0125 against 0.4125 for a point estimate and 0.9825
for best-of-8 selection pressure, so having a valid significance test at α = 0.05
is what resists noise — not the five-key conjunction, and not the pairing (an
unpaired test at the same α is indistinguishable from the gate on these nulls);
blind disjointness is enforced by construction rather than measured. We argue that
self-improvement research needs gates that can say no, and reports that show
them saying it.

## 9. Broader Impact

This paper contributes an evaluation methodology, not a self-improving system:
the released artefacts are the gate implementation, the decision-rule ablation
scripts, run logs and question-provenance records.

*Potential benefits.* A promotion decision that is fail-closed, preregistered
and independently recomputable reduces one specific risk of prompt-level
self-improvement: deploying an update whose claimed gain does not survive a
preregistered comparison against a standard baseline. The error-control
measurement (§5.6) gives practitioners a way to audit a decision rule before
trusting it, and the boundary result (§5.3) shows that audit working against
our own promoted policy.

*Potential risks.* (i) A "gate passed" outcome can be over-read as a general
capability endorsement; the gate certifies only the preregistered comparison
on the preregistered item set — which is why the paper's central result is the
gate *rejecting* our own policy. (ii) The machinery is metric-agnostic and operator-controlled: the same gate
that refuses unsupported claims could approve a genuinely harmful prompt update
if the metric were mis-specified — or, deliberately, an operator who controls
the metric, the gate parameters and the signing key could use the whole
apparatus as a rubber stamp, lending preregistered, signed evidence to updates
it was never meant to certify (a credibility-laundering vector; a signed bundle
certifies process integrity, not content safety or operator intent). The blind
set, the ledger identity and preregistration mitigate but do not eliminate
metric gaming.
(iii) All results are on GSM8K-style arithmetic word problems with 4B–27B open
weights models; nothing here licenses claims about safety-critical domains or
frontier systems. (iv) A fail-closed gate has a structural false-negative cost
that this paper measures only on the looseness side: at n = 40 a genuine small
improvement is routinely refused (§5.4's +0.05 effects at p = 0.5), refused
updates are usually never reported, and field-wide adoption of strict gates
without minimum-power guidance would suppress real improvements. Reporting
standards should require the refused-and-unmeasured cases to be reported
alongside the accepted ones.

*Compute and data.* Measured inference compute is on the order of ten GPU-hours
(a consumer laptop GPU for rounds 1–4 and cross-model runs; one remote 48 GB
GPU for the 27B arm; the compute declaration with per-run latency sums is in
the evidence protocol). No training was performed, all questions are official
GSM8K test items (MIT licence), and no human subjects or newly collected data
are involved.

## Appendix A. Reproducibility

Every claim in this paper maps to a verified entry in the claim ledger
(`paper/CLAIM_LEDGER.md`, C1–C31), which in turn maps to artefacts; an
anonymized repository containing the ledger, the per-question artefacts, the
ablation pools and all scripts accompanies the submission. Principal
entry points:

| purpose | command / artefact |
| --- | --- |
| recompute the signed evidence chain | verifier script (§3.6) |
| recompute the merged 200-item statistics | merge script for the primary track |
| recompute cross-model statistics | per-model result files + summariser |
| recompute run-to-run variance | three repeat files + variance report |
| recompute the decision-rule ablation (§5.6) | `scripts/ablation_gate.py` (zero model calls) + `scripts/audit_gate_rules.py` |
| verify question provenance | provenance script (fetches official GSM8K) |
| gate the released artefact | publish gate (excludes internal dirs, logs, keys) |

Two known caveats are recorded in the repository: the signed bundle binds the
evaluator as it stood at the promotion commit, so the verifier reports an
expected artefact-hash mismatch against the current, additively extended
evaluator (the original prompts' code paths are unchanged); and the evaluator
has since been extended by 70 added and 2 removed lines across two rounds,
documented with the exact pristine hash.

## References

> **Verification note (2026-09-16).** Every entry below was checked against its
> primary source: arXiv abs pages fetched directly (号-题-作者 match), McNemar
> via Crossref DOI metadata, RFC 8032 via the IETF datatracker, both model-card
> URLs fetched and content-checked. **One error found and fixed**: McNemar
> (1947) pages are **153–157**, not 153–160. Checklist item (i) is thereby
> complete; the model cards carry no verifiable publication year on their
> fetched pages, so only an access date is given.

- Cobbe, K., Kosaraju, V., Bavarian, M., Chen, M., Jun, H., Kaiser, L., Plappert, M., Tworek, J., Hilton, J., Nakano, R., Hesse, C., & Schulman, J. (2021). *Training Verifiers to Solve Math Word Problems* (GSM8K). arXiv:2110.14168.
- McNemar, Q. (1947). Note on the sampling error of the difference between correlated proportions or percentages. *Psychometrika* 12(2), 153–157. doi:10.1007/BF02295996.
- Josefsson, S., & Liusvaara, I. (2017). *Edwards-Curve Digital Signature Algorithm (EdDSA)*. RFC 8032, IETF.
- Shinn, N., Cassano, F., Berman, E., Gopinath, A., Narasimhan, K., & Yao, S. (2023). *Reflexion: Language Agents with Verbal Reinforcement Learning*. arXiv:2303.11366.
- Madaan, A., et al. (2023). *Self-Refine: Iterative Refinement with Self-Feedback*. arXiv:2303.17651.
- Yuksekgonul, M., Bianchi, F., Boen, J., Liu, S., Huang, Z., Guestrin, C., & Zou, J. (2024). *TextGrad: Automatic "Differentiation" via Text*. arXiv:2406.07496.
- Wu, C., & Qu, Z. (2025). *Reflection-Enhanced Meta-Optimization Integrating TextGrad-style Prompt Optimization with Memory-Driven Self-Evolution* (REMO). arXiv:2508.18749.
- Singh, J., Chakraborty, T., & Nambi, A. (2025). *Self-Evolved Preference Optimization for Enhancing Mathematical Reasoning in Small Language Models* (SPHERE). arXiv:2503.04813.
- Fang, J., et al. (2025). *A Comprehensive Survey of Self-Evolving AI Agents: A New Paradigm Bridging Foundation Models and Lifelong Agentic Systems*. arXiv:2508.07407.
- Yang, A., et al. (2024). *Qwen2.5 Technical Report*. arXiv:2412.15115.
- Model cards for the cross-model backends: *Gemma 3 (4B-it)* — https://huggingface.co/google/gemma-3-4b-it ; *Llama 3.1 (8B)* — https://github.com/meta-llama/llama-models/blob/main/models/llama3_1/MODEL_CARD.md (both accessed 2026-09-16).
- Wei, J., et al. (2022). *Chain-of-Thought Prompting Elicits Reasoning in Large Language Models*. arXiv:2201.11903.
- Kojima, T., et al. (2022). *Large Language Models are Zero-Shot Reasoners*. arXiv:2205.11916.

> **Pre-submission checklist.** (i) verify every reference above against its
> primary source and complete missing author lists; (ii) finalise the
> anonymisation pass; (iii) convert to the venue template; (iv) re-run the
> verifier and the publish gate on the exact submitted artefact and record the
> hashes in the submission.
