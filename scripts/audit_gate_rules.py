"""Task 5: the independent audit that closes the reproducibility loop.

Authoritative protocol: ``results/rounds/round5/PREREG-round5.md`` (S4 ``recomputability``
metric, S5/S5.1/S5.2 the verdict device) and ``paper/PLAN-NOVELTY.md`` Task 5.

This module is an **independent re-derivation**, not a re-run of ``scripts/ablation_gate.py``:
it never imports that module, and it never reads a single answer from ``ablation.json`` to
*produce* a figure.  Every number below is recomputed from the committed evidence:

* the pools are read only through the published loader ``build_pools.load_pools_json()``
  (which re-verifies the artefact description, the blind-label consistency, and the
  byte-stability of roster indices 0-3), never as a bare ``json.loads``;
* every rule decision is made only through the published ``gate_rules.decide(rule, pool)``;
* R7's candidates are regenerated on the fly only through the published candidate streams
  ``build_pools.iter_null_candidate_blocks`` (NULL family) and
  ``build_pools.positive_candidate_blocks`` (POSITIVE family) -- never from any embedded copy or
  serialised snapshot;
* the Wilson interval, the tie correction, the pooled null expectation, the paired exact McNemar
  agreement and the three-grade verdict device are all recomputed here from the pool rows.

``ablation.json`` is read **only** as the committed reference to compare against.  The audit
exits 0 iff every recomputed figure -- the per-rule pooled and per-source-pool FPR (headline
promoted/rate plus the Wilson endpoints), the TPR values, the FPR@8 endpoint, ``verdict_branch``,
and the Wilson + McNemar agreement fields of the verdict device -- equals the committed value.
On ANY mismatch it prints the field, the committed value and the recomputed value, and exits
non-zero, so a drifted artefact cannot pass.  This is what makes the "recomputability" metric of
PREREG S4 a real gate rather than a decoration (the bite is proven by
``tests/test_audit_gate_rules.py``).
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

ABLATION = bp.ROUND5 / "ablation.json"
POOLS = bp.ROUND5 / "pools.json"

RULES = ("R1", "R2", "R3", "R4", "R5", "R6", "R7")
NULL_SOURCE_INDICES = bp.DECLARED_NULL_SOURCES          # (0, 1, 2, 3)
NONBLIND_INDICES = bp.NOT_NULL_SOURCES                  # (4, ..., 9)
ALPHA = gr.ALPHA
K_R7 = gr.K_R7

# The 97.5th percentile of the standard normal distribution -- the ``z`` of the Wilson 95% score
# interval.  Identical constant to the one the committed artefact was produced with, so the Wilson
# endpoints recompute byte-identically.
Z = 1.959963984540054


def wilson_interval(x: int, n: int):
    """Wilson 95% score interval ``(lower, upper)`` for a proportion with numerator ``x``, denom ``n``."""
    if n <= 0:
        raise ValueError(f"wilson_interval: denominator must be positive, got {n!r}")
    p = x / n
    z2 = Z * Z
    denom = 1.0 + z2 / n
    centre = p + z2 / (2.0 * n)
    half = Z * math.sqrt(p * (1.0 - p) / n + z2 / (4.0 * n * n))
    return (centre - half) / denom, (centre + half) / denom


def tie_probability(d: int) -> float:
    """``P(tie) = C(d, d/2) / 2^d`` for even ``d``, 0 for odd ``d`` (PREREG S4.1)."""
    if d % 2 == 1:
        return 0.0
    return math.comb(d, d // 2) / (2 ** d)


def r2_null_expectation(d: int) -> float:
    """``E[FPR_R2] = (1 - P(tie)) / 2`` -- constructive, not a measurement (PREREG S4.1)."""
    return (1.0 - tie_probability(d)) / 2.0


def _unit_candidates_blocks(source_pool: dict):
    """``{unit_index: [candidate, ...]}`` of the NULL-family candidate stream, regenerated live."""
    by_unit = {}
    for i, j, cand in bp.iter_null_candidate_blocks(source_pool):
        by_unit.setdefault(i, []).append(cand)
    return by_unit


def _decide_r7_with_candidates(pool: dict, cands: list) -> bool:
    """R7``bestofk`` over ``cands``, decided through the canonical ``gate_rules.decide`` path."""
    wrapped = dict(pool)
    wrapped["candidates"] = cands
    return bool(gr.decide("R7", wrapped)["promote"])


def recompute(pools: list) -> dict:
    """Re-derive every auditable figure from the pool rows (never from ablation.json)."""
    observed = [p for p in pools if p["truth"] == "observed"]
    nulls = [p for p in pools if p["truth"] == "null"]
    obs_by_index = {p["meta"]["source_pool_index"]: p for p in observed}

    n_null = len(nulls)
    assert n_null == bp.K * len(NULL_SOURCE_INDICES) == 800, n_null

    # null pool -> (source_index, null_index), plus the R1/R2 decisions per unit (branch (i) b).
    r1_dec = {}
    r2_dec = {}
    for p in nulls:
        idx = p["meta"]["source_pool_index"]
        i = p["meta"]["null_index"]
        r1_dec[(idx, i)] = gr.decide("R1", p)["promote"]
        r2_dec[(idx, i)] = gr.decide("R2", p)["promote"]

    pooled_orientations = [
        {"chal_policy": obs_by_index[idx]["chal_policy"],
         "inc_policy": obs_by_index[idx]["inc_policy"]}
        for idx in NULL_SOURCE_INDICES]

    pooled = {}
    for rule in ("R1", "R2", "R3", "R4", "R5", "R6"):
        promoted = sum(1 for p in nulls if gr.decide(rule, p)["promote"])
        lo, hi = wilson_interval(promoted, n_null)
        pooled[rule] = {
            "promoted": promoted, "total": n_null, "rate": promoted / n_null,
            "wilson95_lower": lo, "wilson95_upper": hi,
        }

    # R7 FPR@k curve + pinned k=8 endpoint (operative), decided via decide("R7", ...).
    curve_counts = {k: 0 for k in range(1, K_R7 + 1)}
    r7_at8_dec = {}
    unit_orientations = []
    for idx in NULL_SOURCE_INDICES:
        sp = obs_by_index[idx]
        unit_orientations.append(
            {"chal_policy": sp["chal_policy"], "inc_policy": sp["inc_policy"]})
        units = _unit_candidates_blocks(sp)
        assert len(units) == bp.K, (idx, len(units))
        for i in range(bp.K):
            cands = units[i]
            assert len(cands) == K_R7, (idx, i, len(cands))
            for k in range(1, K_R7 + 1):
                if _decide_r7_with_candidates(sp, cands[:k]):
                    curve_counts[k] += 1
            r7_at8_dec[(idx, i)] = _decide_r7_with_candidates(sp, cands[:K_R7])

    k_curve = {}
    for k in range(1, K_R7 + 1):
        x = curve_counts[k]
        lo, hi = wilson_interval(x, n_null)
        k_curve[str(k)] = {
            "k": k, "promoted_units": x, "total_units": n_null, "fpr_at_k": x / n_null,
            "wilson95_lower": lo, "wilson95_upper": hi, "operative": k == K_R7,
        }
    fpr_r7_at8 = k_curve[str(K_R7)]["fpr_at_k"]

    pooled["R7"] = {
        "promoted": curve_counts[K_R7], "total": n_null, "rate": fpr_r7_at8,
        "wilson95_lower": k_curve[str(K_R7)]["wilson95_lower"],
        "wilson95_upper": k_curve[str(K_R7)]["wilson95_upper"], "k": K_R7,
    }

    # per-source-pool FPR
    per_source = []
    for idx in NULL_SOURCE_INDICES:
        sp = obs_by_index[idx]
        sub = [p for p in nulls if p["meta"]["source_pool_index"] == idx]
        d = sp["meta"]["discordant_total"]
        row = {
            "source_pool": sp["name"], "source_pool_index": idx,
            "d": d, "r2_null_expectation": r2_null_expectation(d), "rules": {},
        }
        for rule in ("R1", "R2", "R3", "R4", "R5", "R6"):
            promoted = sum(1 for p in sub if gr.decide(rule, p)["promote"])
            lo, hi = wilson_interval(promoted, len(sub))
            row["rules"][rule] = {
                "promoted": promoted, "total": len(sub), "rate": promoted / len(sub),
                "wilson95_lower": lo, "wilson95_upper": hi,
            }
        r7_promoted = sum(1 for i in range(bp.K) if r7_at8_dec[(idx, i)])
        lo, hi = wilson_interval(r7_promoted, bp.K)
        row["rules"]["R7"] = {
            "promoted": r7_promoted, "total": bp.K, "rate": r7_promoted / bp.K,
            "wilson95_lower": lo, "wilson95_upper": hi, "k": K_R7,
        }
        per_source.append(row)

    pooled_expectation = sum(
        r2_null_expectation(obs_by_index[idx]["meta"]["discordant_total"]) * bp.K
        for idx in NULL_SOURCE_INDICES) / n_null

    # POSITIVE / TPR
    positive = obs_by_index[bp.POSITIVE_SOURCE_INDEX]
    positive_r7 = dict(positive)
    positive_r7["candidates"] = bp.positive_candidate_blocks(positive)

    tpr = {}
    for rule in ("R1", "R2", "R3", "R4", "R5", "R6"):
        promoted = 1 if gr.decide(rule, positive)["promote"] else 0
        tpr[rule] = {"promoted": promoted, "total": 1, "rate": float(promoted)}
    tpr["R7"] = {
        "promoted": 1 if gr.decide("R7", positive_r7)["promote"] else 0,
        "total": 1, "rate": 1.0 if gr.decide("R7", positive_r7)["promote"] else 0.0,
        "k": K_R7,
    }
    tpr_r7_promote = tpr["R7"]["promoted"] == 1

    # R4 (S5A): the six non-blind per-pool decisions, denominator 6, no FPR.
    r4_per_pool = []
    for idx in NONBLIND_INDICES:
        p = obs_by_index[idx]
        r4 = gr.decide("R4", p)
        r1 = gr.decide("R1", p)
        r4_per_pool.append({
            "roster_index": idx, "pool": p["name"],
            "chal_policy": p["chal_policy"], "inc_policy": p["inc_policy"], "n": p["n"],
            "gain": r4["gain"], "exact_mcnemar_p": r4["p"],
            "R4_promote": r4["promote"], "R1_promote": r1["promote"],
        })
    meta = bp.pools_meta(pools)
    r4 = {
        "per_pool": r4_per_pool,
        "promoted": sum(1 for r in r4_per_pool if r["R4_promote"]),
        "total": len(r4_per_pool),
        "r1_by_construction_refuses_all": all(not r["R1_promote"] for r in r4_per_pool),
        "r1_vs_r4_contrast_is_definitional": True,
        "no_r4_fpr_is_claimed": True,
        "denominator": len(r4_per_pool),
        "reconciled_with": {"r4_status": meta["r4_status"], "r4_evaluable": meta["r4_evaluable"]},
    }

    # --------------------------------------------------------------------- verdict device
    fpr_r1 = pooled["R1"]["rate"]
    fpr_r2 = pooled["R2"]["rate"]
    w_r1 = (pooled["R1"]["wilson95_lower"], pooled["R1"]["wilson95_upper"])
    w_r2 = (pooled["R2"]["wilson95_lower"], pooled["R2"]["wilson95_upper"])
    w_r7 = (pooled["R7"]["wilson95_lower"], pooled["R7"]["wilson95_upper"])
    clause_a = (w_r1[1] < w_r2[0], w_r1[1] < w_r7[0])

    def paired_mcnemar(comparison_dec, want_r1_below, baseline_name):
        b = 0
        c = 0
        for (idx, i) in r1_dec:
            v1 = int(r1_dec[(idx, i)])
            v2 = int(comparison_dec[(idx, i)])
            if v1 and not v2:
                b += 1
            elif (not v1) and v2:
                c += 1
        direction_consistent = (c > b) if want_r1_below else (b > c)
        p = mcnemar_two_sided(b, c)
        return {
            "baseline": baseline_name, "n_paired_units": len(r1_dec),
            "r1_only_b": b, "baseline_only_c": c,
            "direction_consistent": direction_consistent, "exact_two_sided_p": p,
            "p_lt_alpha": p < ALPHA,
            "agrees": direction_consistent and (p < ALPHA),
        }

    mcn_r2 = paired_mcnemar(r2_dec, True, "R2")
    mcn_r7 = paired_mcnemar(r7_at8_dec, True, "R7@8")
    clause_b = (mcn_r2["agrees"], mcn_r7["agrees"])

    tpr_r1 = tpr["R1"]["rate"]
    tpr_r2 = tpr["R2"]["rate"]
    tpr_r7 = tpr["R7"]["rate"]
    clause_c = (tpr_r1 >= tpr_r2, tpr_r1 >= tpr_r7)

    branch_i = all([*clause_a, *clause_b, *clause_c])
    fpr_at_8_r1 = fpr_r1
    fpr_at_8_r2 = fpr_r2
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
        },
        "branch_i": {
            "met": branch_i,
            "clause_a_intervals_disjoint_r1_below": {
                "met": bool(clause_a[0] and clause_a[1]),
                "wilson_upper_r1": w_r1[1], "wilson_lower_r2": w_r2[0],
                "wilson_lower_r7at8": w_r7[0],
                "r1_below_r2": bool(clause_a[0]), "r1_below_r7at8": bool(clause_a[1]),
            },
            "clause_b_paired_mcnemar_agrees": {
                "met": bool(clause_b[0] and clause_b[1]),
                "r2_comparison": mcn_r2, "r7at8_comparison": mcn_r7,
            },
            "clause_c_no_true_positive_loss": {
                "met": bool(clause_c[0] and clause_c[1]),
                "tpr_r1": tpr_r1, "tpr_r2": tpr_r2, "tpr_r7at8": tpr_r7,
            },
        },
        "branch_ii": {
            "met": branch_ii,
            "fpr_at_8_r1": fpr_at_8_r1, "fpr_at_8_r2": fpr_at_8_r2, "fpr_at_8_r7": fpr_r7_at8,
            "wilson_lower_r2": w_r2[0], "wilson_lower_r7at8": w_r7[0],
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

    return {
        "fpr": {"pooled": pooled, "pooled_r2_null_expectation": pooled_expectation,
                "per_source_pool": per_source},
        "tpr": tpr,
        "k_curve": k_curve,
        "fpr_r7_at8": fpr_r7_at8,
        "r4": r4,
        "verdict": verdict,
        "verdict_branch": verdict_branch,
    }


# ----------------------------------------------------------------- compare (committed vs computed)

def _get(d: dict, path: str):
    """Index a nested dict by a dotted path; list segments are integer indices."""
    cur = d
    for seg in path.split("."):
        if isinstance(cur, list):
            cur = cur[int(seg)]
        else:
            cur = cur[seg]
    return cur


def _is_float(v) -> bool:
    return isinstance(v, float)


def _equal(a, b) -> bool:
    if _is_float(a) or _is_float(b):
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            return math.isclose(float(a), float(b), rel_tol=1e-12, abs_tol=1e-12)
        return False
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_equal(x, y) for x, y in zip(a, b))
    return a == b


def _compare_paths() -> list:
    """The dotted paths of every auditable figure, both numeric and structural."""
    paths = ["verdict_branch", "fpr.pooled_r2_null_expectation", "fpr_r7_at8"]
    for r in RULES:
        for field in ("promoted", "total", "rate", "wilson95_lower", "wilson95_upper"):
            paths.append(f"fpr.pooled.{r}.{field}")
        paths.append(f"tpr.{r}.promoted")
        paths.append(f"tpr.{r}.total")
        paths.append(f"tpr.{r}.rate")
    paths.append("fpr.pooled.R7.k")
    paths.append("tpr.R7.k")
    for i in NULL_SOURCE_INDICES:
        paths.append(f"fpr.per_source_pool.{i}.source_pool")
        paths.append(f"fpr.per_source_pool.{i}.source_pool_index")
        paths.append(f"fpr.per_source_pool.{i}.d")
        paths.append(f"fpr.per_source_pool.{i}.r2_null_expectation")
        for r in RULES:
            for field in ("promoted", "total", "rate", "wilson95_lower", "wilson95_upper"):
                paths.append(f"fpr.per_source_pool.{i}.rules.{r}.{field}")
    for k in range(1, K_R7 + 1):
        for field in ("promoted_units", "total_units", "fpr_at_k"):
            paths.append(f"k_curve.{k}.{field}")
    # verdict device
    paths += [
        "verdict.null_set.n_null",
        "verdict.verdict_branch",
        "verdict.verdict_meaning",
        "verdict.branch_i.met",
        "verdict.branch_i.clause_a_intervals_disjoint_r1_below.met",
        "verdict.branch_i.clause_a_intervals_disjoint_r1_below.r1_below_r2",
        "verdict.branch_i.clause_a_intervals_disjoint_r1_below.r1_below_r7at8",
        "verdict.branch_i.clause_a_intervals_disjoint_r1_below.wilson_upper_r1",
        "verdict.branch_i.clause_a_intervals_disjoint_r1_below.wilson_lower_r2",
        "verdict.branch_i.clause_a_intervals_disjoint_r1_below.wilson_lower_r7at8",
        "verdict.branch_i.clause_b_paired_mcnemar_agrees.met",
        "verdict.branch_i.clause_c_no_true_positive_loss.met",
        "verdict.branch_i.clause_c_no_true_positive_loss.tpr_r1",
        "verdict.branch_i.clause_c_no_true_positive_loss.tpr_r2",
        "verdict.branch_i.clause_c_no_true_positive_loss.tpr_r7at8",
        "verdict.branch_ii.met",
        "verdict.branch_ii.fpr_at_8_r1",
        "verdict.branch_ii.fpr_at_8_r2",
        "verdict.branch_ii.fpr_at_8_r7",
        "verdict.branch_ii.wilson_lower_r2",
        "verdict.branch_ii.wilson_lower_r7at8",
        "verdict.branch_ii.r1_below_r2_lower",
        "verdict.branch_ii.r1_below_r7at8_lower",
    ]
    for comp in ("r2_comparison", "r7at8_comparison"):
        for field in ("agrees", "direction_consistent", "exact_two_sided_p", "p_lt_alpha",
                      "r1_only_b", "baseline_only_c", "n_paired_units"):
            paths.append(f"verdict.branch_i.clause_b_paired_mcnemar_agrees.{comp}.{field}")
    # R4 block
    paths += [
        "r4.promoted", "r4.total", "r4.no_r4_fpr_is_claimed",
        "r4.r1_by_construction_refuses_all", "r4.r1_vs_r4_contrast_is_definitional",
        "r4.denominator", "r4.reconciled_with.r4_status", "r4.reconciled_with.r4_evaluable",
    ]
    for i in range(len(NONBLIND_INDICES)):
        for field in ("roster_index", "pool", "chal_policy", "inc_policy", "n", "gain",
                      "exact_mcnemar_p", "R4_promote", "R1_promote"):
            paths.append(f"r4.per_pool.{i}.{field}")
    return paths


def compare(committed: dict, recomputed: dict) -> list:
    """Return the list of mismatch strings ('field | committed | recomputed'), empty iff equal."""
    mismatches = []
    for path in _compare_paths():
        try:
            got = _get(committed, path)
        except (KeyError, IndexError, TypeError, ValueError):
            mismatches.append(f"MISMATCH {path} | committed=<missing> | "
                              f"recomputed={_get(recomputed, path)!r}")
            continue
        want = _get(recomputed, path)
        if not _equal(got, want):
            mismatches.append(f"MISMATCH {path} | committed={got!r} | recomputed={want!r}")
    return mismatches


def _rel(path: Path):
    """``path`` relative to the repo root when possible, else the absolute path (temp copies)."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    ablation_path = Path(argv[0]) if argv else ABLATION
    pools_path = Path(argv[1]) if len(argv) > 1 else POOLS

    pools = bp.load_pools_json(pools_path)                    # committed evidence, verified on load
    committed = json.loads(ablation_path.read_text(encoding="utf-8"))
    if not isinstance(committed, dict):
        print(f"audit: {ablation_path} is not an object ({type(committed).__name__})")
        return 1

    recomputed = recompute(pools)
    mismatches = compare(committed, recomputed)

    print(f"audit: recomputed {len(_compare_paths())} figures from "
          f"{_rel(pools_path)} + {_rel(ablation_path)} "
          f"(source modules only; ablation.json read as the committed reference)")
    print(f"audit: pooled FPR  R1={recomputed['fpr']['pooled']['R1']['rate']}  "
          f"R2={recomputed['fpr']['pooled']['R2']['rate']}  "
          f"R3={recomputed['fpr']['pooled']['R3']['rate']}  "
          f"R4={recomputed['fpr']['pooled']['R4']['rate']}  "
          f"R5={recomputed['fpr']['pooled']['R5']['rate']}  "
          f"R6={recomputed['fpr']['pooled']['R6']['rate']}  "
          f"R7@8={recomputed['fpr']['pooled']['R7']['rate']}")
    print(f"audit: TPR R1..R7 = "
          f"{[recomputed['tpr'][r]['rate'] for r in RULES]}  "
          f"(POSITIVE denominator = 1, no discriminating power)")
    print(f"audit: FPR@8 endpoint = {recomputed['fpr_r7_at8']}  "
          f"verdict_branch = {recomputed['verdict_branch']!r}")
    print(f"audit: Wilson[R1] upper={recomputed['fpr']['pooled']['R1']['wilson95_upper']} "
          f"< Wilson[R2] lower={recomputed['fpr']['pooled']['R2']['wilson95_lower']}  "
          f"< Wilson[R7@8] lower={recomputed['fpr']['pooled']['R7']['wilson95_lower']}")
    mcn = recomputed['verdict']['branch_i']['clause_b_paired_mcnemar_agrees']
    print(f"audit: McNemar agreement  R2  p={mcn['r2_comparison']['exact_two_sided_p']:.3g}  "
          f"R7@8 p={mcn['r7at8_comparison']['exact_two_sided_p']:.3g}")

    if mismatches:
        print(f"AUDIT FAIL: {len(mismatches)} figure(s) do not match the committed ablation.json")
        for m in mismatches:
            print(m)
        return 1

    print(f"AUDIT PASS: all {len(_compare_paths())} recomputed figures equal the committed "
          f"ablation.json (exit 0)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())