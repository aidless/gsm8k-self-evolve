# PREREG Round-5 — gate decision-rule ablation (novelty head-to-head)

- **Date:** 2026-09-12
- **Status:** preregistered, no ablation executed yet
- **Frozen-before-run statement:** this file is frozen before any run — it is committed first, and nothing in the ablation (Tasks 1–5, optional Task 6) is executed until that commit exists.

Any deviation from this document must be disclosed as a dated **revision declaration** at the top of `results/rounds/round5/ROUND5-RESULT.md` before the deviating analysis is reported. Silent deviation is prohibited.

---

## 1. Zero-effect construction (core)

Given a real paired pool's discordant item set `D` (`|D| = d > 0`), independently relabel each of the `d` items (swap challenger/incumbent) with probability 0.5; all other (concordant) items are left unchanged. Under this relabelling the true treatment effect is identically 0 while the discordant total stays `d`. Fixed seed; **K = 200** permutation-null pools per real pool.

Construction properties that later tasks must preserve and test:

- Only discordant items are relabelled; concordant items are copied through unchanged.
- The discordant total is preserved: `b' + c' = d` in every null pool.
- The random source is `random.Random(seed)` with a fixed, recorded seed; the mapping (real pool → its 200 nulls) must be deterministic and independently reproducible.
- Null pools derived from one real pool share that pool's questions and are therefore **not independent samples**. Wilson intervals are read conservatively for this reason, and the paper must state that the nulls come from relabelling, not from independent sampling.
- Orientation convention: every pool stores its items as `{"chal": bool, "inc": bool}` plus an explicit orientation label; `b` counts items where the challenger is correct and the incumbent wrong, `c` the reverse, and `gain = (b - c) / n` is computed in the stored orientation. Counts and gain are therefore only comparable within one orientation.

## 2. Decision rules (7) — exact semantics

The unified interface is `decide(rule, pool) -> dict` (see `paper/PLAN-NOVELTY.md`, File Structure): a pure function returning at least `{"promote": bool, "p": float | None, "gain": float, "reasons": [str], "recomputable": bool}`. Same input must give the same output; no network, clock, or unseeded randomness.

| Rule | Name | Exact semantics |
| --- | --- | --- |
| **R1** | `gate` | This work's **five-key gate**; `alpha = 0.05`, `eps = 0.02`, **blind set**. Promotion iff all five keys are true: `statistical_passed` (blind paired exact McNemar `p < alpha` **and** `gain >= eps`), `hidden_passed`, `safety_passed`, `rollback_available`, `bundle_signature_valid`. Fail-closed: any false or missing key yields no promotion. Requires `pool["blind"] is True`. |
| **R2** | `point` | Promote iff `gain > 0` (**no test at all**). |
| **R3** | `unpaired` | **Two-sample proportion test (NOT paired)**: `p < 0.05` **and** `gain >= 0.02`. The test form actually used (e.g. Fisher exact or normal approximation) must be named in the implementation docstring. |
| **R4** | `nonblind` | The gate's paired test, computed on the **selection (non-blind) set** — i.e. the same paired exact McNemar criterion, ignoring the blindness constraint (`pool["blind"] is False`). |
| **R5** | `loose` | The gate with `alpha = 0.20` (threshold sensitivity); all other gate semantics unchanged. |
| **R6** | `no-stat` | The gate with the `statistical_passed` key **removed** (the other four keys kept). |
| **R7** | `bestofk` | Promote the **point-estimate best of k candidates** (selection pressure): among `k` candidate pools, promote iff the best candidate has `gain > 0`. |

### 2.1 R7 interface (controller decision — binding)

R7's interface is `decide(rule, pool)`, reading an **optional** `pool["candidates"]` list (a list of candidate pools). When `pool["candidates"]` is absent, R7 **degenerates to k = 1**: the best of one candidate is the pool itself, making it equivalent to R2. The unified `decide(rule, pool)` signature is preserved so that Task 5's audit stays uniform; the degenerate-k behaviour must be documented in the implementation docstring so it is auditable.

### 2.2 R6 operational reading (pinned by pilot evidence, §7)

On the pools of this study the four keys other than `statistical_passed` (`hidden_passed`, `safety_passed`, `rollback_available`, `bundle_signature_valid`) are **structural**: pool construction sets them true. A reading of R6 as "the four remaining structural keys alone" would therefore promote every pool and give null FPR = 1.0. The pilot records R6 null FPR = **0.320**, which rules that reading out. The frozen reading is therefore: R6 keeps the gate's **magnitude criterion** `gain >= eps = 0.02` and drops the significance test. At `d = 6` this coincides with R2's `gain > 0` (gains there are multiples of 0.025, so `gain > 0` and `gain >= 0.02` are the same event) — which is exactly why the pilot's R6 and R2 FPRs tie at 0.320. On large-discordance pools the two can diverge, and both must be reported separately.

## 3. Pool families

| Family | Definition |
| --- | --- |
| **NULL** | The permutation nulls of §1 (true value identically 0). |
| **POSITIVE** | Real pairing `cot-zero` vs `direct` (true effect large, `> 0`). |
| **MARGINAL** | Real pairing `step-calc` vs `concise-reason` on `qwen2:7b` (gain ~ +0.05). |

Each real (observed) pool carries a `truth` label together with its provenance, so that no pool can be silently reclassified. `paper/PLAN-NOVELTY.md` (Task 3) fixes the observed-pool roster and sizes; pools taken from the blind versus the selection set must be labelled via the `blind` flag because R1/R4 depend on it.

## 4. Metrics

| Metric | Definition |
| --- | --- |
| **FPR** | Fraction of NULL pools promoted (lower is better; **R2 expected ≈ 0.5**, **R1 expected ≤ alpha**). |
| **TPR** | Fraction of POSITIVE pools promoted (higher is better). |
| **FPR@k** | False-positive rate of `bestofk` on NULL pools, `k = 1..8`. |
| **recomputability** | Whether the audit script can recompute each rule's decision (boolean). |

Interpretation notes fixed in advance: R2's ≈ 0.5 is **constructive** — it is what "no error control" means, and must never be reported as "we found that the baseline is bad". R1's null FPR may legitimately be 0 at small `d` because the exact test is discrete and conservative; report 0 together with its interval upper bound, never as a "zero error rate". Wilson 95% intervals are the pre-registered comparison device for "significantly lower"; because the null pools of one source pool are not independent, they are read conservatively.

## 5. Exhaustive verdict branches

| Branch | Condition | Recorded verdict |
| --- | --- | --- |
| **(i)** | R1's FPR is significantly lower than R2's and R7's (non-overlapping Wilson 95% intervals) **and** R1's TPR is not lower than theirs | "gate value established" |
| **(ii)** | (i) not met, but R1's FPR@k curve is significantly flatter than R2's / R7's | "value established under selection pressure" |
| **(iii)** | neither (i) nor (ii) | "not established"; the novelty score is **not** raised |

The three branches are exhaustive by construction; the recorded branch is written into `results/rounds/round5/ablation.json` as `verdict_branch`. Branch (iii) leaves the self-assessed novelty score unchanged — an honest negative is a permitted and reportable outcome.

## 6. Budget

- **Tasks 1–5 use ZERO model calls.** The pool construction, the seven rules, the ablation, and the audit are pure computation over already-committed run data.
- The optional proposer arm (Task 6) is capped at **400 calls** (`heldout40` × 5 policies × 2). It is optional and must not be a dependency of any other task: if it is not executed it must be recorded as "not executed" and never substituted with other data.

## 7. Pilot evidence (already run — PILOT EVIDENCE, NOT A RESULT)

The following numbers come from a pre-execution mini-pilot run during plan design. They are recorded here **as pilot evidence only, explicitly not as results**, and no claim in the paper may cite them as findings.

- observed marginal pool: `qwen2:7b` `step-calc` vs `concise-reason`, `b=2` `c=4` `d=6`, McNemar `p=0.688`, `gain=-0.050`
- observed positive pool: trackA `cot-zero` vs `direct`, `b=159` `c=0` `d=159`, `p=2.7e-48`, `gain=+0.795`
- permutation null, `K=2000`, mean gain = `-0.0029` (expected ~0)
- pilot FPRs: R1 `0.015`, R2 `0.320`, R6 `0.320`; R7 FPR@k: k=1 `0.357`, k=2 `0.620`, k=4 `0.838`, k=8 `0.968`

Provenance and orientation note (added at Task 0 to make the frozen pilot record auditable — **no value was altered**):

- The marginal record is consistent with `results/rounds/round4/trackC-qwen2-7b-heldout40.json`, which stores `step-calc_vs_concise-reason` as `better=4, worse=2, p=0.6875, gain=+0.05` over `n=40`. That is the **same pool in the reverse orientation**: with `concise-reason` as challenger and `step-calc` as incumbent, `b=2, c=4, d=6, gain=(2-4)/40=-0.050`. The two records agree on `d=6` and `p=0.688`; only the orientation differs. Task 1/3 must therefore record each pool's orientation explicitly (see §1), and Task 4 must state which orientation each reported decision uses.
- The positive record matches `results/rounds/round4/trackA-merged.json` (`direct_vs_cot-zero`: `better=159, worse=0, p=2.7369110631344083e-48, gain=0.795`, `n=200`).
- The `K=2000` mean-null-gain and pilot FPR figures come from the design-validation block of `paper/PLAN-NOVELTY.md`; no pilot artefact was written to disk, so these figures are **not independently recomputable from a committed artefact** and are treated as design evidence only. The deliverable run (K=200, Task 4) must recompute every reported metric from `pools.json`, and its numbers — not these — are the ones that may be reported.
- The pilot's R7 FPR@k at `k=1` (0.357) need not equal the R2 FPR (0.320): the k-curve candidates are built by an independent relabelling draw rather than by reusing the R2 pool. Both values are reported; neither is substituted for the other.

## 8. Design constraint: discordance granularity (binding on Tasks 3 and 4)

At `d = 6` the exact McNemar `p` can only take values `{0.031, 0.219, ...}`, so `alpha = 0.05` and `alpha = 0.20` produce **IDENTICAL decisions** there. Therefore the alpha-sensitivity (R5) and unpaired (R3) arms **MUST be evaluated on large-discordance pools (`d >= 15`)**, e.g. the available `step-calc` vs `cot-zero` (`d=16`), `step-calc` vs `few-shot` (`d=23`), `cot-zero` vs `few-shot` (`d=15`).

Reporting an "alpha has no effect" conclusion from `d = 6` pools alone would be an artefact of the discrete test's granularity, not a finding. Task 3 must therefore include at least one observed pool with `discordant_total >= 15`, and Task 4 must report the R5 and R3 arms on those large-discordance pools (the `d = 6` marginal pool may be reported alongside, clearly separated).

## 9. Boundary statement

We compare decision **PROCEDURES** consistent with published descriptions, **NOT** the actual REMO / SPHERE / TextGrad systems, and no claim of reproducing or beating those systems may be made. The comparison targets idealised decision rules in the sense that each is a published description's decision logic instantiated on our pools; the systems themselves were not re-implemented, downloaded, or run. This boundary must appear in the paper's limitations and must not be weakened in the abstract or the introduction whatever verdict branch (§5) is recorded.
