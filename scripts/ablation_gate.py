"""Task 4: the ablation main experiment — FPR / TPR / FPR@k per rule + frozen verdict device.

Authoritative protocol: ``results/rounds/round5/PREREG-round5.md`` (§4 metrics, §5/§5.1/§5.2 the
three exhaustive verdict branches, §5A R4's status).  This module is pure computation over the
committed pool artefact: it makes ZERO model calls, reads the pools only through the published
loader ``build_pools.load_pools_json()``, decides every rule only through the published
``gate_rules.decide(rule, pool)``, and regenerates R7's candidates only through the published
candidate streams ``build_pools.iter_null_candidate_blocks`` / ``build_pools.positive_candidate_blocks``
(never from an embedded copy).  No number is hard-coded; every figure below is recomputed from the
pool rows.

What this runs and reports (frozen §4 / §5):

1. Per rule (R1, R2, R3, R4, R5, R6, R7): FPR over NULL pools and TPR over POSITIVE pools.
   Because the nulls of one source pool are NOT independent Bernoulli trials (Ruling 8), FPR is
   reported per source pool AND pooled, with Wilson 95% intervals on the pooled figure.
2. The FPR@k curve of R7 (k = 1..8, descriptive) with the pinned k = 8 endpoint (operative) —
   the term used by branch (ii).
3. R4's row computed, reported with the §5A framing: the R1-vs-R4 contrast is definitional (R1
   refuses every non-blind pool by construction), the denominator is exactly 6, and no R4 FPR
   may be claimed.
4. The verdict: branches (i)/(ii)/(iii) evaluated exactly per §5.1/§5.2, including the paired
   exact McNemar agreement on branch (i) with the stated ``(source_pool, null_index)`` pairing
   unit, clause (c) as a sanity guard with its no-discriminating-power disclosure, and the
   branch (ii) point-below-lower-bound test at k = 8.  Output is a single ``verdict_branch``
   value in {``"i"``, ``"ii"``, ``"iii"``} plus the supporting figures.
5. Every reported row carries the declared ``(chal_policy, inc_policy)`` orientation it was
   computed in (Ruling 20).

Notes on the branch (ii) notation (binding, quoted so the reading is auditable): §5.1 branch (ii)
writes ``FPR@8(R1) < WilsonLower95(FPR@8(R2)) and FPR@8(R1) < WilsonLower95(FPR@8(R7))``.  R1 and
R2 have no ``k``: their FPR is a single-pool decision with no selection-pressure candidates, so
``FPR@8(R1)`` = ``FPR(R1)`` and ``FPR@8(R2)`` = ``FPR(R2)`` are the two k-independent terms, and
only ``FPR@8(R7)`` is the k-dependent pinned ``k = 8`` quantity ``FPR_R7@8`` (§5.2).  Because
branch (i) is met here, the verdict is ``"i"`` regardless of the branch (ii) comparison (it is
computed and reported for completeness only).
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.build_pools as bp          # noqa: E402
import scripts.gate_rules as gr           # noqa: E402
from evokit.stats import mcnemar_two_sided  # noqa: E402

OUT = bp.ROUND5 / "ablation.json"

RULES = ("R1", "R2", "R3", "R4", "R5", "R6", "R7")
NULL_SOURCE_INDICES = bp.DECLARED_NULL_SOURCES          # (0, 1, 2, 3)
NONBLIND_INDICES = bp.NOT_NULL_SOURCES                  # (4, ..., 9)
ALPHA = gr.ALPHA
K_R7 = gr.K_R7

# The 97.5th percentile of the standard normal distribution — the ``z`` of the Wilson 95% score
# interval.  Pin it as a constant so the interval is byte-recomputable.
Z = 1.959963984540054


# ----------------------------------------------------------------- coefficients / helpers

def wilson_interval(x: int, n: int):
    """Wilson 95% score interval (lower, upper) for a proportion with numerator ``x``, denom ``n``."""
    if n <= 0:
        raise ValueError(f"wilson_interval: denominator must be positive, got {n!r}")
    p = x / n
    z2 = Z * Z
    denom = 1.0 + z2 / n
    centre = p + z2 / (2.0 * n)
    half = Z * math.sqrt(p * (1.0 - p) / n + z2 / (4.0 * n * n))
    return (centre - half) / denom, (centre + half) / denom


def tie_probability(d: int) -> float:
    """``P(tie) = C(d, d/2) / 2^d`` for even ``d``, 0 for odd ``d`` (PREREG §4.1)."""
    if d % 2 == 1:
        return 0.0
    return math.comb(d, d // 2) / (2 ** d)


def r2_null_expectation(d: int) -> float:
    """``E[FPR_R2] = (1 - P(tie)) / 2`` — constructive, not a measurement (PREREG §4.1)."""
    return (1.0 - tie_probability(d)) / 2.0


def pair_orientation(pool: dict) -> dict:
    """The ``(chal_policy, inc_policy)`` declaration of one pool row (Ruling 20)."""
    return {"chal_policy": pool["chal_policy"], "inc_policy": pool["inc_policy"]}


def _best_of_k_gain(cands, k) -> float:
    """The point-estimate best gain over the first ``k`` candidates (prefix ``j = 1..k``)."""
    return max(gr._gain(c) for c in cands[:k])


# --------------------------------------------------------------------------- pool assembly

def _unit_candidates_blocks(source_pool: dict):
    """``(i, [(j, candidate)])`` blocks of the NULL-family stream for one null source pool.

    The stream is generated once per source pool (it is deterministic and pinned); units are
    grouped by ``unit_index = i`` so the ``k``-subset of each unit is the literal prefix
    ``j = 1..k`` of the SAME nested stream (§1 rule 5, §4).  Never an embedded copy.
    """
    by_unit = {}
    for i, j, cand in bp.iter_null_candidate_blocks(source_pool):
        by_unit.setdefault(i, []).append(cand)
    return by_unit


def main() -> int:
    pools = bp.load_pools_json()                       # {"meta","pools"} -> pools (published loader)
    observed = [p for p in pools if p["truth"] == "observed"]
    nulls = [p for p in pools if p["truth"] == "null"]
    obs_by_index = {p["meta"]["source_pool_index"]: p for p in observed}

    n_null = len(nulls)
    assert n_null == bp.K * len(NULL_SOURCE_INDICES) == 800, n_null

    # null pool -> (source_index, null_index), and the R2 null-pool decisions (one decision per
    # unit for branch (i) clause (b)'s R2 comparison).
    null_key = []                                       # parallel to `nulls`
    r1_dec = {}                                         # (idx, null_index) -> bool
    r2_dec = {}
    for p in nulls:
        idx = p["meta"]["source_pool_index"]
        i = p["meta"]["null_index"]
        null_key.append((idx, i))
        r1_dec[(idx, i)] = gr.decide("R1", p)["promote"]
        r2_dec[(idx, i)] = gr.decide("R2", p)["promote"]

    # ---------------------------------------------------------------- per-rule FPR (pooled)
    # The pooled FPR aggregates four null sources, each with its own declared orientation; the
    # pooled row therefore carries the four (chal_policy, inc_policy) pairs explicitly (Ruling 20).
    pooled_orientations = [
        pair_orientation(obs_by_index[idx]) for idx in NULL_SOURCE_INDICES]
    pooled = {}
    for rule in ("R1", "R2", "R3", "R4", "R5", "R6"):
        promoted = sum(1 for p in nulls if gr.decide(rule, p)["promote"])
        lo, hi = wilson_interval(promoted, n_null)
        row = {
            "promoted": promoted,
            "total": n_null,
            "rate": promoted / n_null,
            "wilson95_lower": lo,
            "wilson95_upper": hi,
            "orientations": pooled_orientations,
            "orientation_note": ("the pooled rate aggregates the four declared blind null sources; "
                                 "each null pool is decided in its OWN declared (chal_policy, "
                                 "inc_policy) orientation, listed in 'orientations' (Ruling 20)"),
        }
        if rule == "R4":
            # §5A: R4's arm is the non-blind per-pool decision set (denominator 6), NOT an FPR.
            # The R4 entries in THIS table are the rule evaluated on the *blind* null set, where
            # R4's blindness requirement is vacuous and it therefore coincides with R1.  This
            # number is not the §5A "R4 FPR" (a non-blind null set does not exist and none is
            # invented); the §5A R4 column is reported in the separate ``r4`` block below.
            row["note"] = (
                "R4 evaluated on the BLIND null set (blindness requirement vacuous -> coincides "
                "with R1). This is NOT the §5A 'R4 FPR' over a non-blind null set: no non-blind "
                "null set exists and no R4 FPR is claimed (§5A); the §5A R4 column (denominator 6) "
                "is the 'r4' block below.")
        pooled[rule] = row

    # ---------------------------------------------------------------- R7 FPR@k curve + @8
    # For each null source pool, draw the candidate stream once and group by unit.  Then decide
    # R7 over the first k candidates, k = 1..8.  The k = 8 endpoint is the operative FPR_R7@8.
    curve_counts = {k: 0 for k in range(1, K_R7 + 1)}
    r7_at8_dec = {}                                    # (idx, null_index) -> R7@8 promote (branch b)
    unit_orientations = []
    for idx in NULL_SOURCE_INDICES:
        sp = obs_by_index[idx]
        unit_orientations.append(pair_orientation(sp))
        units = _unit_candidates_blocks(sp)
        assert len(units) == bp.K, (idx, len(units))
        for i in range(bp.K):
            cands = units[i]
            assert len(cands) == K_R7
            gains = [gr._gain(c) for c in cands]
            for k in range(1, K_R7 + 1):
                if max(gains[:k]) > 0:
                    curve_counts[k] += 1
            r7_at8_dec[(idx, i)] = max(gains[:K_R7]) > 0

    k_curve = {}
    for k in range(1, K_R7 + 1):
        x = curve_counts[k]
        lo, hi = wilson_interval(x, n_null)
        k_curve[str(k)] = {
            "k": k,
            "promoted_units": x,
            "total_units": n_null,
            "fpr_at_k": x / n_null,
            "wilson95_lower": lo,
            "wilson95_upper": hi,
            "operative": k == K_R7,
            "role": ("pinned k = 8 endpoint — FPR_R7@8, the operative R7 statistic of §5.1/§5.2"
                     if k == K_R7 else "descriptive curve point; NOT a decision device (§4)"),
            "orientations": unit_orientations,
        }
    fpr_r7_at8 = k_curve[str(K_R7)]["fpr_at_k"]

    pooled["R7"] = {
        "promoted": curve_counts[K_R7],
        "total": n_null,
        "rate": fpr_r7_at8,
        "wilson95_lower": k_curve[str(K_R7)]["wilson95_lower"],
        "wilson95_upper": k_curve[str(K_R7)]["wilson95_upper"],
        "k": K_R7,
        "orientations": pooled_orientations,
        "orientation_note": ("FPR_R7@8 = FPR@8(R7): bestofk FPR at the pinned k=8 over the "
                             "NULL-family relabelling candidates (§5.2), decided per null unit in "
                             "its source pool's declared orientation"),
    }

    # ------------------------------------------------------------ per-source-pool FPR
    per_source = []
    for idx in NULL_SOURCE_INDICES:
        sp = obs_by_index[idx]
        sub = [p for p in nulls if p["meta"]["source_pool_index"] == idx]
        d = sp["meta"]["discordant_total"]
        row = {
            "source_pool": sp["name"],
            "source_pool_index": idx,
            "n_null": len(sub),
            "d": d,
            "r2_null_expectation": r2_null_expectation(d),
            "chal_policy": sp["chal_policy"],
            "inc_policy": sp["inc_policy"],
            "rules": {},
        }
        for rule in ("R1", "R2", "R3", "R4", "R5", "R6"):
            promoted = sum(1 for p in sub if gr.decide(rule, p)["promote"])
            lo, hi = wilson_interval(promoted, len(sub))
            row["rules"][rule] = {
                "promoted": promoted, "total": len(sub), "rate": promoted / len(sub),
                "wilson95_lower": lo, "wilson95_upper": hi,
            }
        # R7 per-source at the pinned k=8 (per unit over that source pool's own candidates)
        r7_promoted = sum(1 for i in range(bp.K) if r7_at8_dec[(idx, i)])
        lo, hi = wilson_interval(r7_promoted, bp.K)
        row["rules"]["R7"] = {
            "promoted": r7_promoted, "total": bp.K, "rate": r7_promoted / bp.K,
            "wilson95_lower": lo, "wilson95_upper": hi, "k": K_R7,
        }
        per_source.append(row)

    # R2 pooled tie-corrected expectation (size-weighted mean over the four sources, §4.1)
    pooled_expectation = sum(
        r2_null_expectation(obs_by_index[idx]["meta"]["discordant_total"]) * bp.K
        for idx in NULL_SOURCE_INDICES) / n_null

    # --------------------------------------------------------------------- POSITIVE / TPR
    positive = obs_by_index[bp.POSITIVE_SOURCE_INDEX]
    positive_candidates = bp.positive_candidate_blocks(positive)      # label-preserving bootstrap
    positive_r7 = dict(positive)
    positive_r7["candidates"] = positive_candidates

    tpr = {}
    for rule in ("R1", "R2", "R3", "R4", "R5", "R6"):
        promoted = 1 if gr.decide(rule, positive)["promote"] else 0
        tpr[rule] = {
            "promoted": promoted,
            "total": 1,
            "rate": float(promoted),
            "chal_policy": positive["chal_policy"],
            "inc_policy": positive["inc_policy"],
            "denominator": 1,
        }
    tpr_r7_promote = bool(gr.decide("R7", positive_r7)["promote"])
    tpr["R7"] = {
        "promoted": 1 if tpr_r7_promote else 0,
        "total": 1,
        "rate": 1.0 if tpr_r7_promote else 0.0,
        "chal_policy": positive["chal_policy"],
        "inc_policy": positive["inc_policy"],
        "k": K_R7,
        "candidate_family": "POSITIVE (label-preserving item bootstrap, §1 rule 5 / §5.2)",
        "denominator": 1,
    }

    # ------------------------------------------------------------------------ R4 (§5A)
    r4_per_pool = []
    for idx in NONBLIND_INDICES:
        p = obs_by_index[idx]
        r4 = gr.decide("R4", p)
        r1 = gr.decide("R1", p)
        r4_per_pool.append({
            "roster_index": idx,
            "pool": p["name"],
            "chal_policy": p["chal_policy"],
            "inc_policy": p["inc_policy"],
            "n": p["n"],
            "gain": r4["gain"],
            "exact_mcnemar_p": r4["p"],
            "R4_promote": r4["promote"],
            "R1_promote": r1["promote"],
        })
    r4 = {
        "per_pool": r4_per_pool,
        "promoted": sum(1 for r in r4_per_pool if r["R4_promote"]),
        "total": len(r4_per_pool),
        "r1_by_construction_refuses_all": all(not r["R1_promote"] for r in r4_per_pool),
        "r1_vs_r4_contrast_is_definitional": True,
        "no_r4_fpr_is_claimed": True,
        "denominator": len(r4_per_pool),
        "framing": (
            "R4 is EVALUATED on the six non-blind selection-set pools of roster indices 4-9 (§5A). "
            "The R1-vs-R4 contrast is DEFINITIONAL: R1 requires pool['blind'] is True, so it "
            "refuses all six non-blind pools by construction — a definitional consequence, not a "
            "finding. The denominator is exactly 6 per-pool decisions; there is no non-blind null "
            "set, so no R4 FPR may be claimed (§5A). These selection-set decisions carry no "
            "generalisation claim."
        ),
        "reconciled_with": {
            "r4_status": bp.pools_meta(pools)["r4_status"],
            "r4_evaluable": bp.pools_meta(pools)["r4_evaluable"],
        },
    }

    # --------------------------------------------------------------------- verdict device
    n = n_null
    fpr_r1 = pooled["R1"]["rate"]
    fpr_r2 = pooled["R2"]["rate"]
    w_r1 = (pooled["R1"]["wilson95_lower"], pooled["R1"]["wilson95_upper"])
    w_r2 = (pooled["R2"]["wilson95_lower"], pooled["R2"]["wilson95_upper"])
    w_r7 = (pooled["R7"]["wilson95_lower"], pooled["R7"]["wilson95_upper"])

    # clause (a): intervals disjoint, R1 below
    clause_a = (w_r1[1] < w_r2[0], w_r1[1] < w_r7[0])

    # clause (b): paired exact McNemar agreement on pairing unit (source_pool, null_index)
    def paired_mcnemar(comparison_dec: dict, want_r1_below: bool, baseline_name: str) -> dict:
        b = 0   # units where R1 promotes and the baseline does not
        c = 0   # units where the baseline promotes and R1 does not
        for (idx, i) in r1_dec:
            v1 = int(r1_dec[(idx, i)])
            v2 = int(comparison_dec[(idx, i)])
            if v1 and not v2:
                b += 1
            elif (not v1) and v2:
                c += 1
        # "same direction" as clause (a): R1 below -> the baseline promotes more -> c > b
        direction_consistent = (c > b) if want_r1_below else (b > c)
        p = mcnemar_two_sided(b, c)
        return {
            "baseline": baseline_name,
            "n_paired_units": len(r1_dec),
            "r1_only_b": b,
            "baseline_only_c": c,
            "direction_consistent": direction_consistent,
            "exact_two_sided_p": p,
            "p_lt_alpha": p < ALPHA,
            "agrees": direction_consistent and (p < ALPHA),
        }
    mcn_r2 = paired_mcnemar(r2_dec, True, "R2")
    mcn_r7 = paired_mcnemar(r7_at8_dec, True, "R7@8")
    clause_b = (mcn_r2["agrees"], mcn_r7["agrees"])

    # clause (c): sanity guard, no discriminating power at denominator 1
    tpr_r1 = tpr["R1"]["rate"]
    tpr_r2 = tpr["R2"]["rate"]
    tpr_r7 = tpr["R7"]["rate"]
    clause_c = (tpr_r1 >= tpr_r2, tpr_r1 >= tpr_r7)

    branch_i = all([*clause_a, *clause_b, *clause_c])

    # branch (ii): point-below-lower-bound at k = 8 (moot when (i) holds, computed for the record)
    fpr_at_8_r1 = fpr_r1                                   # R1 has no k: FPR@8(R1) = FPR(R1)
    fpr_at_8_r2 = fpr_r2                                   # R2 has no k: FPR@8(R2) = FPR(R2)
    branch_ii = (not branch_i) and (fpr_at_8_r1 < w_r2[0]) and (fpr_at_8_r1 < w_r7[0])

    if branch_i:
        verdict_branch = "i"
    elif branch_ii:
        verdict_branch = "ii"
    else:
        verdict_branch = "iii"

    verdict = {
        "null_set": {
            "n_null": n_null,
            "sources": [obs_by_index[i]["name"] for i in NULL_SOURCE_INDICES],
            "independence_note": ("the 200 permutation nulls of one source pool share that pool's "
                                  "questions and are NOT independent Bernoulli trials (Ruling 8); "
                                  "Wilson intervals are read conservatively"),
        },
        "branch_i": {
            "met": branch_i,
            "clause_a_intervals_disjoint_r1_below": {
                "met": bool(clause_a[0] and clause_a[1]),
                "wilson_upper_r1": w_r1[1],
                "wilson_lower_r2": w_r2[0],
                "wilson_lower_r7at8": w_r7[0],
                "r1_below_r2": bool(clause_a[0]),
                "r1_below_r7at8": bool(clause_a[1]),
            },
            "clause_b_paired_mcnemar_agrees": {
                "met": bool(clause_b[0] and clause_b[1]),
                "pairing_unit": "(source_pool, null_index)",
                "r2_comparison": mcn_r2,
                "r7at8_comparison": mcn_r7,
            },
            "clause_c_no_true_positive_loss": {
                "met": bool(clause_c[0] and clause_c[1]),
                "tpr_r1": tpr_r1, "tpr_r2": tpr_r2, "tpr_r7at8": tpr_r7,
                "denominator": 1,
                "no_discriminating_power": True,
                "disclosure": ("the POSITIVE set contains exactly one pool, so every TPR here is a "
                               "single 0/1 decision over denominator 1; clause (c) is an "
                               "anti-vacuity sanity guard only and MUST NOT be reported as evidence "
                               "that R1 outperforms R2 or R7 on TPR (§5.1(c))"),
            },
        },
        "branch_ii": {
            "met": branch_ii,
            "note": ("if branch (i) is met the verdict is (i) regardless of the FPR@8 comparison "
                     "(§5.1 branch (ii)); computed for completeness"),
            "fpr_at_8_r1": fpr_at_8_r1,
            "fpr_at_8_r2": fpr_at_8_r2,
            "fpr_at_8_r7": fpr_r7_at8,
            "wilson_lower_r2": w_r2[0],
            "wilson_lower_r7at8": w_r7[0],
            "r1_below_r2_lower": fpr_at_8_r1 < w_r2[0],
            "r1_below_r7at8_lower": fpr_at_8_r1 < w_r7[0],
        },
        "verdict_branch": verdict_branch,
        "verdict_meaning": {
            "i": "gate value established",
            "ii": "value established under selection pressure",
            "iii": "not established; novelty score not raised",
        }[verdict_branch],
    }

    result = {
        "schema_version": 1,
        "generated_by": "scripts/ablation_gate.py",
        "prereg": "results/rounds/round5/PREREG-round5.md",
        "pools_artefact": "results/rounds/round5/pools.json",
        "zero_model_calls": True,
        "orientation_convention": ("chal = the candidate being promoted; inc = the incumbent; "
                                   "gain = (total_chal - total_inc)/n; every row declares "
                                   "(chal_policy, inc_policy) (PREREG §1.1, Ruling 20)"),
        "r2_null_expectation_note": ("E[FPR_R2] = (1 - P(tie))/2 is CONSTRUCTIVE — what 'no error "
                                     "control' means — never reported as a finding (PREREG §4.1)"),
        "fpr": {
            "pooled": pooled,
            "pooled_r2_null_expectation": pooled_expectation,
            "per_source_pool": per_source,
            "r4_note": ("R4 appears twice with distinct meanings. (1) In this FPR table, R4 is the "
                        "rule evaluated on the 800 BLIND null pools, where its blindness requirement "
                        "is vacuous and it therefore coincides with R1 — this is NOT the §5A 'R4 "
                        "FPR'. (2) The §5A R4 column — the six non-blind selection-set per-pool "
                        "decisions, denominator 6, with NO FPR claimed — is the 'r4' block below."),
        },
        "tpr": tpr,
        "k_curve": k_curve,
        "fpr_r7_at8": fpr_r7_at8,
        "r4": r4,
        "verdict": verdict,
        "verdict_branch": verdict_branch,
    }

    # Defensive self-consistency: the recorded branch must be one of the exhaustive three, and the
    # pooled R1/R2/R7@8 rates must reproduce the branch (i)/(ii) comparison inputs verbatim.
    assert verdict_branch in ("i", "ii", "iii")
    assert abs(pooled["R1"]["rate"] - fpr_r1) < 1e-15
    assert abs(pooled["R2"]["rate"] - fpr_r2) < 1e-15
    assert abs(pooled["R7"]["rate"] - fpr_r7_at8) < 1e-15

    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")

    _print_summary(result)
    return 0


# --------------------------------------------------------------------------- human summary

def _print_summary(result: dict) -> None:
    fpr = result["fpr"]["pooled"]
    print("=" * 78)
    print("round5 ablation — per-rule FPR (pooled over 800 blind nulls) + Wilson 95%")
    for rule in RULES:
        r = fpr[rule]
        lo = r.get("wilson95_lower"); hi = r.get("wilson95_upper")
        k = f" (k={r['k']})" if "k" in r else ""
        print(f"  {rule:3s}{k:7s} FPR = {r['promoted']:3d}/{r['total']} = {r['rate']:.5f}  "
              f"Wilson95 [{lo:.5f}, {hi:.5f}]")
    print(f"  R2 pooled null expectation (tie-corrected) = {result['fpr']['pooled_r2_null_expectation']:.5f}")
    print("-" * 78)
    print("per-source-pool FPR (each source pool contributes exactly 200 nulls):")
    for row in result["fpr"]["per_source_pool"]:
        parts = [f"{rule}={row['rules'][rule]['promoted']}/{row['rules'][rule]['total']}"
                 for rule in RULES]
        print(f"  {row['source_pool']} (d={row['d']}, {row['chal_policy']} vs {row['inc_policy']})")
        print(f"     " + "  ".join(parts))
    print("-" * 78)
    print("R7 FPR@k curve (descriptive k=1..7; k=8 pinned operative):")
    for k in range(1, K_R7 + 1):
        row = result["k_curve"][str(k)]
        print(f"  k={k}  FPR@k = {row['fpr_at_k']:.5f}  ({row['promoted_units']}/800)  "
              f"{'<-- OPERATIVE (FPR_R7@8)' if row['operative'] else ''}")
    print("-" * 78)
    print("TPR (POSITIVE pool = cot-zero vs direct, denominator = 1; no discriminating power):")
    for rule in RULES:
        print(f"  {rule:3s} TPR = {result['tpr'][rule]['promoted']}/{result['tpr'][rule]['total']}")
    print("-" * 78)
    print("R4 (non-blind selection set, 6 pools, indices 4-9; NO FPR claimed):")
    for row in result["r4"]["per_pool"]:
        print(f"  idx{row['roster_index']} {row['pool']:34s} ({row['chal_policy']} vs "
              f"{row['inc_policy']}) gain={row['gain']:+.3f} p={row['exact_mcnemar_p']:.6g} "
              f"R4={'PROMOTE' if row['R4_promote'] else 'refuse'}  "
              f"R1={'refuse (definitional)' if not row['R1_promote'] else 'promote'}")
    print(f"  R4 promoted = {result['r4']['promoted']}/{result['r4']['total']}")
    print("-" * 78)
    v = result["verdict"]
    print(f"verdict_branch = {result['verdict_branch']!r}  ({v['verdict_meaning']})")
    print(f"  clause (a) intervals disjoint, R1 below: {v['branch_i']['clause_a_intervals_disjoint_r1_below']['met']}")
    print(f"  clause (b) paired McNemar agrees (both): {v['branch_i']['clause_b_paired_mcnemar_agrees']['met']}")
    print(f"     R2 : p={v['branch_i']['clause_b_paired_mcnemar_agrees']['r2_comparison']['exact_two_sided_p']:.3g} "
          f"dir_ok={v['branch_i']['clause_b_paired_mcnemar_agrees']['r2_comparison']['direction_consistent']}")
    print(f"     R7@8: p={v['branch_i']['clause_b_paired_mcnemar_agrees']['r7at8_comparison']['exact_two_sided_p']:.3g} "
          f"dir_ok={v['branch_i']['clause_b_paired_mcnemar_agrees']['r7at8_comparison']['direction_consistent']}")
    print(f"  clause (c) R1 does not lose true positives: {v['branch_i']['clause_c_no_true_positive_loss']['met']}")
    print(f"  branch (ii) [moot, (i) holds] would also hold: {v['branch_ii']['r1_below_r2_lower'] and v['branch_ii']['r1_below_r7at8_lower']}")
    print("=" * 78)
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    raise SystemExit(main())