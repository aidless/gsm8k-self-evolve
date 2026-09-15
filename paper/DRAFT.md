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
point-estimate rule and 0.9825 for best-of-8 selection pressure (paired exact
McNemar p = 2⁻³¹⁹ between the gate and the point estimate) — a comparison of
decision procedures, not of the corresponding systems, which we do not run.
On standard GSM8K test items, the gate
accepts a genuine large gain (185/200 vs 156/200, exact McNemar
p = 1.08e-06), rejects a negative result, and — the result this paper is
really about — **rejects the claim that the self-evolved policy is better than
standard zero-shot chain-of-thought**. Across four model families the
self-evolved policy is statistically indistinguishable from zero-shot CoT
(p = 0.80 / 0.50 / 1.00 / 0.50), and its original gain over the incumbent does
not replicate on any of the three additional models. The only robust effect we
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
step, and in most reported systems it is a single accuracy number on a single
model, computed once, with no stated mechanism for *rejecting* a candidate.

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
(point estimate) and 0.9825 (best-of-8), establishing the differentiation from
the self-improvement literature as a measurement rather than an assertion.

**(2) A boundary result obtained by using the gate honestly.** We apply the gate
to a concrete system and report the outcome even though it is unflattering: the
policy that the self-evolution loop selected and promoted does **not**
significantly outperform standard zero-shot chain-of-thought, on any of four
model families, and its advantage over the weaker incumbent does not replicate
beyond the model on which the evolution ran. The only robust effect in the data
is that CoT-style prompting substantially beats number-only answering.

We consider the second contribution to be the more useful one. A gate is only
credible if it can reject, and a field learns more from a well-measured boundary
than from another reported improvement.

**Scope.** Our experiments use GSM8K (Cobbe et al., 2021) test items on locally
served 4B–8B models at temperature 0. We do not claim state-of-the-art
accuracy, and we do not claim that prompt self-evolution is ineffective: our
claims are comparative and bounded, as stated in §7.

## 2. Related Work

**Self-improving and self-evolving agents.** Self-Refine-style self-critique
and Reflexion (Shinn et al., 2023) improve outputs by iterative verbal feedback
without weight updates. TextGrad (Yuksekgonul et al., 2024; arXiv:2406.07496)
treats textual feedback as a gradient-like signal for optimising prompts and
solutions. REMO (arXiv:2508.18749) and SPHERE (arXiv:2503.04813) report
meta-optimisation and self-evolution of reasoning pipelines, and arXiv:2508.07407
surveys the landscape. Reflections and surveys alike focus on *producing*
improvement; the gate mechanism by which a candidate is accepted or rejected —
paired significance, blind disjointness, signed artefact binding, rollback —
is not their object of study. We therefore take these works as adjacent
context, not as prior art for the gate. Where earlier drafts had to note that
this differentiation was **an argument rather than an experimentally
established contrast**, we now make the contrast measurable rather than
asserted: §5.6 reports a same-corpus decision-rule ablation in which our
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
unexpired. The verifier trusts no cached claim. Rollback is guaranteed by
archiving the pre-promotion artefacts.

## 4. Experimental Setup

### 4.1 Backends

All runs use temperature 0 through a local Ollama endpoint; Ollama exposes no
seed control, which we record as a limitation (§7). The primary backend is
Qwen2.5-7B. The cross-model study (§5.4) additionally uses Gemma3-4B,
Qwen2-7B, and Llama-3.1-8B.

### 4.2 Question sets and provenance

The study uses 240 items: a 40-item selection set and a 200-item blind held-out
set (40 + 160). We verify provenance programmatically against the official
GSM8K release: **240/240 items match the GSM8K test split verbatim, 0 items
overlap the GSM8K train split, and their positions are spread across the split**
(mean position 644.7 against a uniform expectation of 659.0; quartiles
344 / 630 / 947; 126 items in the first half and 114 in the second), which
rules out a biased prefix selection. Because the items are standard test items,
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

A subsequent round proposed two challengers against the stable incumbent on a
fresh 40-item blind set. Both failed: `reflect-retry` tied 1:1 (p = 1.0) and
was moreover 2.32× slower; `textgrad-prompt` was 2:1 (p = 1.0). Both have
`gate_pass = false`. The registry records an explicit rejection, and the
incumbent remains stable. The gate's default answer held.

### 5.3 The self-evolved policy does not beat zero-shot CoT

We then asked the question the earlier rounds had not: does the promoted policy
beat a *standard* baseline? Round 2 had compared against `direct` (number-only
answering), which turns out to be a weak comparison. On the merged 200-item
blind set at Qwen2.5-7B:

| policy | correct / 200 | vs `step-calc` |
| --- | --- | --- |
| `direct` | 27 (0.135) | gain +0.785, p ≈ 1.1e-47 |
| `step-calc` (promoted) | 184 (0.920) | — |
| `cot-zero` (zero-shot CoT) | 186 (0.930) | gain +0.010, **p = 0.804** |
| `few-shot` (frozen 4-shot) | 179 (0.895) | gain −0.025, **p = 0.405** |

The gate fails both headline comparisons. This is the preregistered
**inconclusive** branch: no significant advantage, and no significant
disadvantage, relative to standard CoT. The substantive reading is that the
headline "0.125 → 0.925" improvement of Round 2 is mostly the jump from
number-only answering to CoT-style prompting, not a distinct contribution of
the evolution mechanism.

### 5.4 Cross-model validation

We repeated the comparison on three further model families (40-item blind set).
The self-evolved policy is statistically indistinguishable from zero-shot CoT
on **every** model tested:

| model | `step-calc` vs `cot-zero` | `step-calc` vs `concise-reason` |
| --- | --- | --- |
| Qwen2.5-7B (n=200) | p = 0.804, gain +0.010 | (Round 2: p = 1.08e-06, gain +0.145) |
| Gemma3-4B (n=40) | p = 0.500, gain +0.050 | p = 0.453, gain −0.075 |
| Qwen2-7B (n=40) | p = 1.000, gain −0.025 | p = 0.688, gain +0.050 |
| Llama-3.1-8B (n=40) | p = 0.500, gain +0.050 | p = 1.000, gain −0.025 |

Two things follow. First, the null comparison against CoT replicates in
direction and significance across all four models. Second, the original gain of
the evolved policy over the weaker incumbent **does not replicate** on any of
the three new models. The only effect that is large and consistent everywhere
is `direct` vs any CoT-style policy (p ≈ 1e-9 to 1e-48; gain +0.70 to +0.95).

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

The preregistered verdict device lands in **branch (i), "gate value
established"**: (i) the Wilson 95% intervals are disjoint with R1 below —
WilsonUpper95(R1) = 0.022856 < WilsonLower95(R2) = 0.37888 < WilsonLower95(R7@8) =
0.97084 — and (ii) a paired exact McNemar test on the same 800 nulls, pairing by
(source pool, null index), agrees in the same direction: R1 vs R2 has
discordant counts 0 vs 320, p = 2⁻³¹⁹ ≈ 9.3634e-97; R1 vs R7@8 has 0 vs 776,
p = 2⁻⁷⁷⁵ ≈ 5.0321e-234; the direction is unanimous across all four source
pools. Under best-of-8 selection pressure, the point-estimate rule promotes
nearly every null, while the five-key gate holds its false-promotion rate at
0.0125 — the paired significance test, not the population of candidates, is
what resists the noise.

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
**definitional** contrast, not a finding: R1 refuses all six non-blind sets by
construction (it requires the set to be blind), R4 promotes 2/6, and no R4
false-promotion rate is claimed (a non-blind null set does not exist).

### 5.7 Proposer-substitution arm: the verdict does not depend on the proposer

To test whether the gate's refusal behaviour is an artefact of a specific
proposer, we ran the optional proposer-substitution arm (Task 6 in the
preregistration; the backbone swap is recorded as a dated amendment,
AMENDMENT-2). A text-critique proposer (TextGrad/Reflexion-style) rewrites the
zero-shot CoT answer against a critique prompt, and its product is compared
against standard zero-shot CoT on the same blind held-out set, at temperature 0,
with two replicates.

On a new-generation backbone — Qwen3.8-27B served in AWQ-INT4 quantisation,
400 calls (40 items × 5 policies × 2 replicates) — the proposer product scores
13/40 against 14/40 for zero-shot CoT (exact McNemar b = 0, c = 1, p = 1.0,
gain −0.025): the proposer product does not beat the standard baseline. Across
the two replicates, 198 of 200 cells agree and the headline comparison is
identical in both. The only robust ordering remains chain-of-thought-style
prompting ≫ number-only answering (1/40 vs 12–14/40). We read this as
proposer-agnostic behaviour: the gate's conclusion survives a change of proposer
and of backbone generation, within the limits stated in §7.

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
0.4125/0.9825). A companion study applies the same decomposition to an approval
gate in multi-agent tool execution and occupies the complementary cells: its
coverage holds by construction over a thin event base, its benefit is undetected
at low power, and its error control is not measurable without ground-truth
safety labels (manuscript in preparation).

## 7. Limitations

- **Scope of the negative claim.** "No significant difference" is not proof of
  equivalence. We preregistered no equivalence margin, and n = 40 for three of
  the four models is underpowered for small effects. We therefore claim
  *non-replication* at the tested sample sizes, not *absence*.
- **Subset, not full split.** The evaluation uses 240 of the 1319 GSM8K test
  items. No number in this paper should be read as a full-test GSM8K score, and
  cross-subset comparisons are invalid.
- **Backends.** Locally served 4B–8B instruction models; nothing here licenses
  a claim about frontier models or about transfer to other task families. The
  preregistered transfer study across SVAMP, MultiArith and ASDiv was **not**
  run; we note in particular that its preregistered success rule compared only
  against the number-only baseline, which §5.3 shows to be a strawman, so
  executing it as written would produce an uninformative "success". It must be
  amended (adding a CoT baseline) before it is worth running.
- **Determinism.** Temperature 0 without seed control. We quantified
  run-to-run variance (§5.5) at one model and one item set; the variance study
  is itself three repeats of 40 items, not a distribution.
- **Signatures.** Self-signed and integrity-only; the signer is the same agent
  that produced the result. This is an audit mechanism, not a trust boundary.
- **Decision procedures, not systems.** The decision-rule ablation (§5.6)
  compares idealised promotion *decision procedures* re-implemented from the
  public descriptions of prior self-improvement work; it does not run, and we do
  not claim to reproduce or beat, REMO, SPHERE, TextGrad, or any other system.
- **Preregistration coverage.** Only the cross-model study (§5.4) and the
  decision-rule ablation (§5.6) were preregistered; Rounds 1–3 were not, and are
  reported as exploratory.
- **Proposer-substitution arm (§5.7).** One backbone (Qwen3.8-27B, AWQ-INT4,
  self-hosted), one item set, one proposer type. A single observation, not a
  cross-backbone trend; it is not numerically comparable to the 4B–8B results in
  §5.4, and AWQ-INT4 quantisation is part of the instrument. The earlier partial
  run on a superseded backbone is not reported.

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
for best-of-8 selection pressure, so the paired significance test — combined
with blind disjointness — is what resists noise, not the population of
candidates. We argue that
self-improvement research needs gates that can say no, and reports that show
them saying it.

## Appendix A. Reproducibility

Every claim in this paper maps to a verified entry in the claim ledger
(`paper/CLAIM_LEDGER.md`, C1–C30), which in turn maps to artefacts. Principal
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

- Cobbe, K., et al. (2021). *Training Verifiers to Solve Math Word Problems* (GSM8K). arXiv:2110.14168.
- McNemar, Q. (1947). Note on the sampling error of the difference between correlated proportions or percentages. *Psychometrika* 12(2), 153–160.
- Josefsson, S., & Liusvaara, I. (2017). *Edwards-Curve Digital Signature Algorithm (Ed25519)*. RFC 8032.
- Shinn, N., et al. (2023). *Reflexion: Language Agents with Verbal Reinforcement Learning*. arXiv:2303.11366.
- Yuksekgonul, M., et al. (2024). *TextGrad: Automatic Differentiation via Text*. arXiv:2406.07496.
- *REMO: meta-optimisation / self-evolution of reasoning pipelines.* arXiv:2508.18749v1.
- *SPHERE: self-evolving reasoning methods.* arXiv:2503.04813v1.
- *Survey of self-evolution / self-improvement.* arXiv:2508.07407v2.
- Qwen2.5 technical report (model family used as the primary backend).
- Gemma 3, Llama 3.1: model cards for the cross-model backends.

> **Pre-submission checklist.** (i) verify every reference above against its
> primary source and complete missing author lists; (ii) finalise the
> anonymisation pass; (iii) convert to the venue template; (iv) re-run the
> verifier and the publish gate on the exact submitted artefact and record the
> hashes in the submission.
