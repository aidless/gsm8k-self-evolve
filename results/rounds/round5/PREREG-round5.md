# PREREG Round-5 — gate decision-rule ablation (novelty head-to-head)

- **Date:** 2026-09-12
- **Status:** preregistered, no ablation executed yet
- **Frozen-before-run statement:** this file is frozen before any run — it is committed first, and nothing in the ablation (Tasks 1–5, optional Task 6) is executed until that commit exists.

Any deviation from this document must be disclosed as a dated **revision declaration** at the top of `results/rounds/round5/ROUND5-RESULT.md` before the deviating analysis is reported. Silent deviation is prohibited.

---

## AMENDMENT 1 (2026-09-12, before any deliverable run)

**Subject: R6 `no-stat` semantics — disambiguation of an ambiguous pre-registered wording.**

The original pre-registered wording of R6 was: *the gate with the `statistical_passed` key **removed** (the other four keys kept)*. That wording admits two readings, and they are not equivalent:

| Reading | Semantics | Consequence on the NULL pools |
| --- | --- | --- |
| **(i)** literal | Drop the whole statistical criterion: promote whenever the four remaining keys hold. | The four remaining keys (`hidden_passed`, `safety_passed`, `rollback_available`, `bundle_signature_valid`) are **structural constants** — pool construction of this study sets them true — so every NULL pool would be promoted and null FPR would be **1.0**. R6 would degenerate into a constant-true rule with no discriminative content. The measured pilot FPR for R6 is 0.320, so the literal reading also contradicts the pilot. |
| **(ii)** intended | Keep the gate's **effect-size threshold** `gain >= eps`, `eps = 0.02`, and drop **only** the significance test. | R6 stays a magnitude-only promotion rule; the measured pilot FPR for R6 is **0.320**. |

**Reading (ii) is adopted.** Reasons, in order of weight:

1. **Reading (i) is degenerate on this document's own definitions.** On synthetic pools the four non-statistical keys are not evidence, they are constants. A rule that promotes every pool cannot be contrasted with R2 or R7, so the pre-registered ablation would be vacuous at the R6 column. The scientific question this document pre-registers — *does adding a significance test on top of a magnitude criterion buy error control?* — exists only under reading (ii).
2. **The pilot corroborates (ii).** The design-validation pilot records R6 null FPR = 0.320, inconsistent with the 1.0 that reading (i) forces, and equal to R2's 0.320 exactly as expected at `d = 6` (see §2.2). This is corroboration, not the primary grounds: per §7.1 (controller ruling 10) those pilot figures are **superseded and not citable**, and they are not recomputable from any committed artefact.
3. **Nothing else changes.** R1, R2, R3, R4, R5 and R7 are unaffected by this amendment; only the R6 column of the ablation is defined by it.

This amendment is made **before any deliverable run** (status above: no deliverable ablation has been executed). §7 documents a design-validation **pilot** that had already run during plan design: that pilot is pilot evidence only, it is **not** a deliverable run, and under §7.1 (controller ruling 10) its figures are superseded and not citable — so the freeze order stated here is intact. §2's rule table and §2.2 now state the adopted semantics, so the rule list is self-consistent and the superseded phrasing is not left standing. `paper/PLAN-NOVELTY.md` carries a matching correction and points back to this amendment.

---

## 1. Zero-effect construction (core)

Given a real paired pool's discordant item set `D` (`|D| = d > 0`), independently relabel each of the `d` items (swap challenger/incumbent) with probability 0.5; all other (concordant) items are left unchanged. Under this relabelling the true treatment effect is identically 0 while the discordant total stays `d`. **K = 200** permutation-null pools per real pool, drawn from the pinned randomness below.

**Pinned randomness (binding — no retuning after this freeze).** The construction is fully determined by the following five rules, and Task 1 must implement exactly them:

1. **Literal seed:** `SEED = 20260912` (the date of this freeze, `YYYYMMDD`). It is a literal constant, not a parameter that may be re-chosen after this document is committed.
2. **Per-pool child seed:** `child_seed = SEED + source_pool_index`, where `source_pool_index` is the 0-based position of the source pool in the **Observed-pool roster (frozen)** of this section, which is enumerated with its indices immediately below the pinned-randomness rules (`positive-cotzero-vs-direct` = 0, `mid-stepcalc-vs-cotzero` = 1, `mid-stepcalc-vs-fewshot` = 2, `marginal-stepcalc-vs-concise` = 3). `paper/PLAN-NOVELTY.md` Task 3 mirrors the same four entries in the same order; that roster block and this one are the only definition of `source_pool_index`.
3. **RNG layout:** exactly one `random.Random(child_seed)` instance per source pool, consumed **sequentially**: for null index `i = 0 .. K-1`, walk that pool's discordant items in the pool's frozen item order and draw one `rng.random()` per item; the item's labels are swapped iff the draw is `< 0.5`. There is no re-seeding between nulls and no other consumer of that RNG **within the null construction** — the R7 candidate stream of rule 5 is the single declared extension of it, realised as the two disjoint family streams of rule 5 (NULL-family, then POSITIVE-family for the POSITIVE source pool), and they are drawn only after every null block has been drawn; concordant items are copied through without ever being drawn for (a NULL-family candidate block draws on discordant items only, and the POSITIVE-family stream of rule 5 belongs to the POSITIVE source pool alone — see rule 5 and §3). The mapping (`source_pool`, `i`) → null pool is therefore a pure function of `(SEED, source_pool_index, frozen item order)`, and Task 1/5 can recompute any single null pool independently.
4. **`d == 0` (undecidable source) is an error, never a silent skip.** With `d = 0` there is no discordant item to relabel, so `permutation_nulls()` must raise `ValueError` and `build_pools()` must reject such a pool as a null source. A pool with `d = 0` may appear in `pools.json` only as an **observed** pool that the **Observed-pool roster (frozen)** of this section (`PLAN-NOVELTY.md` Task 3 mirrors it) explicitly declares *not a null source*. Silent omission is prohibited because it would shrink the FPR denominator without a record, and a `0/0` rate reads as perfect error control. Task 1's tests must assert `len(nulls) == K × (number of declared null sources)`.
5. **R7 candidate stream (declared extensions of rule 3 — pinned, not a second RNG).** The one `random.Random(child_seed)` instance of rule 3 per source pool is continued, **after** all `K = 200` null blocks of that source pool have been drawn and never interleaved with them, with **two declared, disjoint candidate streams consumed in a fixed order** — the NULL-family stream, which for null index `i = 0 .. K-1` and candidate index `j = 1 .. 8` yields the relabelling candidate `C(source_pool, i, j)`, and then the POSITIVE-family stream of the POSITIVE source pool:
   - **NULL-family candidates — relabelling (true effect ≡ 0).** Walk that pool's discordant items in the pool's frozen item order and draw one `rng.random()` per item; the item's labels are swapped iff the draw is `< 0.5`. The resulting pool `C(source_pool, i, j)` is a permutation null, which is exactly what a NULL-family evaluation needs: its true treatment effect is identically 0.
   - **POSITIVE-family candidates — label-preserving item bootstrap (effect preserved).** Only for the POSITIVE source pool, and only after the NULL-family stream above has been fully consumed: for candidate index `j = 1 .. 8` (there is exactly **one** POSITIVE unit, indexed `i = 0`), draw `n` values `u` from `rng.random()` — one per resampled position — and place at position `t` a copy of the pool's item at index `int(u × n)` in the pool's frozen item order, **leaving that item's `chal`/`inc` labels exactly as observed**. The pool is resampled **with replacement** and nothing is relabelled, so `C_pos(source_pool, i = 0, j)` carries the pool's observed positive effect in every draw and is a legitimate positive draw — a bootstrapped positive candidate, **not** a null. Relabelling is forbidden on the POSITIVE family for the same reason it is required on the NULL family: relabelling sets the true effect to 0, so a relabelled candidate could never be evidence about a true-positive rate.
   - **Nested draw order and `k`-subsets (pinned).** Within each stream the draw order is `i` outer, `j` inner — every candidate block of unit `i` is consumed before unit `i + 1` begins — and inside one block the pool's frozen item order is walked in order. The `k`-subset of a unit's candidate blocks is exactly the prefix `j = 1 .. k`.
   Because every null block is consumed before the first candidate block, and the two candidate streams never interleave, rule 3's mapping `(source_pool, i)` → null pool is unchanged and remains a pure function of `(SEED, source_pool_index, frozen item order)`; each relabelling candidate `C(source_pool, i, j)` is likewise a pure function of `(SEED, source_pool_index, frozen item order, i, j)`, as is the POSITIVE-family candidate `C_pos(source_pool, i = 0, j)` (that stream's first draw is fixed by the pinned draw counts of the null blocks and of the NULL-family stream). The candidate count `k = 8` and the reading of these candidates as R7's operative statistic are pinned in §5.2; the `k = 1` degeneracy of §2.1 is **not** an operative reading. Candidate families are never mixed: an effect-0 (relabelled) candidate is never used where the pool under evaluation is POSITIVE, and a label-preserving bootstrap candidate is never used where the pool under evaluation is NULL.

**Observed-pool roster (frozen).** This roster, together with its mirror in `paper/PLAN-NOVELTY.md` Task 3, is the only definition of `source_pool_index`; it is frozen with this document and must not be renumbered or reordered (renumbering would silently change every `child_seed` and therefore every null pool):

| `source_pool_index` | `source_pool` | provenance (mirrored from `PLAN-NOVELTY.md` Task 3) |
| --- | --- | --- |
| 0 | `positive-cotzero-vs-direct` | trackA, `d = 159` |
| 1 | `mid-stepcalc-vs-cotzero` | trackA, `d = 16` |
| 2 | `mid-stepcalc-vs-fewshot` | trackA, `d = 23` |
| 3 | `marginal-stepcalc-vs-concise` | qwen2:7b, `d = 6` |

All four roster entries are declared **null sources** — `PLAN-NOVELTY.md` Task 3 pairs each of them with `K = 200` permutation nulls — and none is marked *not a null source* at this freeze, so rule 4's *not a null source* escape hatch is currently unused and all four entries count toward the null-pool identity of rule 4. Rule 5's NULL-family candidate stream is drawn for **every** entry of this roster — all four are null sources, and each of their `K = 200` null units needs its own 8 candidates. The POSITIVE-family bootstrap stream of rule 5 is drawn for the POSITIVE source pool `positive-cotzero-vs-direct` (index 0) only, because the POSITIVE family has exactly one pool (§3).

Construction properties that later tasks must preserve and test:

- Only discordant items are relabelled; concordant items are copied through unchanged. (This describes the NULL construction — null pools and NULL-family candidates; the POSITIVE-family bootstrap candidates of rule 5 relabel nothing, §1 rule 5.)
- The discordant total is preserved: `b' + c' = d` in every null pool.
- **Structural gate keys are set by construction.** Every pool built by this study — observed and permutation-null alike — carries the four structural evidence keys set to `True`: `hidden_passed = True`, `safety_passed = True`, `rollback_available = True`, `bundle_signature_valid = True`. They are constants of this study's pool schema, so R1's five-key conjunction reduces to `statistical_passed` on these pools; asserting them is what makes the gate's negative conclusion *non-vacuous* (the other four keys are true by construction and are tested, not assumed). Task 1's tests must assert all four are `True` on every pool, and the pool schema in `paper/PLAN-NOVELTY.md` (File Structure) records them as required fields.
- Null pools derived from one real pool share that pool's questions and are therefore **not independent samples**. Wilson intervals are read conservatively for this reason, and the paper must state that the nulls come from relabelling, not from independent sampling.
- **The POSITIVE-family bootstrap candidates of rule 5 are candidates, not null pools.** They are never counted in the NULL pool set and never enter `FPR` or `FPR@k`; they are used only for `TPR_R7@8` (§5.1(c), §5.2). A bootstrap draw is a **construction** used to read a rule, not a measurement: no bootstrap-derived quantity (for example a candidate's own gain) may be reported as an experimental result about the underlying policies.
- Orientation convention: every pool stores its items as `{"chal": bool, "inc": bool}` plus an explicit `(chal_policy, inc_policy)` declaration; `b` counts items where the challenger passes and the incumbent fails, `c` the reverse, and `gain` is computed in the declared orientation. Counts and gain are therefore only comparable within one declared orientation. The binding statement, including the worked example, is §1.1.

### 1.1 Orientation convention (binding for every pool row)

```
Orientation convention (binding for every pool row):
  chal = the candidate being promoted; inc = the incumbent.
  b = # items where chal passes and inc fails;  c = # items where inc passes and chal fails.
  gain = (total_chal - total_inc) / n.
  Every pool row MUST declare (chal_policy, inc_policy).
  A signed gain may never be transcribed without its orientation.
Worked example: qwen2:7b step-calc(chal) vs concise-reason(inc) -> b=2, c=4, d=6, gain=-0.050;
the same pool read with the roles swapped reads better=4 worse=2 gain=+0.05. Both are the
same pool; only the declared orientation disambiguates them.
```

Note that `(total_chal - total_inc) / n` and `(b - c) / n` are the same quantity on a paired pool. §7's reconciliation of the marginal pool against `trackC-qwen2-7b-heldout40.json` is an instance of the rule above, and Task 4's results table must carry the orientation for every row.

## 2. Decision rules (7) — exact semantics

The unified interface is `decide(rule, pool) -> dict` (see `paper/PLAN-NOVELTY.md`, File Structure): a pure function returning at least `{"promote": bool, "p": float | None, "gain": float, "reasons": [str], "recomputable": bool}`. Same input must give the same output; no network, clock, or unseeded randomness.

| Rule | Name | Exact semantics |
| --- | --- | --- |
| **R1** | `gate` | This work's **five-key gate**; `alpha = 0.05`, `eps = 0.02`, **blind set**. Promotion iff all five keys are true: `statistical_passed` (blind paired exact McNemar `p < alpha` **and** `gain >= eps`), `hidden_passed`, `safety_passed`, `rollback_available`, `bundle_signature_valid`. Fail-closed: any false or missing key yields no promotion. Requires `pool["blind"] is True`. |
| **R2** | `point` | Promote iff `gain > 0` (**no test at all**). |
| **R3** | `unpaired` | **Two-sample proportion test (NOT paired)**: `p < 0.05` **and** `gain >= 0.02`. The test form actually used (e.g. Fisher exact or normal approximation) must be named in the implementation docstring. |
| **R4** | `nonblind` | The gate's paired test, computed on the **selection (non-blind) set** — i.e. the same paired exact McNemar criterion, ignoring the blindness constraint (`pool["blind"] is False`). **§5A: this arm is NOT EVALUATED in this study** — the repository contains no non-blind per-item pool, so the blindness contrast R1 vs R4 is unmeasured and R4 must be reported as `not evaluated (no non-blind data)`. Implemented by Task 2 (a rule of the description) but never computed as a result. |
| **R5** | `loose` | The gate with `alpha = 0.20` (threshold sensitivity); all other gate semantics unchanged. |
| **R6** | `no-stat` | The gate with the significance test **dropped** but the **magnitude criterion kept** (adopted semantics — **AMENDMENT 1**): promote iff `gain >= eps = 0.02`, together with the four structural keys. The earlier phrasing "the `statistical_passed` key removed, the other four keys kept" is ambiguous and superseded; it is **not** the operative rule. |
| **R7** | `bestofk` | Promote the **point-estimate best of k candidates** (selection pressure): among `k` candidate pools, promote iff the best candidate has `gain > 0`. For every evaluation in this document `k` is the **pre-run-fixed `k = 8`** of §5.2, over candidates built **family-appropriately** by the pinned candidate construction of §1 rule 5 — relabelling for a NULL-family evaluation, **label-preserving item bootstrap** for a POSITIVE-family evaluation, the two never mixed; the `k = 1` degeneracy of §2.1 is an interface note only and is **not** the operative reading. |

### 2.1 R7 interface (controller decision — binding)

R7's interface is `decide(rule, pool)`, reading an **optional** `pool["candidates"]` list (a list of candidate pools). When `pool["candidates"]` is absent, R7 **degenerates to k = 1**: the best of one candidate is the pool itself, making it equivalent to R2. The unified `decide(rule, pool)` signature is preserved so that Task 5's audit stays uniform; the degenerate-k behaviour must be documented in the implementation docstring so it is auditable. **This interface degeneracy is not the descriptive curve's `k = 1` endpoint** (§4): the degeneracy is the case *no candidates given*, where the single candidate is the pool itself; the curve's `k = 1` endpoint is candidate block `(i, 1)` of the pinned stream — a genuine candidate pool which is not the pool itself. The two coincide only if a caller passes the pool itself as that single candidate, which no reading of this document does.

**Operative reading of the statistic (binding).** For every §5 evaluation — branch (i), branch (ii), and clause (c)'s TPR alike — R7 is read at the **pre-run-fixed `k = 8`** over that unit's candidates `C(source_pool, i, j)`, `j = 1..8`, of the pinned candidate stream (§1 rule 5), as defined in §5.2. The absent-`candidates` degeneracy documented just above (`k = 1` ⇒ the pool itself ⇒ behaviourally R2, no information beyond R2) is an interface note about the function signature, **not** an operative reading: `R7@k = 1` is never substituted for the `k = 8` term anywhere in this document, and the descriptive curve's `k = 1` endpoint (candidate block `(i, 1)`, §1 rule 5) is a third, distinct reading which is likewise never so substituted.

### 2.2 R6 operational reading (adopted as AMENDMENT 1)

**AMENDMENT 1** (top of this file) is the binding statement of R6's semantics; the paragraph below records the supporting reasoning. The adopted reading is: R6 keeps the gate's **magnitude criterion** `gain >= eps = 0.02` and drops the significance test.

On the pools of this study the four keys other than `statistical_passed` (`hidden_passed`, `safety_passed`, `rollback_available`, `bundle_signature_valid`) are **structural**: pool construction sets them true. A reading of R6 as "the four remaining structural keys alone" would therefore promote every pool and give null FPR = 1.0. The pilot's R6 null FPR (**0.320**, superseded design evidence per §7.1 — recorded, not citable) is inconsistent with that reading too, but the **construction argument above is the operative reason**; the pilot figure is corroboration only, never the grounds. At `d = 6` the adopted reading coincides with R2's `gain > 0` (gains there are multiples of 0.025, so `gain > 0` and `gain >= 0.02` are the same event) — which is exactly why the pilot's R6 and R2 FPRs tie at 0.320. On large-discordance pools the two can diverge, and both must be reported separately.

## 3. Pool families

| Family | Definition |
| --- | --- |
| **NULL** | The permutation nulls of §1 (true value identically 0). |
| **POSITIVE** | Real pairing `cot-zero` vs `direct` (true effect large, `> 0`), declared in the orientation `(chal_policy=cot-zero, inc_policy=direct, b=159, c=0, d=159, gain=+0.795)`. |
| **MARGINAL** | Real pairing `step-calc` vs `concise-reason` on `qwen2:7b`, declared in the §1.1 orientation `(chal_policy=step-calc, inc_policy=concise-reason, b=2, c=4, d=6, gain=-0.050)`; `trackC-qwen2-7b-heldout40.json` stores the same pool in the reverse orientation `(chal_policy=concise-reason, inc_policy=step-calc, b=4, c=2, d=6, gain=+0.05)` (reconciled in §7.2). The family headline is the small magnitude (0.05) at `p = 0.688`, i.e. small in either orientation. |

Each real (observed) pool carries a `truth` label together with its provenance, so that no pool can be silently reclassified. `paper/PLAN-NOVELTY.md` (Task 3) fixes the observed-pool roster and sizes; pools taken from the blind versus the selection set must be labelled via the `blind` flag because R1/R4 depend on it — **in this corpus every pool is `blind = True`: no selection-set pool exists, so the R4 arm is not evaluable (§5A).** This section defines the pool **families**; the numbered observed-pool **roster** — and therefore each pool's `source_pool_index` and `child_seed` — is fixed in §1's **Observed-pool roster (frozen)** block (mirrored in `PLAN-NOVELTY.md` Task 3), not here. R7's candidates are family-appropriate (§1 rule 5): a NULL-family evaluation uses relabelling candidates and a POSITIVE-family evaluation uses a **label-preserving item bootstrap** of the POSITIVE pool, so an effect-zero (relabelled) pool is never used to measure a true-positive rate.

## 4. Metrics

| Metric | Definition |
| --- | --- |
| **FPR** | Fraction of NULL pools promoted (lower is better). R2's null expectation is the tie-corrected `E[FPR_R2] = (1 - P(tie))/2` of §4.1, **not** 0.5. **R1 expected ≤ alpha**. |
| **TPR** | Fraction of POSITIVE pools promoted (higher is better). This document's POSITIVE set contains exactly **one** pool, so this denominator is 1 and every TPR below is a single 0/1 decision; §5.1(c) states the consequences and forbids reading any TPR comparison between rules as a difference. |
| **FPR@k** | False-positive rate of `bestofk` on NULL pools, `k = 1..8`. The `k`-subset is the **prefix `j = 1..k`** of that unit's pinned candidate blocks (§1 rule 5), so the curve is one fixed nested stream, not a fresh draw per `k`. The `k = 8` endpoint is written **`FPR_R7@8`** and denotes the **same quantity** as `FPR@8(R7)`; branches (i) **and** (ii) read that endpoint only (§5.1, §5.2). The `k = 1..7` curve is descriptive, is **required of Task 4**, and is not a decision device; its `k = 1` endpoint is candidate block `(i, 1)` — a genuine candidate pool, **not** the pool itself — and must not be confused with §2.1's interface degeneracy (`no candidates given` ⇒ the pool itself). In particular, the degenerate `k = 1` reading is never substituted for `FPR_R7@8`, and neither is the curve's `k = 1` endpoint. |
| **recomputability** | Whether the audit script can recompute each rule's decision (boolean). |

### 4.1 R2's null expectation is not 0.5 — tie correction (binding)

R2 promotes iff `gain > 0`, i.e. iff `b' > c'`. Under §1's construction each discordant item independently ends up "challenger passes, incumbent fails" with probability 0.5, so `b' ~ Binomial(d, 0.5)`; a **tie** (`b' = c'`, no promotion) therefore has probability `P(tie) = C(d, d/2) / 2^d` (even `d`), and by symmetry

`E[FPR_R2] = (1 - P(tie)) / 2`.

Consequences Task 4 must apply, per pool and pooled:

- at `d = 6`: `P(tie) = 20/64 = 0.3125` → `E[FPR_R2] = (1 - 20/64)/2 = 0.34375`;
- at `d = 16`: `P(tie) = 12870/65536 = 0.19638…` → `E[FPR_R2] = 0.40181…`;
- only as `d → infinity` does the expectation approach 0.5. For a pooled FPR over pools with different `d`, the expectation is the size-weighted mean of `(1 - P(tie_d))/2` over those pools.

So on the `d = 6` MARGINAL nulls R2 is expected to promote about **a third**, not about a half. Task 4 must compare the observed R2 FPR against `(1 - P(tie))/2` computed for that pool's own `d` (and report the pooled expectation next to the pooled rate) so that a non-discrepancy is not reported as a discrepancy.

Interpretation notes fixed in advance: R2's null expectation (§4.1) is **constructive** — it is what "no error control" means, and must never be reported as "we found that the baseline is bad". R1's null FPR may legitimately be 0 at small `d` because the exact test is discrete and conservative; report 0 together with its interval upper bound, never as a "zero error rate". Wilson 95% intervals are the pre-registered comparison device for "significantly lower"; because the null pools of one source pool are not independent, they are read conservatively.

## 5. Exhaustive verdict branches

| Branch | Condition | Recorded verdict |
| --- | --- | --- |
| **(i)** | `WilsonUpper95(FPR_R1) < WilsonLower95(FPR_R2)` and `WilsonUpper95(FPR_R1) < WilsonLower95(FPR_R7@8)` (intervals disjoint, R1 below) on the pooled NULL set, **and** the paired exact McNemar on the same null set agrees for both comparisons, **and** `TPR_R1 >= TPR_R2` and `TPR_R1 >= TPR_R7@8` — exact clauses in §5.1; the R7 terms are the pinned `k = 8` statistic of §5.2, and clause (c) is a sanity guard with no discriminating power at the POSITIVE denominator of 1 (§5.1(c)) | "gate value established" |
| **(ii)** | (i) not met, but `FPR@8(R1) < WilsonLower95(FPR@8(R2))` **and** `FPR@8(R1) < WilsonLower95(FPR@8(R7))` — exact device in §5.1; here `FPR@8(R7)` denotes the same pinned `k = 8` quantity as `FPR_R7@8` (§5.2) | "value established under selection pressure" |
| **(iii)** | neither (i) nor (ii) | "not established"; the novelty score is **not** raised |

The three branches are exhaustive by construction; the recorded branch is written into `results/rounds/round5/ablation.json` as `verdict_branch`. Branch (iii) leaves the self-assessed novelty score unchanged — an honest negative is a permitted and reportable outcome.

### 5.1 Exact statistics and exact comparisons (binding — Task 4 must decide these without further judgement)

**Statistics.** On the NULL pool set (every null of every declared source pool): `FPR_rule = #{NULL pools where the rule promotes} / #{NULL pools}`. `FPR@k(rule)` is the same proportion for `bestofk` with `k` candidates per null pool (`k = 1..8`). On the POSITIVE pool set: `TPR_rule` likewise. `WilsonLower95(p, n)` and `WilsonUpper95(p, n)` are the Wilson 95% score interval's lower and upper endpoints for a proportion `p` with denominator `n`.

**R7 is read at one pinned `k`.** For `rule = R7` the operative `k` is the pre-run-fixed `k = 8` (§5.2), and the two symbols used below are defined by it: `FPR_R7@8 := FPR@8(R7)` on the pooled NULL set, and `TPR_R7@8 :=` R7's POSITIVE promotion rate at that same `k = 8`. Every occurrence of `FPR_R7@8` and `TPR_R7@8` in this document means exactly those two quantities. `FPR_R7@8` is computed over the **NULL-family** relabelling candidates `C(source_pool, i, j)`, `j = 1..8`, of the pinned candidate stream (§1 rule 5), and `TPR_R7@8` over the **POSITIVE-family** label-preserving bootstrap candidates `C_pos(source_pool, i = 0, j)`, `j = 1..8`, of that same rule — the two families never share a candidate construction (§1 rule 5, §5.2). No `k` other than 8 is admissible for the R7 terms of §5, and the degenerate `R7@k = 1` reading of §2.1 is **not** an admissible substitute (§5.2).

**Branch (i) — exact clauses (all three required).**

(a) *Intervals disjoint with R1 below:* `WilsonUpper95(FPR_R1) < WilsonLower95(FPR_R2)` **and** `WilsonUpper95(FPR_R1) < WilsonLower95(FPR_R7@8)`, all three rates computed on the same pooled NULL set (`n` = the total number of NULL pools). The R7 term here is the `k = 8` statistic, not the `k = 1` degeneration.

(b) *Paired exact McNemar agrees, on a stated pairing unit.* The pairing unit is the individual null pool identified by `(source_pool, null_index)`, `null_index = 0..K-1`: each declared source pool contributes exactly `K = 200` paired units, and a unit contributes one 2×2 pair — (R1 decision, R2 decision) on that same null pool for the R2 comparison, (R1 decision, R7@8 decision) for the R7 comparison, where the unit's **R7@8 decision** is `bestofk` at `k = 8` over that unit's own pinned candidate pools `C(source_pool, i, j)`, `j = 1..8` (§1 rule 5, §5.2; for a NULL unit these are the **NULL-family** relabelling candidates of §1 rule 5, never the POSITIVE-family bootstrap, because the unit is a NULL pool) — i.e. the R2 null pool at index `i` is not itself one of the unit's candidates. Pairing is by source pool **and** null index; nulls are never paired across source pools and no re-pairing or subsetting is permitted after the run. "Agrees" means the paired exact McNemar is same-direction as clause (a) (`FPR_R1 < FPR_R2`, respectively `FPR_R1 < FPR_R7@8`) **and** its two-sided exact `p < alpha = 0.05`; if either comparison fails to agree, branch (i) is not met.

(c) *R1 does not lose true positives — a sanity guard, not a discriminator:* `TPR_R1 >= TPR_R2` and `TPR_R1 >= TPR_R7@8`, as point estimates over the POSITIVE pools, with each rule's `promoted / total` printed so the denominator is visible. `TPR_R7@8` is R7's `k = 8` TPR over the **POSITIVE-family** label-preserving bootstrap candidates `C_pos(source_pool, i = 0, j)`, `j = 1..8` (§1 rule 5, §5.2), so the true-positive comparison is made on genuinely positive draws and not on effect-0 relabellings. **The POSITIVE set of this document contains exactly one pool, so the denominator of every TPR in this clause is 1**: each TPR is a single 0/1 decision and this clause therefore has **no discriminating power** between rules at this denominator — it cannot rank R1 against R2 or R7. Its only admissible reading is the anti-vacuity guard *R1 does not lose true positives*, i.e. it rules out a gate that never promotes on a real effect. **Clause (c) may not be reported as evidence that R1 "outperforms" R2 or R7 on TPR, or that R1 has any TPR advantage over either of them**; any such statement is out of scope for this document and must not appear in any result file or paper text.

**Branch (ii) — exact device (one clause).** (ii) is declared iff branch (i) is not met **and** `FPR@8(R1) < WilsonLower95(FPR@8(R2))` **and** `FPR@8(R1) < WilsonLower95(FPR@8(R7))`, each proportion computed on the same pooled NULL set with its own denominator. `FPR@8(R7)` here is the same `FPR_R7@8` quantity used in branch (i) (§5.2), so the R7 term cannot drift between the two branches. The `k = 8` endpoint is fixed before the run because it is the largest pre-registered `k` and therefore the most favourable to the selection-pressure baselines; no other `k` may be substituted after the run and no `k` may be selected post hoc from the curve. If branch (i) is met, the verdict is (i) regardless of the `FPR@8` comparison. The phrase "significantly flatter" is **not** a device and must not be used to decide (ii).

**Branch (iii).** Neither (i) nor (ii) → "not established"; the novelty score is not raised.

**Independence safeguard (binding for branch (i)).** The 200 permutation nulls derived from one source pool share that pool's questions and are therefore **NOT independent Bernoulli trials**; the Wilson intervals are a **conservative descriptive bound only**, not a valid inference under that dependence. Accordingly, branch (i) may be declared **only when the paired McNemar test on the same null set agrees**; if the paired McNemar disagrees with the interval reading, branch (i) must not be recorded. FPR must also be reported **per source pool**, not only pooled. Branches (i) and (ii) both read the same pooled NULL set, so per-source-pool reporting is required for both, and (ii)'s `FPR@8` is reported per source pool as well.

### 5.2 R7's operative statistic (binding — `k = 8` pinned before the run)

**The statistic.** In every comparison of §5 the R7 term is the pooled promotion rate of `bestofk` evaluated at the **pre-run-fixed** `k = 8`: written `FPR_R7@8` on the pooled NULL set and `TPR_R7@8` on the POSITIVE pool set. `FPR_R7@8` is the same quantity as `FPR@8(R7)` of §4/§5.1, and `TPR_R7@8` is R7's POSITIVE promotion rate at that same `k = 8`. `k = 8` is fixed here, before any deliverable run, as the largest pre-registered `k`; no other `k` may be substituted after the run, and no `k` may be selected post hoc from the `k` curve. Branches (i) and (ii) and clause (c) of §5.1 all read this one statistic.

**How R7's candidates are generated (pinned construction, family-appropriate).** For a NULL-family evaluation R7's candidates are permutation nulls of the unit's own source pool, produced by the pinned construction of §1 — the same per-source-pool `random.Random(child_seed)` instance, the same one-draw-per-discordant-item rule, the same frozen item order — on the NULL-family candidate stream of §1 rule 5: for pairing unit `(source_pool, null_index = i)` and candidate index `j = 1 .. 8` (the pinned `k = 8`), the candidate pool `C(source_pool, i, j)` is the relabelling obtained from candidate block `(i, j)` of that source pool. For the POSITIVE-family evaluation (`TPR_R7@8`) R7's candidates are **not** relabellings: they are the **label-preserving item bootstrap** candidates `C_pos(source_pool, i = 0, j)`, `j = 1 .. 8`, of §1 rule 5, built by resampling the POSITIVE pool's items **with replacement** and leaving every `chal`/`inc` label exactly as observed, so the injected positive effect is preserved and each candidate is a legitimate positive draw. A relabelled (effect-0) candidate must never be used for the POSITIVE term, and a bootstrap candidate must never be used for the NULL term.

**Pinning of the candidate stream (nested draw order, subsets, purity).** Candidate blocks are the `(i, j)` blocks consumed after the pool's `K = 200` null blocks, never before them and never interleaved with them; the two candidate streams (NULL-family first, then POSITIVE-family for the POSITIVE source pool) are likewise disjoint and never interleaved. Within a stream the draws are nested `i` outer, `j` inner — all of unit `i`'s candidate blocks are consumed before unit `i + 1` begins — and inside one block the pool's frozen item order is walked in order; the `k`-subset of a unit's candidate blocks is exactly the prefix `j = 1 .. k`. Each candidate is therefore a pure function of `(SEED, source_pool_index, frozen item order, i, j)` (`C_pos` with the POSITIVE unit's `i = 0`) and can be recomputed independently by Task 5. Because a unit's candidates come from the candidate blocks and not from its own null block, the unit's own null pool (the R2 pool at that index) is **not** among its candidates, so §7.2's binding relation that k-candidates are drawn independently of the R2 null pool is preserved. At the pinned `k = 8` a unit contributes 8 candidate pools.

**`R7@k = 1` is NOT the operative reading.** §2.1 records R7's interface degeneracy: with no `pool["candidates"]`, the best of one candidate is the pool itself, so `R7@k = 1` reduces to `R2` and carries no information beyond R2. **This interface degeneracy is a different thing from the descriptive curve's `k = 1` endpoint** (§4): that endpoint is candidate block `(i, 1)` of the pinned stream — a genuine candidate pool which is not the pool itself — so the curve's `k = 1` value is a descriptive R7 reading, merely not the operative `k = 8` reading; only the *no-candidates* degeneracy reduces to `R2`. That degenerate reading is **not** the R7 term of §5 — not in branch (i), not in branch (ii), and not in clause (c) — nor anywhere else in this document. Wherever §5 reads `FPR_R7@8` or `TPR_R7@8` it means the `k = 8` statistic defined above; an analysis that reports the `k = 1` reading in place of it is not this document's pre-registered comparison and would have to be disclosed as a dated revision declaration before being reported.

## 5A. Limitations / not-evaluated arms (binding — controller ruling 17, added 2026-09-12 before the deliverable run)

### R4 (`nonblind`) is NOT EVALUATED — the repository contains no non-blind per-item data

**Recorded limitation.** Rule **R4** of §2 — "the gate's paired test, computed on the **selection (non-blind) set**", i.e. the paired exact McNemar criterion with the blindness constraint dropped — is **not evaluated** in this study. There is nothing to evaluate it on:

1. `results/runs/*.json` carry **only aggregate fields** and contain **no per-question details**, so no per-item pool can be derived from them.
2. Every usable per-item pool in this repository derives from a **blind held-out set** (`examples/heldout40.json`, `examples/heldout-batch2-160.json`, and the round-4 blind merges built from them), and the frozen roster of §1 labels all four observed pools `blind = True`.
3. Consequently there is **no non-blind (selection-set) per-item pool** in this repository, and none can be derived from the committed artefacts.

**Consequence, stated plainly.** The **blindness contrast — R1 (blind, `alpha = 0.05`) versus R4 (non-blind, same paired test) — is therefore unmeasured.** R4's column must be reported as **`not evaluated (no non-blind data)`**. R4 is **omitted from results with this explicit note**; it may not be silently dropped from a table, and it may not be reported as a number. Reporting R4 as `0` (or as any promoted/total fraction) because every available pool has `blind = True` would be an artefact of the corpus — `decide("R4", pool)` would be reading a blind pool through a non-blind rule — and is prohibited.

**Declined construction (recorded so it is not reinvented).** A **synthetic non-blind pool** built from the registry's **aggregate selection-set counts** was considered and **DECLINED**. It is an unverifiable construction: the aggregate counts fix no per-question pairing, so no `b`/`c` discordance structure can be recovered, and any per-item pool fabricated to fit those marginals would be invented evidence, not a measurement. Per the standing rule that a construction is not a measurement, no R4 figure may be derived from such a pool.

**Mechanical record.** The invariant is recorded where it cannot be lost, not only in this prose: `scripts/build_pools.py` carries the constants `R4_STATUS` and `NO_NONBLIND_POOL_NOTE`, emits them into the top-level `meta` note of `results/rounds/round5/pools.json` (as `r4_status`, `r4_evaluable: false`, `all_pools_blind: true`, `no_nonblind_pool_exists: true`, `r4_note`), refuses to load a bare-array artefact, and asserts in `main()` that every pool is blind. `tests/test_build_pools.py::test_pools_artefact_declares_no_nonblind_pool_and_marks_r4_not_evaluable` asserts both invariants (every pool row `blind is True`; the artefact carries the note) and proves the guard bites on a bare array and on a non-blind row.

**Consequences for Tasks 2, 4 and 5.** Task 2 still *implements* R4 as specified in §2 (it is a rule of the published description and stays in the uniform `decide(rule, pool)` interface, with its own unit test on hand-made pools) — implementation of a rule is not evaluation of it. Task 4 must **not** compute or report an R4 column: it reports `R4: not evaluated (no non-blind data)` in every rules table, and §5's branches are unaffected because no branch reads R4. Task 5 must not attempt to recompute R4 decisions from the corpus and must carry the same not-evaluated note.

### Not-evaluated arms summary

| Arm | Status | Basis |
| --- | --- | --- |
| **R4** `nonblind` | **not evaluated (no non-blind data)** | no non-blind per-item pool exists; `results/runs/*.json` are aggregate-only; synthetic reconstruction declined as unverifiable |
| Task 6 `proposer` arm | not executed unless run (optional, §6) | must be recorded as "not executed", never substituted with other data |

## 6. Budget

- **Tasks 1–5 use ZERO model calls.** The pool construction, the seven rules, the ablation, and the audit are pure computation over already-committed run data.
- The optional proposer arm (Task 6) is capped at **400 calls** (`heldout40` × 5 policies × 2). It is optional and must not be a dependency of any other task: if it is not executed it must be recorded as "not executed" and never substituted with other data.

## 7. Pilot evidence (already run — PILOT EVIDENCE, NOT A RESULT)

The numbers in this section come from a pre-execution mini-pilot run during plan design. They are recorded **as pilot evidence only, explicitly not as results**, and — per §7.1 — **none of them may be cited** by any task, result file, or paper text.

### 7.1 Supersession (binding — controller ruling 10)

The standing prose pilot figures are **SUPERSEDED and NOT CITABLE**:

1. **Superseded set.** Permutation count `K=2000`; mean null gain `-0.0029`; FPR R1 `0.015` / R2 `0.320` / R6 `0.320`; `FPR@k` k=1 `0.357`, k=2 `0.620`, k=4 `0.838`, k=8 `0.968`.
2. **Why they are superseded.** The ad-hoc pilot recorded **no seed at all**, and it did not record a single `(K, seed)` pair per metric. Its FPR figures sit on a `/2000` grid (`0.015 = 30/2000`, `0.320 = 640/2000`), while three of its `FPR@k` figures are **not on the deliverable's `K = 200` grid**: `0.357 × 200 = 71.4`, `0.838 × 200 = 167.6`, `0.968 × 200 = 193.6` are not whole numbers. The prose therefore cannot be reproduced from any single recorded `(K, seed)` pair, and no pilot script or pool artefact was committed either.
3. **Task 1 must re-run the pilot as a committed script.** The script is committed **before** it is run, and it records an **explicit `K` and an explicit seed per metric** (one `(metric, K, seed)` record per reported metric — a per-metric record is required precisely because the standing prose mixes grids).
4. **Only the re-run figures become the citable pilot.** Until Task 1 has committed that script and its outputs, no figure in this section is citable anywhere, including in Task 4's report and in the paper.

### 7.2 The standing records (non-citable), with explicit orientation

- observed marginal pool: `qwen2:7b` `(chal_policy=step-calc, inc_policy=concise-reason, b=2, c=4, d=6, gain=-0.050)`, McNemar `p=0.688`
- observed positive pool: trackA `(chal_policy=cot-zero, inc_policy=direct, b=159, c=0, d=159, gain=+0.795)`, `p=2.7e-48`
- permutation null, `K=2000`, mean gain = `-0.0029` (expected ~0)
- pilot FPRs: R1 `0.015`, R2 `0.320`, R6 `0.320`; R7 FPR@k: k=1 `0.357`, k=2 `0.620`, k=4 `0.838`, k=8 `0.968`

Provenance and orientation note (added at Task 0 to make the frozen pilot record auditable — **no value was altered**; orientation labels corrected in fix round 2, again **no value altered**):

- The marginal record is consistent with `results/rounds/round4/trackC-qwen2-7b-heldout40.json`, which stores the pair key `step-calc_vs_concise-reason` as `better=4, worse=2, p=0.6875, gain=+0.05` over `n=40`. In that file `better` counts the **second-named** policy's wins and `gain = (total_y - total_x)/n` (see `scripts/summarize_trackC.py`), so with `x = step-calc` (35/40) and `y = concise-reason` (37/40) the stored record is itself in the orientation `(chal_policy=concise-reason, inc_policy=step-calc, b=4, c=2, d=6, gain=+0.05)` — concise-reason holds the higher pass total (37 vs 35). The §7.2 bullet above records the **same pool** in the orientation `(chal_policy=step-calc, inc_policy=concise-reason, b=2, c=4, d=6, gain=-0.050)`: with step-calc as challenger the gain is negative. The two records agree on `d=6` and `p=0.688`; only the declared orientation differs. Task 1/3 must therefore record each pool's orientation explicitly (see §1), and Task 4 must state which orientation each reported decision uses.
- The positive record matches `results/rounds/round4/trackA-merged.json` (`direct_vs_cot-zero`: `better=159, worse=0, p=2.7369110631344083e-48, gain=0.795`, `n=200`); recomputed from that file's `details`, `better=159` counts cot-zero-only passes (cot-zero 186/200 vs direct 27/200), so the stored orientation is `(chal_policy=cot-zero, inc_policy=direct, b=159, c=0, d=159, gain=+0.795)` — identical to the §7.2 bullet's orientation.
- The `K=2000` mean-null-gain and pilot FPR figures come from the design-validation block of `paper/PLAN-NOVELTY.md`; no pilot artefact or script was written to disk and no seed was recorded, which is why **§7.1 (controller ruling 10) declares them superseded and not citable**. The deliverable run (K=200, Task 4) must recompute every reported metric from `pools.json`, and its numbers — not these — are the ones that may be reported.
- (Retained only to document the design reasoning; the values themselves are superseded by §7.1.) The pilot's R7 FPR@k at `k=1` (0.357) need not equal the R2 FPR (0.320): the k-curve candidates are built by an independent relabelling draw rather than by reusing the R2 pool. Both values are reported; neither is substituted for the other. The **relation** is binding on Task 4: k-candidates must be drawn independently of the R2 null pool. In the deliverable run those candidates are the pinned candidate stream of §1 rule 5, read at the pre-run-fixed `k = 8` of §5.2 (the pilot's `k = 1` value above is not that reading and is not substituted for it). The curve's `k = 1` endpoint is candidate block `(i, 1)` of that stream — a genuine candidate pool, **not** the interface degeneracy's *no candidates ⇒ the pool itself* — which is one more reason that endpoint need not coincide with the R2 null-pool rate.

### 7.3 Recomputability status of the pilot figures (binding)

The pilot figures recorded in §7.2 — mean null gain `-0.0029`; FPR R1 `0.015` / R2 `0.320` / R6 `0.320`; FPR@k `0.357` / `0.620` / `0.838` / `0.968` — are **design evidence only and are not yet recomputable from committed artefacts** (no pilot pool file was written to disk) **and are additionally superseded by §7.1**. They become citable only once Task 1's re-run script (committed before the run, with its `(metric, K, seed)` records) has produced and committed its outputs; until then no paper text may cite any of these values as a result.

## 8. Design constraint: discordance granularity (binding on Tasks 3 and 4)

At `d = 6` the exact McNemar `p` can only take values `{0.031, 0.219, ...}`, so `alpha = 0.05` and `alpha = 0.20` produce **IDENTICAL decisions** there. Therefore the alpha-sensitivity (R5) and unpaired (R3) arms **MUST be evaluated on large-discordance pools (`d >= 15`)**, e.g. the available `step-calc` vs `cot-zero` (`d=16`), `step-calc` vs `few-shot` (`d=23`), `cot-zero` vs `few-shot` (`d=15`).

Reporting an "alpha has no effect" conclusion from `d = 6` pools alone would be an artefact of the discrete test's granularity, not a finding. Task 3 must therefore include at least one observed pool with `discordant_total >= 15`, and Task 4 must report the R5 and R3 arms on those large-discordance pools (the `d = 6` marginal pool may be reported alongside, clearly separated).

## 9. Boundary statement

We compare decision **PROCEDURES** consistent with published descriptions, **NOT** the actual REMO / SPHERE / TextGrad systems, and no claim of reproducing or beating those systems may be made. The comparison targets idealised decision rules in the sense that each is a published description's decision logic instantiated on our pools; the systems themselves were not re-implemented, downloaded, or run. This boundary must appear in the paper's limitations and must not be weakened in the abstract or the introduction whatever verdict branch (§5) is recorded.
