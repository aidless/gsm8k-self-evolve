"""Re-run of the design-validation pilot, committed as a script (PREREG-round5.md §7.1).

Why this file exists
--------------------
The standing prose pilot figures of ``PLAN-NOVELTY.md`` / ``PREREG-round5.md`` §7.2 are
**superseded and not citable** (controller ruling 10): the ad-hoc design pilot recorded no
seed at all and no ``(K, seed)`` pair per metric, its FPR figures sit on a ``/2000`` grid while
part of its ``FPR@k`` curve does not sit on the deliverable's ``/200`` grid, and no pilot
script or pool artefact was ever committed.  §7.1.3 therefore requires Task 1 to re-run the
pilot as a committed script that records an **explicit K and an explicit seed per metric**.

This script is committed **before** it is run.  It records, for every reported metric, the
``(metric, K, seed)`` triple that produced it, and writes ``results/rounds/round5/PILOT.json``.
Only the figures this run produces are citable; the superseded prose values are carried along
**for comparison only** and are marked as such.

Scope and honesty boundaries
----------------------------
* This is **design-validation pilot evidence, not a deliverable result**.  The deliverable
  run is Task 4, at the prereg's ``K = 200`` over ``results/rounds/round5/pools.json``.
* The superseded pilot never recorded *which* pool(s) it ran on.  The reconstruction target is
  therefore **inferred** from the grid arithmetic and that inference is recorded, not hidden:
  see ``_reconstruction_rationale()``.  Metrics are also recorded for every other source pool
  and for the four-pool pooled set, so no reading has to depend on the inference.
* The decision rules used here are **pilot-local** implementations of PREREG §2 (R1, R2, R6)
  and of the §1 rule 5 candidate streams (R7), because the deliverable implementation of the
  rules (Task 2, ``scripts/gate_rules.py``) does not exist at Task 1 time and the pilot must
  be runnable and committed now.  No metric of this pilot may be cited as a result about the
  decision rules themselves (PREREG §6: the deliverable run is Task 4).
* A permutation draw is a **construction**, not a measurement (PREREG §1).

Reconciliation obligation (controller ruling 18) -- for Task 2/Task 4
--------------------------------------------------------------------
``scripts/gate_rules.py`` (Task 2) is the **canonical** rule implementation.  The rule code in
this pilot is **pilot-local and provisional**, and it MUST be reconciled with that canonical
module once Task 2 ships -- either

  (a) by a test asserting **equivalence at the pilot's own parameters** (compare
      ``decide("R1"|"R2"|"R6", pool)`` from ``scripts/gate_rules.py`` against
      ``promote_r1``/``promote_r2``/``promote_r6`` of this module on the same pools, at
      ``alpha = 0.05``, ``eps = 0.02`` and the AMENDMENT 1 R6 reading), or

  (b) by **re-running this pilot through the canonical module** and disclosing the updated
      figures (a new ``PILOT.json``, superseding the current one, with a dated note here).

Until one of those is done, ``PILOT.json``'s ``rule_source`` field stands as the disclosure
that the figures come from pilot-local code.  This paragraph is the pointer that makes the
obligation visible where Task 2 and Task 4 will read it; the reconciliation itself is
deliberately **not** implemented here (the canonical module does not exist yet).
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.build_pools as bp                      # noqa: E402
from evokit.stats import mcnemar_two_sided            # noqa: E402

OUT = ROOT / "results" / "rounds" / "round5" / "PILOT.json"

K_PILOT = 2000          # the superseded design pilot's grid (PREREG §7.1.1)
ALPHA = 0.05            # PREREG §2 R1
EPS = 0.02              # PREREG §2 R1
K_MAX = bp.K_CANDIDATES  # PREREG §5.2: the pre-run-fixed k = 8

# PREREG §7.1.1 "Superseded set" -- recorded for comparison only, never as a result.
SUPERSEDED = {
    "source": "PREREG-round5.md §7.1.1 / PLAN-NOVELTY.md design-validation prose",
    "citable": False,
    "mean_null_gain": -0.0029,
    "fpr": {"R1": 0.015, "R2": 0.320, "R6": 0.320},
    "fpr_at_k": {1: 0.357, 2: 0.620, 4: 0.838, 8: 0.968},
}


# --------------------------------------------------------------- pilot-local rule readings
#
# PREREG §2 (R1/R2/R6 semantics, R6 as adopted by AMENDMENT 1); the four structural gate keys
# are true by construction (§1), which is asserted below on every pool the pilot touches.

def _bc(pool: dict):
    items = pool["items"]
    b = sum(1 for it in items if it["chal"] and not it["inc"])
    c = sum(1 for it in items if it["inc"] and not it["chal"])
    return b, c


def _gain(pool: dict) -> float:
    return bp._gain(pool)


def promote_r1(pool: dict) -> bool:
    """PREREG §2 R1: five-key gate, alpha = 0.05, eps = 0.02, blind set."""
    if pool["blind"] is not True:
        return False
    if not all(pool[key] is True for key in bp.GATE_KEYS):
        return False
    b, c = _bc(pool)
    return mcnemar_two_sided(b, c) < ALPHA and _gain(pool) >= EPS


def promote_r2(pool: dict) -> bool:
    """PREREG §2 R2: promote iff gain > 0 (no test at all)."""
    return _gain(pool) > 0


def promote_r6(pool: dict) -> bool:
    """PREREG §2 R6 as adopted by AMENDMENT 1: magnitude criterion kept, significance dropped."""
    if not all(pool[key] is True for key in bp.GATE_KEYS):
        return False
    return _gain(pool) >= EPS


def r2_expected_null_rate(d: int) -> float:
    """PREREG §4.1: E[FPR_R2] = (1 - P(tie))/2 with P(tie) = C(d, d/2)/2^d (0 for odd d)."""
    if d % 2:
        return 0.5
    return (1 - math.comb(d, d // 2) / 2 ** d) / 2


# ------------------------------------------------------------------------ pilot run

def run_pool(pool: dict, K: int = K_PILOT) -> dict:
    """All pilot metrics for one source pool, each with the K and seed that produced it."""
    index = pool["meta"]["source_pool_index"]
    seed = bp.child_seed(index)
    d = pool["meta"]["discordant_total"]

    nulls = bp.permutation_nulls(pool, K, seed)
    for null in nulls:                                    # §1: keys are structural constants
        assert all(null[key] is True for key in bp.GATE_KEYS)
    assert len(nulls) == K

    gains = [_gain(p) for p in nulls]
    fpr = {
        "R1": sum(1 for p in nulls if promote_r1(p)) / K,
        "R2": sum(1 for p in nulls if promote_r2(p)) / K,
        "R6": sum(1 for p in nulls if promote_r6(p)) / K,
    }

    # R7 FPR@k, k = 1..8: the k-subset is the prefix j = 1..k of the unit's nested candidate
    # blocks (§1 rule 5 / §4), so one pass over the pinned stream yields the whole curve.
    best = [[float("-inf")] * (K_MAX + 1) for _ in range(K)]
    n_candidates = 0
    for unit, j, cand in bp.iter_null_candidate_blocks(pool, k_units=K, k_prefix=K_MAX, seed=seed):
        n_candidates += 1
        best[unit][j] = max(best[unit][j], _gain(cand))
    assert n_candidates == K * K_MAX, (n_candidates, K * K_MAX)

    curve = {}
    for k in range(1, K_MAX + 1):
        promoted = 0
        for unit in range(K):
            unit_best = max(best[unit][1:k + 1])
            promoted += unit_best > 0
        curve[k] = promoted / K

    return {
        "source_pool": pool["meta"]["source_pool"],
        "source_pool_index": index,
        "n": pool["n"],
        "discordant_total": d,
        "K": K,
        "seed": seed,
        "n_units": K,
        "n_candidate_blocks": n_candidates,
        "mean_null_gain": sum(gains) / K,
        "fpr": fpr,
        "fpr_at_k": curve,
        "r2_expected_null_rate_prereg_4_1": r2_expected_null_rate(d),
        "r1_expected_null_rate_note": (
            "PREREG §4: R1 expected <= alpha; at small d the exact test is discrete and "
            "conservative, so 0 is reported together with its interval, never as 'zero error rate'"),
    }


def pooled(runs: list[dict]) -> dict:
    """Pooled readings over the four source pools (equal K per pool, so unit-weighted)."""
    units = sum(r["n_units"] for r in runs)
    curve = {}
    for k in range(1, K_MAX + 1):
        promoted = sum(round(r["fpr_at_k"][k] * r["n_units"]) for r in runs)
        curve[k] = promoted / units
    return {
        "source_pool": "ALL_SOURCES_POOLED",
        "source_pool_index": None,
        "K": runs[0]["K"],
        "seeds": [r["seed"] for r in runs],
        "n_units": units,
        "mean_null_gain": sum(r["mean_null_gain"] * r["n_units"] for r in runs) / units,
        "fpr": {rule: sum(r["fpr"][rule] * r["n_units"] for r in runs) / units
                for rule in ("R1", "R2", "R6")},
        "fpr_at_k": curve,
        # PREREG §4.1: for a pooled rate the expectation is the size-weighted mean of
        # (1 - P(tie_d))/2 over the pools of the set.
        "r2_expected_null_rate_prereg_4_1":
            sum(r["r2_expected_null_rate_prereg_4_1"] * r["n_units"] for r in runs) / units,
    }


def _reconstruction_rationale(runs: list[dict], pooled_run: dict) -> dict:
    """Which pool the superseded pilot most plausibly ran on, and the arithmetic behind it."""
    per_pool = {r["source_pool"]: r for r in runs}
    marginal = per_pool["marginal-stepcalc-vs-concise"]
    k = K_PILOT
    # The superseded R2 figure is 640/2000.  On the four-pool pooled set the constructive
    # expectation is mean_d E[FPR_R2](d) = 0.4364 -> 3491/8000, i.e. ~20.8 sigma away; on the
    # d = 6 marginal pool alone it is 0.34375 -> 687.5/2000, i.e. ~2.2 sigma away.
    expected_pooled = pooled_run["r2_expected_null_rate_prereg_4_1"]
    expected_marginal = marginal["r2_expected_null_rate_prereg_4_1"]
    sd_pooled = math.sqrt(pooled_run["n_units"] * 0.25)
    sd_marginal = math.sqrt(k * expected_marginal * (1 - expected_marginal))
    return {
        "target": marginal["source_pool"],
        "target_source_pool_index": marginal["source_pool_index"],
        "target_K": k,
        "target_seed": marginal["seed"],
        "reason": (
            "The superseded pilot recorded no pool identity. Its R2 figure 0.320 = 640/2000 "
            "cannot be the four-pool pooled set (constructive expectation 0.4364 = 3491/8000, "
            "z = -20.8), while the d = 6 marginal pool alone has expectation 0.34375 = 687.5/2000 "
            "(z = -2.2); its R1 figure 0.015 = 30/2000 is likewise the d = 6 order of magnitude "
            "(P(b' = 6) = 1/64 = 0.0156 = 31/2000). The marginal pool is therefore the best "
            "reconstruction target, but it is an inference: the pilot metrics for every other "
            "pool and for the pooled set are recorded alongside so that no reading depends on it."),
        "r2_expected_gain_pooled": expected_pooled,
        "r2_expected_gain_marginal": expected_marginal,
        "r2_pooled_z": (SUPERSEDED["fpr"]["R2"] * pooled_run["n_units"]
                        - expected_pooled * pooled_run["n_units"]) / sd_pooled,
        "r2_marginal_z": (SUPERSEDED["fpr"]["R2"] * k - expected_marginal * k) / sd_marginal,
        "inference_is_uncertain": True,
    }


def _metric(metric: str, scope: str, run: dict, value, superseded_value, note: str) -> dict:
    return {
        "metric": metric,
        "scope": scope,                      # reconstruction-target | transparency | pooled
        "source_pool": run["source_pool"],
        "source_pool_index": run["source_pool_index"],
        "K": run["K"],
        "seed": run.get("seed"),
        "seeds": run.get("seeds", [run["seed"]] if run.get("seed") is not None else []),
        "n_units": run["n_units"],
        "value": value,
        "superseded_prose_value": superseded_value,
        "agrees_with_superseded_prose": (superseded_value is None or
                                         abs(value - superseded_value) < 1e-12),
        "note": note,
    }


def build_pilot() -> dict:
    # The pilot's scope is §7's four *blind null-source* pools (roster indices 0-3), so it uses
    # `build_null_source_pools()` rather than `build_observed_pools()`: the correction round added
    # five non-blind selection-set observed pools (indices 4-8) that are not part of this pilot.
    observed = bp.build_null_source_pools()
    runs = [run_pool(pool) for pool in observed]
    pooled_run = pooled(runs)
    rationale = _reconstruction_rationale(runs, pooled_run)
    target = rationale["target"]

    metrics = []
    for run in runs:
        scope = "reconstruction-target" if run["source_pool"] == target else "transparency"
        metrics.append(_metric(
            "mean_null_gain", scope, run, run["mean_null_gain"],
            SUPERSEDED["mean_null_gain"] if scope == "reconstruction-target" else None,
            "PREREG §1: mean gain of the permutation nulls; true effect identically 0"))
        for rule in ("R1", "R2", "R6"):
            metrics.append(_metric(
                f"fpr_{rule}", scope, run, run["fpr"][rule],
                SUPERSEDED["fpr"][rule] if scope == "reconstruction-target" else None,
                "PREREG §2 rule semantics; R6 per AMENDMENT 1"))
        for k in range(1, K_MAX + 1):
            sup = SUPERSEDED["fpr_at_k"].get(k) if scope == "reconstruction-target" else None
            metrics.append(_metric(
                f"fpr_at_k_{k}", scope, run, run["fpr_at_k"][k], sup,
                "PREREG §4 FPR@k: prefix j = 1..k of the unit's pinned candidate blocks"))
    metrics.append(_metric(
        "mean_null_gain", "pooled", pooled_run, pooled_run["mean_null_gain"],
        SUPERSEDED["mean_null_gain"],
        "pooled over the four source pools, equal K per pool (unit-weighted)"))
    for rule in ("R1", "R2", "R6"):
        metrics.append(_metric(
            f"fpr_{rule}", "pooled", pooled_run, pooled_run["fpr"][rule], SUPERSEDED["fpr"][rule],
            "pooled over the four source pools, equal K per pool (unit-weighted)"))
    for k in range(1, K_MAX + 1):
        metrics.append(_metric(
            f"fpr_at_k_{k}", "pooled", pooled_run, pooled_run["fpr_at_k"][k],
            SUPERSEDED["fpr_at_k"].get(k),
            "pooled FPR@k over the four source pools"))

    return {
        "schema_version": 1,
        "generated_by": "scripts/pilot_round5.py",
        "prereg": "results/rounds/round5/PREREG-round5.md",
        "status": ("design-validation pilot, re-run and committed (PREREG §7.1.3). Supersedes the "
                   "non-citable prose figures of §7.1/§7.2. NOT a deliverable result: the "
                   "deliverable run is Task 4 at K = 200 over results/rounds/round5/pools.json."),
        "citable": False,
        "citable_as_pilot_evidence": True,
        "citable_as_deliverable_result": False,
        "citable_scope": (
            "these re-run figures are the pilot figures of record and are citable *as pilot / "
            "design-validation evidence only* (PREREG §7.1.3), superseding the non-citable prose "
            "values of §7.1/§7.2. They are NOT citable as a deliverable result: the status field "
            "says so, and the deliverable run is Task 4 at K = 200 over "
            "results/rounds/round5/pools.json."),
        "superseded": SUPERSEDED,
        "pinned": {
            "SEED": bp.SEED,
            "K_pilot": K_PILOT,
            "K_deliverable": bp.K,
            "child_seed_rule": "child_seed = SEED + source_pool_index (PREREG §1 rule 2)",
            "candidate_k": K_MAX,
            "alpha": ALPHA,
            "eps": EPS,
        },
        "rule_source": (
            "pilot-local implementations of PREREG §2 R1/R2/R6 (R6 as adopted by AMENDMENT 1) "
            "and of the PREREG §1 rule 5 candidate streams for R7; the deliverable rule "
            "implementation is Task 2's scripts/gate_rules.py, which does not exist yet, and no "
            "pilot figure may be cited as a result about the decision rules (PREREG §6)"),
        "construction_note": (
            "nulls are permutation relabellings of the source pool's discordant items, all "
            "sharing that pool's questions; they are not independent samples (PREREG §1)"),
        "reconstruction_target": rationale,
        "metrics": metrics,
        "pool_rows": runs,
        "pooled_row": pooled_run,
    }


def main() -> int:
    pilot = build_pilot()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(pilot, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    print(f"pilot re-run (PREREG §7.1.3)  SEED={bp.SEED}  K_pilot={K_PILOT}  "
          f"K_deliverable={bp.K}  candidate_k={K_MAX}")
    print(f"reconstruction target (inferred): {pilot['reconstruction_target']['target']} "
          f"(K={K_PILOT}, seed={pilot['reconstruction_target']['target_seed']})")
    print()
    print("per-pool pilot rows (metric : value  [superseded prose value])")
    for run in pilot["pool_rows"]:
        print(f"  {run['source_pool']:32s} K={run['K']} seed={run['seed']} d={run['discordant_total']}")
        print(f"      mean_null_gain={run['mean_null_gain']:+.5f}"
              f"  E[R2|null]={run['r2_expected_null_rate_prereg_4_1']:.5f}")
        print(f"      FPR R1={run['fpr']['R1']:.4f}  R2={run['fpr']['R2']:.4f}"
              f"  R6={run['fpr']['R6']:.4f}")
        print("      FPR@k " + "  ".join(f"k={k}:{run['fpr_at_k'][k]:.4f}"
                                         for k in range(1, K_MAX + 1)))
    p = pilot["pooled_row"]
    print()
    print(f"pooled over 4 source pools: units={p['n_units']} "
          f"seeds={p['seeds']} mean_null_gain={p['mean_null_gain']:+.5f} "
          f"E[R2|null]={p['r2_expected_null_rate_prereg_4_1']:.5f}")
    print(f"  FPR R1={p['fpr']['R1']:.4f} [{SUPERSEDED['fpr']['R1']}]  "
          f"R2={p['fpr']['R2']:.4f} [{SUPERSEDED['fpr']['R2']}]  "
          f"R6={p['fpr']['R6']:.4f} [{SUPERSEDED['fpr']['R6']}]")
    print("  FPR@k " + "  ".join(
        f"k={k}:{p['fpr_at_k'][k]:.4f}[{SUPERSEDED['fpr_at_k'].get(k)}]"
        for k in range(1, K_MAX + 1)))
    print()
    print("comparison against the SUPERSEDED (non-citable) prose figures, "
          "reconstruction target only:")
    for m in pilot["metrics"]:
        if m["scope"] != "reconstruction-target" or m["superseded_prose_value"] is None:
            continue
        flag = "same" if m["agrees_with_superseded_prose"] else "DIFFERS"
        print(f"  {m['metric']:16s} new={m['value']:.5f}  "
              f"superseded={m['superseded_prose_value']}  -> {flag}")
    print(f"\nwrote {OUT.relative_to(ROOT)} "
          f"({OUT.stat().st_size} bytes, {len(pilot['metrics'])} metric records)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
