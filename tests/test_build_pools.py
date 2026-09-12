# tests/test_build_pools.py
"""Tests for the round-5 pool layer (Task 1 + Task 3).

Frozen protocol (authoritative): results/rounds/round5/PREREG-round5.md
  §1     rules 1-5: zero-effect construction, pinned randomness (SEED / child_seed /
         one RNG per source pool / K=200), d == 0 is an error, R7 candidate streams
  §1.1   orientation convention (binding for every pool row)
  §3     pool families + observed-pool roster
  §5A    R4 (non-blind arm) -- EVALUATED (correction round); the earlier "not evaluated"
         claim rested on a false premise and is corrected here and in the artefact
  §4.1   R2's tie-corrected null expectation (background for the gain assertions)

These tests were written before the implementation and run to failure first
(TDD step 1 of PLAN-NOVELTY.md Task 1); the observed-pool figures are recomputed
from the committed source artefacts, never copied from prose.

Correction round (2026-09-12): `results/runs/*.json` DO carry per-question detail
(`baseline.outcomes[]` / `candidates[].evaluation.outcomes[]`), so non-blind
selection-set pools are added as roster indices 4-8.  The guard that enforced the old
"no non-blind pool exists" claim is replaced by one that asserts each pool's `blind` flag
matches the source it declares.

Fix round 3 (2026-09-12): the selection-set run `20260908-235617` carries a THIRD complete
candidate arm (`rounding-aware` vs `concise-reason`) that the first roster silently omitted, so
the block is **six** pools (indices 4-9) and PREREG §5A's exhaustiveness sentence is now true.
`test_the_nonblind_roster_is_exhaustive_over_the_committed_arms` pins the enumeration; the one
arm that is not rostered (`reworded-direct`, d == 0) is an explicit disclosed exclusion.
"""
import hashlib
import json
import math
import random
import subprocess
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.build_pools as bp

ROUND3 = ROOT / "results" / "rounds" / "round3"
ROUND4 = ROOT / "results" / "rounds" / "round4"
ROUND5 = ROOT / "results" / "rounds" / "round5"

GATE_KEYS = ("hidden_passed", "safety_passed", "rollback_available", "bundle_signature_valid")

# The six non-blind selection-set pools, exactly as declared for the correction round (indices
# 4-9; index 9 added by fix round 3 so the block is exhaustive).  The counts are re-derived from
# the source artefacts by `derive_nonblind_pools()` below and compared against this table -- the
# table is the assertion oracle, never the source of the values.
NONBLIND_TABLE = [
    # name, chal, inc, source file, n, b, c, d, gain
    ("nonblind-concise-vs-direct", "concise-reason", "direct",
     "results/runs/20260907-135728.json", 40, 20, 0, 20, 0.500),
    ("nonblind-doublecheck-vs-direct", "double-check", "direct",
     "results/runs/20260907-135728.json", 40, 2, 4, 6, -0.050),
    ("nonblind-stepcalc-vs-concise", "step-calc", "concise-reason",
     "results/runs/20260908-235617.json", 40, 9, 1, 10, 0.200),
    ("nonblind-rectify-vs-concise", "rectify", "concise-reason",
     "results/runs/20260908-235617.json", 40, 5, 3, 8, 0.050),
    ("nonblind-reflect-vs-stepcalc", "reflect-retry", "step-calc",
     "results/rounds/round3/pilot-train40.json", 40, 2, 2, 4, 0.000),
    # fix round 3: the omitted third arm of run 20260908-235617 (status-equivalent to `rectify`,
    # which was already rostered), so the non-blind block is now exhaustive
    ("nonblind-roundingaware-vs-concise", "rounding-aware", "concise-reason",
     "results/runs/20260908-235617.json", 40, 8, 2, 10, 0.150),
]


# --------------------------------------------------------------------------- helpers

def mk_pool(b, c, blind=True, name="synthetic-pool", source_pool="synthetic-pool",
            source_pool_index=0, swap_facing=False):
    """Hand-made pool with exactly b challenger-only and c incumbent-only items.

    Two concordant items are appended (both pass / both fail) so that a test can
    prove concordant items are copied through unchanged by the null construction.
    `swap_facing` puts the discordant items in the reverse order, to prove the
    frozen item order (not the polarity) drives the draw sequence.
    """
    items = []
    for i in range(b):
        items.append({"qid": f"b{i:03d}", "chal": True, "inc": False})
    for i in range(c):
        items.append({"qid": f"c{i:03d}", "chal": False, "inc": True})
    if swap_facing:
        items.reverse()
    items.append({"qid": "concordant-both-pass", "chal": True, "inc": True})
    items.append({"qid": "concordant-both-fail", "chal": False, "inc": False})
    pool = {
        "name": name,
        "n": len(items),
        "blind": blind,
        "truth": "observed",
        "chal_policy": "chal-policy",
        "inc_policy": "inc-policy",
        "items": items,
        "meta": {
            "source_pool": source_pool,
            "source_pool_index": source_pool_index,
            "discordant_total": b + c,
            "chal_policy": "chal-policy",
            "inc_policy": "inc-policy",
            "seed": bp.SEED + source_pool_index,
        },
    }
    for key in GATE_KEYS:
        pool[key] = True
    return pool


def gain_of(pool):
    n = len(pool["items"])
    return (sum(1 for it in pool["items"] if it["chal"])
            - sum(1 for it in pool["items"] if it["inc"])) / n


def bc_of(pool):
    items = pool["items"]
    b = sum(1 for it in items if it["chal"] and not it["inc"])
    c = sum(1 for it in items if it["inc"] and not it["chal"])
    return b, c


def _source_totals(details, policies):
    return {p: sum(1 for row in details.values() if row[p]["passed"]) for p in policies}


def exact_mcnemar_two_sided(b, c):
    """Two-sided exact McNemar p from the discordant counts, by the exact binomial definition.

    Computed here independently of both the run files and the module under test, so every `p` the
    report or the artefact carries for an observed pool can be re-derived from the raw `b`/`c`.
    """
    n_disc = b + c
    if n_disc == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(math.comb(n_disc, i) for i in range(k + 1)) / 2 ** n_disc)


def _ref_relabel(items, rng):
    """Reference relabelling used by the tests: independent of the module's implementation."""
    out = [dict(it) for it in items]
    for it in out:
        if bool(it["chal"]) != bool(it["inc"]):
            if rng.random() < 0.5:
                it["chal"], it["inc"] = it["inc"], it["chal"]
    return out


class _CountingRng:
    def __init__(self, seed):
        self._rng = random.Random(seed)
        self.draws = 0

    def random(self):
        self.draws += 1
        return self._rng.random()


class _RngFactory:
    """Stand-in for `bp.random` whose `Random(...)` counts every `.random()` call."""

    def __init__(self):
        self.instances = []

    def __call__(self, seed):
        rng = _CountingRng(seed)
        self.instances.append(rng)
        return rng

    @property
    def draws(self):
        return sum(r.draws for r in self.instances)


def install_counting_random(monkeypatch):
    factory = _RngFactory()
    monkeypatch.setattr(bp, "random", types.SimpleNamespace(Random=factory))
    return factory


def _loads(rel_path):
    return json.loads((ROOT / rel_path).read_text(encoding="utf-8"))


def derive_nonblind_pools():
    """Re-derive the six non-blind pools from the raw committed artefacts.

    The run artefacts are located by their recorded (baseline policy, candidate policy) rather
    than by filename; the round-3 pilot is located by its `oracle` field.  Nothing here imports
    the module's own builders, so this is an independent re-derivation.
    """
    runs = []
    for path in sorted((ROOT / "results" / "runs").glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        baseline_policy = doc["baseline"]["outcomes"][0]["details"]["policy"]
        assert all(o["details"]["policy"] == baseline_policy for o in doc["baseline"]["outcomes"])
        for cand in doc["candidates"]:
            policy = cand["candidate"]["answer_policy"]
            assert all(o["details"]["policy"] == policy for o in cand["evaluation"]["outcomes"])
            runs.append((path, doc, baseline_policy, policy, cand))

    def run_items(baseline_policy, chal_policy):
        hits = [(p, d, c) for p, d, b, ch, c in runs
                if b == baseline_policy and ch == chal_policy]
        assert len(hits) == 1, (baseline_policy, chal_policy, [str(h[0]) for h in hits])
        path, doc, cand = hits[0]
        base = {o["task_id"]: bool(o["passed"]) for o in doc["baseline"]["outcomes"]}
        chal = {o["task_id"]: bool(o["passed"]) for o in cand["evaluation"]["outcomes"]}
        assert set(base) == set(chal)
        qids = sorted(base)
        return (path.relative_to(ROOT).as_posix(),
                [{"qid": q, "chal": chal[q], "inc": base[q]} for q in qids])

    pilot_paths = [p for p in sorted((ROOT / "results" / "rounds" / "round3").glob("*.json"))
                   if json.loads(p.read_text(encoding="utf-8")).get("oracle") == "train-only"]
    assert len(pilot_paths) == 1, pilot_paths
    pilot = json.loads(pilot_paths[0].read_text(encoding="utf-8"))
    assert pilot["oracle"] == "train-only"

    out = []
    for name, chal_policy, inc_policy, declared_source, *_ in NONBLIND_TABLE:
        if declared_source.startswith("results/runs/"):
            source, items = run_items(inc_policy, chal_policy)
        else:
            source = pilot_paths[0].relative_to(ROOT).as_posix()
            chal_rows = {r["id"]: bool(r["passed"])
                         for r in pilot[chal_policy.replace("-", "_")]["details"]}
            inc_rows = {r["id"]: bool(r["passed"])
                        for r in pilot[inc_policy.replace("-", "_")]["details"]}
            assert set(chal_rows) == set(inc_rows)
            items = [{"qid": q, "chal": chal_rows[q], "inc": inc_rows[q]}
                     for q in sorted(chal_rows)]
        b = sum(1 for it in items if it["chal"] and not it["inc"])
        c = sum(1 for it in items if it["inc"] and not it["chal"])
        n = len(items)
        gain = (sum(1 for it in items if it["chal"]) - sum(1 for it in items if it["inc"])) / n
        out.append({"name": name, "source": source, "n": n, "b": b, "c": c, "d": b + c,
                    "gain": round(gain, 12), "gain_raw": gain,
                    "chal_policy": chal_policy, "inc_policy": inc_policy})
    return out


# --------------------------------------------------- PREREG §1 rule 1 (construction)

def test_permutation_null_has_zero_expected_gain_and_keeps_discordance():
    """PREREG §1: only discordant items are relabelled, each independently with p=0.5,
    so d is preserved exactly and the true effect is identically 0 (mean gain ~ 0)."""
    base = mk_pool(b=9, c=7)                       # d = 16
    nulls = bp.permutation_nulls(base, k=200, seed=1)
    assert len(nulls) == 200
    for p in nulls:
        assert p["truth"] == "null"
        assert p["meta"]["discordant_total"] == 16
        b, c = bc_of(p)
        assert b + c == 16, "discordant total must be preserved by relabelling"
    gains = [gain_of(p) for p in nulls]
    assert abs(sum(gains) / len(gains)) < 0.05, "mean null gain must be ~0"
    # concordant items pass through unchanged (both the both-pass and both-fail item)
    base_concordant = {it["qid"]: (it["chal"], it["inc"])
                       for it in base["items"] if it["chal"] == it["inc"]}
    assert len(base_concordant) == 2
    for p in nulls:
        for it in p["items"]:
            if it["qid"] in base_concordant:
                assert (it["chal"], it["inc"]) == base_concordant[it["qid"]], it["qid"]
    # the source pool must not be mutated by the construction
    b0, c0 = bc_of(base)
    assert (b0, c0) == (9, 7)


def test_null_draw_rule_is_one_draw_per_discordant_item_in_frozen_order():
    """PREREG §1 rules 2-3: swap iff a single rng.random() draw is < 0.5, walked once per
    discordant item in the pool's frozen item order, one RNG per source pool."""
    base = mk_pool(b=9, c=7)
    expected = [dict(it) for it in base["items"]]
    rng = random.Random(1)
    for idx, it in enumerate(expected):
        if it["chal"] != it["inc"]:                # frozen order: enumerate order
            if rng.random() < 0.5:
                expected[idx]["chal"], expected[idx]["inc"] = it["inc"], it["chal"]
    assert bp.permutation_nulls(base, k=1, seed=1)[0]["items"] == expected


def test_the_draw_budget_is_exactly_one_draw_per_discordant_item(monkeypatch):
    """PREREG §1 rules 1/3 -- **the draw budget itself**, counted rather than inferred.

    The earlier version of this test asserted only the length of the item lists and that the
    discordant total was preserved; neither counts a draw, so an implementation that drew twice
    per discordant item (or re-seeded per null) would have passed it.  Here every `.random()`
    call is counted: `k` null blocks over `d` discordant items must consume exactly `k * d`
    draws, from exactly one RNG instance, and the polarity/order of the *labels* cannot change
    that budget (only the number of discordant items can).
    """
    base = mk_pool(b=9, c=7)                        # d = 16
    factory = install_counting_random(monkeypatch)
    bp.permutation_nulls(base, k=200, seed=5)
    assert len(factory.instances) == 1, "exactly one RNG instance per source pool (no re-seeding)"
    assert factory.draws == 200 * 16

    flipped = mk_pool(b=9, c=7, swap_facing=True)   # same d, reversed discordant order
    factory2 = install_counting_random(monkeypatch)
    bp.permutation_nulls(flipped, k=200, seed=5)
    assert len(factory2.instances) == 1
    assert factory2.draws == 200 * 16

    # concordant items are never drawn for: a pool with more concordant items but the same d
    # consumes exactly the same budget
    wider = mk_pool(b=9, c=7)
    wider["items"] = wider["items"] + [{"qid": "extra-both-pass", "chal": True, "inc": True}]
    factory3 = install_counting_random(monkeypatch)
    bp.permutation_nulls(wider, k=50, seed=7)
    assert factory3.draws == 50 * 16


# ---------------------------------------- PREREG §1 rules 2-3 (determinism, purity)

def test_permutation_null_is_deterministic_given_seed():
    """PREREG §1 rules 2-3: (source_pool, i) -> null pool is a pure function of
    (SEED, source_pool_index, frozen item order)."""
    base = mk_pool(b=9, c=7)
    assert bp.permutation_nulls(base, 50, 3) == bp.permutation_nulls(base, 50, 3)
    # a single null pool is also reproducible on its own (no global state, no re-seeding)
    nulls = bp.permutation_nulls(base, 50, 3)
    assert nulls[7] == bp.permutation_nulls(base, 8, 3)[7]
    # the seed must actually be consumed: a different seed gives different nulls
    assert bp.permutation_nulls(base, 50, 3)[0]["items"] != \
        bp.permutation_nulls(base, 50, 4)[0]["items"]
    # and the child seeds are the pinned ones (SEED + 0-based roster index)
    assert bp.child_seed(0) == 20260912 and bp.child_seed(3) == 20260915


# ------------------------------------------------ PREREG §1 rule 4 (d == 0 is an error)

def test_zero_discordance_pool_is_rejected_not_silently_skipped():
    with pytest.raises(ValueError):
        bp.permutation_nulls(mk_pool(b=0, c=0), k=200, seed=20260912)


def test_build_pools_rejects_a_zero_discordance_null_source(monkeypatch):
    """PREREG §1 rule 4: build_pools must reject such a pool as a null source."""
    zero = mk_pool(b=0, c=0)
    zero["meta"]["declared_null_source"] = True
    monkeypatch.setattr(bp, "build_observed_pools", lambda: [zero])
    with pytest.raises(ValueError):
        bp.build_pools()


def test_zero_discordance_null_candidate_stream_is_rejected():
    """PREREG §1 rule 4: the NULL-family candidate stream is a relabelling stream and must
    refuse a pool with nothing to relabel (the earlier code had no such guard here)."""
    with pytest.raises(ValueError):
        list(bp.iter_null_candidate_blocks(mk_pool(b=0, c=0), k_units=4, k_prefix=8, seed=1))


def test_zero_discordance_positive_candidate_stream_is_rejected():
    """PREREG §1 rule 5: the POSITIVE-family label-preserving bootstrap must refuse a pool with
    no observed effect (`d == 0`), the twin of the NULL-family guard above.

    Fix round 3: `positive_candidate_blocks`'s `d == 0` guard was a closed branch with no test.
    The second half checks the guard is *closed and not merely noisy*: a pool with a real effect
    draws its candidates normally, so the rejection above cannot be an accidental side effect.
    """
    with pytest.raises(ValueError, match="real effect"):
        bp.positive_candidate_blocks(mk_pool(b=0, c=0), k_units=4, k_prefix=8, seed=1)
    ok = bp.positive_candidate_blocks(mk_pool(b=3, c=1), k_units=4, k_prefix=2, seed=1)
    assert len(ok) == 2
    assert all(c["meta"]["candidate_family"] == "POSITIVE" for c in ok)
    assert [c["meta"]["candidate_index"] for c in ok] == [1, 2]


def test_zero_discordance_observed_pool_is_allowed_only_when_declared_not_a_null_source():
    """PREREG §1 rule 4, both halves, on the observed path (`_build_observed_pool`).

    Rule 4 permits a `d == 0` pool as an observed row **iff** the roster explicitly declares it
    *not a null source*; such a pool still contributes no nulls, so it cannot move any FPR.  Fix
    round 3: `_build_observed_pool` used to raise unconditionally -- its own error message named
    the escape hatch and then ignored it -- which made the declared escape hatch unusable on the
    one path that builds observed rows.

    The raw material is the real `reworded-direct` arm of the committed selection-set run: its
    candidate re-labels the baseline policy, so `b = c = d = 0` is a fact of the artefact and not
    a synthetic construction.
    """
    entry = {
        "index": 99,
        "source_pool": "synthetic-reworded-direct-probe",
        "source_kind": "run",
        "source_probe": {"baseline_policy": "direct", "candidate_policy": "direct"},
        "declared_source_file": "results/runs/20260907-135728.json",
        "chal_policy": "direct",
        "inc_policy": "direct",
        "declared_null_source": False,          # the escape hatch, declared
        "blind": False,
        "family": "NONBLIND_SELECTION",
        "provenance": "probe entry, d = 0",
        "dataset": "the loop's own development/selection set, 40 ids gsm8k-01..40",
    }
    allowed = bp._build_observed_pool(entry)
    assert bc_of(allowed) == (0, 0) and allowed["meta"]["discordant_total"] == 0
    assert allowed["truth"] == "observed" and allowed["n"] == 40
    assert allowed["meta"]["discordant_checks"]["mcnemar_p"] == 1.0

    # the same pool declared a null source is still refused (nothing to relabel)
    refused = dict(entry, declared_null_source=True)
    with pytest.raises(ValueError, match="not a null source"):
        bp._build_observed_pool(refused)


# the one candidate arm of the committed artefacts that is deliberately NOT a rostered pool;
# fix round 3 pins it so that "exhaustive" cannot be asserted while an arm is merely missing
DISCLOSED_EXCLUSIONS = [
    # (source, baseline policy, candidate policy, reason)
    ("results/runs/20260907-135728.json", "direct", "direct",
     "PREREG §1 rule 4: the candidate re-labels the baseline policy, so b = c = d = 0 and there "
     "is no discordance structure to pool; disclosed, never silently dropped"),
]


def test_roundingaware_pool_counts_and_exact_mcnemar_are_pinned():
    """Fix round 3, item 1: roster index 9 (`rounding-aware` vs `concise-reason`).

    Every figure is re-derived here from the raw run report -- never copied from prose or from the
    artefact under test -- and pinned to the values the controller ruled the roster must carry:
    n = 40, b = 8, c = 2, d = 10, gain = +0.150, exact two-sided McNemar p = 0.109375.
    """
    run = _loads("results/runs/20260908-235617.json")
    cand = next(c for c in run["candidates"]
                if (c.get("candidate") or {}).get("answer_policy") == "rounding-aware")
    base = {o["task_id"]: bool(o["passed"]) for o in run["baseline"]["outcomes"]}
    chal = {o["task_id"]: bool(o["passed"]) for o in cand["evaluation"]["outcomes"]}
    assert set(base) == set(chal) and len(base) == 40
    b = sum(1 for q in base if chal[q] and not base[q])
    c = sum(1 for q in base if base[q] and not chal[q])
    gain = (b - c) / len(base)
    assert (b, c, b + c) == (8, 2, 10)
    assert abs(gain - 0.150) < 1e-12

    # exact two-sided McNemar, recomputed from the exact binomial definition on the 10 discordant
    # pairs (2 x P(X <= min(b, c)), X ~ Binomial(10, 1/2)), independently of both the run file and
    # the module under test
    n_disc, k = b + c, min(b, c)
    p_exact = min(1.0, 2 * sum(math.comb(n_disc, i) for i in range(k + 1)) / 2 ** n_disc)
    assert abs(p_exact - 0.109375) < 1e-12
    # the run's own block is NOT the source of this arm's aggregate (it never promoted it), so
    # there is nothing in the artefact to inherit -- which is exactly why it is pinned here
    assert run["active_id"] != cand["id"]
    assert "statistical_decision" not in cand

    pool = next(p for p in bp.build_observed_pools() if p["meta"]["source_pool_index"] == 9)
    assert pool["meta"]["source_pool"] == "nonblind-roundingaware-vs-concise"
    assert (pool["n"], *bc_of(pool), pool["meta"]["discordant_total"]) == (40, 8, 2, 10)
    assert abs(gain_of(pool) - 0.150) < 1e-12
    assert abs(pool["meta"]["discordant_checks"]["mcnemar_p"] - 0.109375) < 1e-12
    assert pool["blind"] is False
    assert pool["meta"]["declared_null_source"] is False
    assert (pool["chal_policy"], pool["inc_policy"]) == ("rounding-aware", "concise-reason")
    assert pool["meta"]["source_file"] == "results/runs/20260908-235617.json"
    assert bp.ROUNDINGAWARE_PINNED == {"n": 40, "b": 8, "c": 2, "d": 10,
                                       "gain": 0.150, "mcnemar_p": 0.109375}


def _candidate_arms():
    """Every candidate arm the committed artefacts contain, re-derived from the raw JSON.

    Each arm is one (baseline policy, candidate policy) comparison recorded by a committed run
    report, plus the round-3 train-40 pilot's (step-calc, reflect-retry) pair.  The pilot's
    candidate direction is (chal = reflect-retry, inc = step-calc), matching the roster.
    """
    arms = []
    for path in sorted((ROOT / "results" / "runs").glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        base_policy = doc["baseline"]["outcomes"][0]["details"]["policy"]
        base = {o["task_id"]: bool(o["passed"]) for o in doc["baseline"]["outcomes"]}
        for cand in doc["candidates"]:
            cand_policy = (cand.get("candidate") or {}).get("answer_policy") or \
                cand["evaluation"]["outcomes"][0]["details"]["policy"]
            chal = {o["task_id"]: bool(o["passed"]) for o in cand["evaluation"]["outcomes"]}
            assert set(base) == set(chal)
            b = sum(1 for q in base if chal[q] and not base[q])
            c = sum(1 for q in base if base[q] and not chal[q])
            arms.append({"source": path.relative_to(ROOT).as_posix(), "baseline": base_policy,
                         "candidate": cand_policy, "n": len(base), "b": b, "c": c,
                         "d": b + c, "gain": (b - c) / len(base)})
    pilot = json.loads((ROUND3 / "pilot-train40.json").read_text(encoding="utf-8"))
    chal = {r["id"]: bool(r["passed"]) for r in pilot["reflect_retry"]["details"]}
    inc = {r["id"]: bool(r["passed"]) for r in pilot["step_calc"]["details"]}
    assert set(chal) == set(inc)
    b = sum(1 for q in inc if chal[q] and not inc[q])
    c = sum(1 for q in inc if inc[q] and not chal[q])
    arms.append({"source": "results/rounds/round3/pilot-train40.json", "baseline": "step-calc",
                 "candidate": "reflect-retry", "n": len(inc), "b": b, "c": c, "d": b + c,
                 "gain": (b - c) / len(inc)})
    return arms


def test_the_nonblind_roster_is_exhaustive_over_the_committed_arms():
    """Fix round 3, item 1: PREREG §5A's exhaustiveness sentence must be TRUE.

    The sentence is "one per available paired selection-set comparison".  Before fix round 3 the
    roster held five of the six eligible arms while still asserting exhaustiveness, because the
    selection-set run `20260908-235617` carries three complete candidate arms and only two were
    rostered.  This test enumerates **every** candidate arm of every committed run report plus the
    round-3 train-40 pilot and requires a total accounting: each arm is either a rostered pool
    (indices 4-9) or explicitly disclosed -- and a disclosed exclusion must really have `d == 0`,
    so "disclosed" cannot be used to hide an eligible arm.
    """
    arms = _candidate_arms()
    assert {a["source"] for a in arms} == {
        "results/runs/20260907-135728.json",
        "results/runs/20260908-235617.json",
        "results/rounds/round3/pilot-train40.json"}

    rostered = {(r["declared_source_file"], r["inc_policy"], r["chal_policy"])
                for r in bp.ROSTER if not r["blind"]}
    assert len(rostered) == 6, f"the non-blind block must hold six distinct arms, got {rostered}"

    accounted = []
    for arm in arms:
        key = (arm["source"], arm["baseline"], arm["candidate"])
        if key in rostered:
            accounted.append(("rostered", arm))
            continue
        disclosed = [x for x in DISCLOSED_EXCLUSIONS if x[:3] == key]
        assert disclosed, (
            f"candidate arm {key} is neither rostered nor disclosed: the roster is not exhaustive "
            f"(b={arm['b']} c={arm['c']} d={arm['d']} gain={arm['gain']:+.4f})")
        assert arm["d"] == 0, (
            f"{key} is disclosed as a d == 0 exclusion but has d = {arm['d']}: it is eligible and "
            "must be a rostered pool instead")
        accounted.append(("disclosed-exclusion", arm))

    kinds = {"rostered": 0, "disclosed-exclusion": 0}
    for kind, _ in accounted:
        kinds[kind] += 1
    assert kinds == {"rostered": 6, "disclosed-exclusion": 1}, kinds
    assert len(accounted) == len(arms) == 7
    assert [(a["source"], a["baseline"], a["candidate"]) for kind, a in accounted
            if kind == "disclosed-exclusion"] == [x[:3] for x in DISCLOSED_EXCLUSIONS]

    # and the rostered arms reproduce the roster's own orientation + counts, so the accounting is
    # over the same objects the pools are built from (not merely the same names)
    by_key = {(a["source"], a["baseline"], a["candidate"]): a for a in arms}
    artefact = {p["meta"]["source_pool"]: p for p in
                bp.load_pools_json(ROUND5 / "pools.json") if p["truth"] == "observed"}
    for entry in bp.ROSTER:
        if entry["blind"]:
            continue
        arm = by_key[(entry["declared_source_file"], entry["inc_policy"], entry["chal_policy"])]
        pool = artefact[entry["source_pool"]]
        assert (pool["n"], *bc_of(pool), pool["meta"]["discordant_total"]) == \
            (arm["n"], arm["b"], arm["c"], arm["d"])
        assert abs(gain_of(pool) - arm["gain"]) < 1e-12
        assert pool["meta"]["source_pool_index"] == entry["index"]


def test_registry_carries_a_verbatim_copy_not_an_independent_record():
    """Fix round 3, item 2: the provenance of the n=40 selection-set aggregates.

    An earlier round described the registry as an **independent** record of these numbers.  It is
    not: `registry/version-registry.json` -> `history[1]` / `history[3]` carry a byte-identical
    copy of the `statistical_decision` block of the **same** run report, so the agreement asserted
    by the pool builder is a same-source consistency check.  The registry's *current* evidence
    entry for run `eecacc0312d7` (`history[4]`) records a different measurement -- the merged n=200
    held-out result -- which does not corroborate the n=40 selection-set counts.
    """
    reg = _loads("registry/version-registry.json")
    for run_rel, idx in (("results/runs/20260907-135728.json", 1),
                         ("results/runs/20260908-235617.json", 3)):
        run = _loads(run_rel)
        assert reg["history"][idx]["version_id"] == run["active_id"]
        assert reg["history"][idx]["evidence"]["statistical_decision"] == \
            run["statistical_decision"], "the registry entry must be the same-file copy"
        assert reg["history"][idx]["evidence"]["statistical_decision"]["n"] == 40

    merged = reg["history"][4]["evidence"]["statistical_decision"]
    assert reg["history"][4]["version_id"] == "eecacc0312d7"
    assert merged["n"] == 200 and merged["paired_better"] == 33 and merged["paired_worse"] == 4
    assert abs(merged["mcnemar_p_value"] - 1.0843941709026694e-06) < 1e-18
    # the two quantities are genuinely different measurements, not two readings of one record
    assert merged["n"] != reg["history"][3]["evidence"]["statistical_decision"]["n"]
    assert "concise_reason_passed" in merged and \
        "concise_reason_passed" not in reg["history"][3]["evidence"]["statistical_decision"]


def test_null_pool_count_equals_k_times_declared_null_sources():
    """PREREG §1 rule 4: len(nulls) == K x (number of declared null sources), and rule 4's
    "not a null source" escape hatch is honoured: the non-blind observed pools of indices 4-9
    are present in the artefact but contribute no nulls."""
    pools = bp.build_pools()
    nulls = [p for p in pools if p["truth"] == "null"]
    observed = [p for p in pools if p["truth"] == "observed"]
    assert len(bp.DECLARED_NULL_SOURCES) == 4          # the four blind roster entries
    assert bp.NOT_NULL_SOURCES == (4, 5, 6, 7, 8, 9)
    assert len(nulls) == bp.K * len(bp.DECLARED_NULL_SOURCES) == 800
    assert {p["meta"]["source_pool_index"] for p in nulls} == set(bp.DECLARED_NULL_SOURCES)
    assert {p["meta"]["source_pool_index"] for p in observed} == set(range(10))
    assert len(observed) == 10              # 4 blind + 6 non-blind (correction + fix round 3)


# ---------------------------------------------------- PREREG §3 / Task 3 (families)

def test_real_pool_keeps_observed_labels():
    base = mk_pool(b=9, c=7)
    assert base["truth"] == "observed"
    b, c = bc_of(base)
    assert (b, c) == (9, 7)
    observed = bp.build_observed_pools()
    assert all(p["truth"] == "observed" for p in observed)
    positive = observed[0]
    b, c = bc_of(positive)
    assert (b, c) == (159, 0)                          # PREREG §3 declared orientation
    assert (positive["chal_policy"], positive["inc_policy"]) == ("cot-zero", "direct")


def test_pool_families_present_and_sized():
    pools = bp.build_pools()
    nulls = [p for p in pools if p["truth"] == "null"]
    obs = [p for p in pools if p["truth"] == "observed"]
    assert len(nulls) >= 400, "expected >=400 permutation-null pools"
    assert len(obs) == 10, "the frozen roster has four blind + six non-blind observed pools"
    blind_obs = [p for p in obs if p["blind"] is True]
    nonblind_obs = [p for p in obs if p["blind"] is False]
    assert len(blind_obs) == 4 and len(nonblind_obs) == 6
    srcs = {p["meta"]["source_pool"] for p in obs}
    assert len(srcs) == 10
    assert any(s.startswith("positive") for s in srcs)   # cot-zero vs direct
    assert any(s.startswith("mid") for s in srcs)        # large-d pools
    assert any(s.startswith("marginal") for s in srcs)   # step-calc vs concise-reason
    assert len([s for s in srcs if s.startswith("nonblind-")]) == 6
    # hard constraint (PREREG §8): the alpha/unpaired arms need a large-discordance pool
    assert any(p["meta"]["discordant_total"] >= 15 for p in obs), \
        "need a large-discordance observed pool for the alpha/unpaired arms"
    assert all(p["n"] > 0 for p in pools)
    # every observed pool declares its orientation, at top level and in meta
    for p in obs:
        for field in ("chal_policy", "inc_policy"):
            assert isinstance(p[field], str) and p[field], (p["name"], field)
            assert p["meta"][field] == p[field], (p["name"], field)
        assert p["chal_policy"] != p["inc_policy"], p["name"]


def test_every_pool_carries_structural_keys_true():
    """PREREG §1: the four structural keys are set by construction on every pool of
    this study (observed and null alike); this is what makes R1 non-vacuous."""
    pools = bp.build_pools()
    assert len(pools) == 810                           # 10 observed + 800 nulls
    for p in pools:
        for key in GATE_KEYS:
            assert p[key] is True, (p["name"], key)
        assert set(p) >= {"name", "n", "blind", "truth", "items", "meta", *GATE_KEYS}
        for field in ("source_pool", "discordant_total", "chal_policy", "inc_policy", "seed"):
            assert field in p["meta"], (p["name"], field)


def test_observed_pool_blind_flags_and_null_inheritance():
    """PREREG §3: pools taken from the blind held-out sets must be labelled blind, and pools
    taken from the selection set must be labelled non-blind.  Both source classes are present
    since the correction round."""
    observed = bp.build_observed_pools()
    blind = [p for p in observed if p["meta"]["source_pool_index"] < 4]
    nonblind = [p for p in observed if p["meta"]["source_pool_index"] >= 4]
    assert len(blind) == 4 and all(p["blind"] is True for p in blind)
    assert len(nonblind) == 6 and all(p["blind"] is False for p in nonblind)
    for p in observed:
        assert "blind" in p["meta"] and p["meta"]["blind"] == p["blind"]
        assert p["meta"]["blind_basis"]
    for pool in blind + nonblind:
        nulls = bp.permutation_nulls(pool, k=2, seed=bp.child_seed(pool["meta"]["source_pool_index"]))
        assert all(p["blind"] is pool["blind"] for p in nulls)


def test_blind_flags_match_the_declared_source_and_mislabelling_fails():
    """The correction round's guard: a pool's `blind` flag must match the source it declares
    (blind held-out -> True; selection set -> False).  It replaces the earlier guard that
    enforced the false "no non-blind pool exists" claim."""
    pools = bp.load_pools_json(ROUND5 / "pools.json")
    bp.check_blind_labels(pools)                       # the committed artefact is consistent

    # a mislabelled observed pool fails in both directions
    for index, want in ((0, False), (4, True)):
        flipped = [dict(p) for p in pools]
        for p in flipped:
            if p["truth"] == "observed" and p["meta"]["source_pool_index"] == index:
                p["blind"] = want
                p["meta"] = dict(p["meta"], blind=want)
        with pytest.raises(ValueError, match="blind"):
            bp.check_blind_labels(flipped)

    # a null pool that does not inherit its source pool's label fails too
    flipped = [dict(p) for p in pools]
    for p in flipped:
        if p["truth"] == "null":
            p["blind"] = not p["blind"]
            p["meta"] = dict(p["meta"], blind=p["blind"])
            break
    with pytest.raises(ValueError, match="inherit"):
        bp.check_blind_labels(flipped)


def test_nonblind_pools_recomputed_from_source_match_the_declared_table():
    """The six non-blind pools, re-derived in code from the raw run/pilot artefacts.

    FAILS LOUDLY if a derived count differs from the declared table: the table is the oracle,
    the artefacts are the source.  The artefacts are located by recorded policy / oracle, never
    by trusting a filename.
    """
    derived = derive_nonblind_pools()
    assert len(derived) == len(NONBLIND_TABLE) == 6
    got = [(d["name"], d["chal_policy"], d["inc_policy"], d["source"], d["n"], d["b"], d["c"],
            d["d"], round(d["gain_raw"], 6)) for d in derived]
    expected = [(n, ch, inc, src, n_, b, c, d, g) for n, ch, inc, src, n_, b, c, d, g
                in NONBLIND_TABLE]
    assert got == expected, f"re-derived non-blind pools differ from the declared table:\n{got}"

    # and the roster/artefact reproduce the very same figures in the very same orientation
    roster = {r["index"]: r for r in bp.ROSTER}
    artefact = {p["meta"]["source_pool"]: p for p in
                bp.load_pools_json(ROUND5 / "pools.json") if p["truth"] == "observed"}
    for row, entry in zip(derived, NONBLIND_TABLE):
        pool = artefact[row["name"]]
        assert (pool["n"], pool["chal_policy"], pool["inc_policy"]) == \
            (row["n"], row["chal_policy"], row["inc_policy"])
        assert bc_of(pool) == (row["b"], row["c"])
        assert pool["meta"]["discordant_total"] == row["d"]
        assert abs(gain_of(pool) - row["gain_raw"]) < 1e-12
        assert pool["blind"] is False
        assert pool["meta"]["declared_null_source"] is False
        assert pool["meta"]["source_file"] == row["source"]
        assert roster[pool["meta"]["source_pool_index"]]["source_pool"] == row["name"]
        assert pool["meta"]["source_pool_index"] == 4 + [t[0] for t in NONBLIND_TABLE].index(row["name"])
        # the exact McNemar p the PREREG §5A table prints for this row, recomputed independently
        # from the raw b/c (never taken from the run file or from the module's own helper)
        assert abs(pool["meta"]["discordant_checks"]["mcnemar_p"]
                   - exact_mcnemar_two_sided(row["b"], row["c"])) < 1e-12, row["name"]
    # the non-blind roster block is indices 4..9, in that order, and owns no null pools
    assert [r["index"] for r in bp.ROSTER] == list(range(10))
    assert [r["source_pool"] for r in bp.ROSTER][4:] == [t[0] for t in NONBLIND_TABLE]


# ------------------------------------- PREREG §1 (children of a real pool are named)

def test_null_pool_identity_and_naming():
    pools = bp.build_pools()
    by_source = {}
    for p in pools:
        if p["truth"] == "null":
            by_source.setdefault(p["meta"]["source_pool"], []).append(p)
    declared = {bp.ROSTER_BY_INDEX[i]["source_pool"] for i in bp.DECLARED_NULL_SOURCES}
    assert set(by_source) == declared
    # Fix round 3: the assertion that used to sit here intersected `DECLARED_NULL_SOURCES` with
    # `NOT_NULL_SOURCES` -- two complementary filters over the same ROSTER module constant -- so
    # the intersection was empty by construction and it could never fail.  The non-vacuous twin,
    # which reads the *built* null groups and the committed artefact rows, is the final assertion
    # of `test_pools_json_is_the_committed_build_pools_output`.
    for src, group in by_source.items():
        assert len(group) == bp.K
        assert [p["meta"]["null_index"] for p in group] == list(range(bp.K))
        assert len({p["name"] for p in group}) == bp.K
    # the child seed of a source pool is pinned by its roster index, not by its name
    for idx, entry in enumerate(bp.ROSTER):
        if entry["source_pool"] not in by_source:
            continue
        group = by_source[entry["source_pool"]]
        assert all(p["meta"]["seed"] == bp.SEED + idx for p in group)


# --------------------------------------------------- R7 candidate streams (§1 rule 5)

def test_null_candidate_blocks_are_pure_and_drawn_after_every_null_block(monkeypatch):
    """PREREG §5.2: a unit's candidates come from the candidate blocks -- the continuation of
    the pinned stream *after* all `k_units` null blocks -- and never from the unit's own null
    block.

    The property is asserted by **draw position** (an independent reference walk of the pinned
    stream), not by comparing row dicts or discordant-qid sets: the former always differs by
    `name`/`meta` even when the implementation reuses a null block, and the latter is
    relabelling-invariant, so both are vacuous.
    """
    base = bp.build_observed_pools()[1]                # d = 16, large discordance
    seed = bp.child_seed(1)
    k_units, k_prefix = 4, 8
    blocks = {(unit, j): cand for unit, j, cand
              in bp.iter_null_candidate_blocks(base, k_units=k_units, k_prefix=k_prefix, seed=seed)}
    assert sorted(blocks) == [(i, j) for i in range(k_units) for j in range(1, k_prefix + 1)]
    # NULL-family candidates are relabellings: true effect identically 0, d preserved
    for cand in blocks.values():
        b, c = bc_of(cand)
        assert b + c == base["meta"]["discordant_total"]
        assert cand["meta"]["is_candidate"] is True
        assert cand["meta"]["candidate_family"] == "NULL"

    # independent reference walk of the pinned stream, in the pinned order
    rng = random.Random(seed)
    null_blocks = [_ref_relabel(base["items"], rng) for _ in range(k_units)]
    cand_blocks = [_ref_relabel(base["items"], rng)
                   for _ in range(k_units * bp.K_CANDIDATES)]
    for i in range(k_units):
        for j in range(1, k_prefix + 1):
            assert blocks[(i, j)]["items"] == cand_blocks[i * bp.K_CANDIDATES + (j - 1)], (i, j)
    # the candidate stream is NOT the null stream: at least one candidate block differs in its
    # drawn labels from its unit's own null block (an implementation that reused null block i
    # could never satisfy this)
    assert any(blocks[(i, j)]["items"] != null_blocks[i]
               for i in range(k_units) for j in range(1, k_prefix + 1)), \
        "the candidates reproduce their own unit's null blocks -- they are not the candidate stream"

    # purity: recomputing block (2, 3) in a fresh call gives the identical pool
    again = [c for u, j, c in bp.iter_null_candidate_blocks(base, k_units=k_units,
                                                            k_prefix=k_prefix, seed=seed)
             if (u, j) == (2, 3)]
    assert again == [blocks[(2, 3)]]
    # PREREG §4: the k-subset is the prefix j = 1..k of that unit's nested block stream, and
    # the reported k only filters the pinned stream -- it never reshapes or re-draws it
    prefix = [c for u, j, c in bp.iter_null_candidate_blocks(base, k_units=k_units,
                                                             k_prefix=2, seed=seed)
              if u == 1]
    assert prefix == [blocks[(1, 1)], blocks[(1, 2)]]
    assert [c for u, j, c in bp.iter_null_candidate_blocks(base, k_units=k_units, k_prefix=1,
                                                           seed=seed)] == \
        [blocks[(0, 1)], blocks[(1, 1)], blocks[(2, 1)], blocks[(3, 1)]]
    # and the k=8 endpoint (R7's operative reading, PREREG §5.2) is candidate block (i, 8)
    last = [c for u, j, c in bp.iter_null_candidate_blocks(base, k_units=3, k_prefix=8, seed=seed)
            if j == 8]
    assert [c["meta"]["candidate_index"] for c in last] == [8, 8, 8]

    # the draw budget is counted, not inferred: k_units null blocks + the whole pinned
    # j = 1..K_CANDIDATES stream, and `k_prefix` cannot change it (PREREG §1 rule 5)
    d = base["meta"]["discordant_total"]
    factory = install_counting_random(monkeypatch)
    list(bp.iter_null_candidate_blocks(base, k_units=k_units, k_prefix=8, seed=seed))
    assert factory.draws == k_units * d + k_units * bp.K_CANDIDATES * d
    factory2 = install_counting_random(monkeypatch)
    list(bp.iter_null_candidate_blocks(base, k_units=k_units, k_prefix=1, seed=seed))
    assert factory2.draws == k_units * d + k_units * bp.K_CANDIDATES * d, \
        "k_prefix must filter the pinned stream, never reshape or re-draw it"


def test_positive_candidates_preserve_observed_labels_and_resample_with_replacement():
    """PREREG §1 rule 5 / §5.2: the POSITIVE-family stream is a label-preserving item
    bootstrap -- with replacement, no relabelling -- so every draw keeps the observed
    positive effect. Relabelling on this family is forbidden."""
    positive = bp.build_observed_pools()[0]            # cot-zero vs direct, b=159 c=0
    observed_triples = {(it["qid"], it["chal"], it["inc"]) for it in positive["items"]}
    cands = bp.positive_candidate_blocks(positive, k_units=bp.K, k_prefix=8)
    assert len(cands) == 8
    for cand in cands:
        assert cand["n"] == positive["n"]
        assert cand["meta"]["is_candidate"] is True
        assert cand["meta"]["candidate_family"] == "POSITIVE"
        assert cand["meta"]["candidate_unit"] == 0
        assert {(it["qid"], it["chal"], it["inc"]) for it in cand["items"]} <= observed_triples
        assert gain_of(cand) > 0, "the observed positive effect must survive the bootstrap"
        # no observed item is incumbent-only, so the incumbent-only count stays 0 in every draw
        assert bc_of(cand)[1] == 0
        assert bc_of(cand)[0] > 0
    # the resample is genuine: with replacement the b' count moves draw to draw, and qids repeat
    assert len({bc_of(c)[0] for c in cands}) > 1, "an item bootstrap must not be a copy"
    assert any(len({it["qid"] for it in cand["items"]}) < positive["n"] for cand in cands)
    # purity + disjointness from the NULL-family stream of the same pool
    assert bp.positive_candidate_blocks(positive, k_units=bp.K, k_prefix=8) == cands
    assert [c["meta"]["candidate_index"] for c in
            bp.positive_candidate_blocks(positive, k_units=bp.K, k_prefix=3)] == [1, 2, 3]
    null_family = [c for u, j, c in bp.iter_null_candidate_blocks(positive, k_units=bp.K,
                                                                  k_prefix=8)
                   if (u, j) == (0, 1)][0]
    assert bc_of(null_family) != bc_of(cands[0])


# ------------------------------------------------- §1 rule 5 fail-open parameters

def test_pinned_candidate_stream_refuses_a_non_K_budget_without_an_explicit_seed():
    """The pinned stream of a roster pool has exactly K null blocks; a different k_units on the
    pinned path would silently re-shape every candidate draw, so it is refused (fail closed)."""
    base = bp.build_observed_pools()[1]
    assert base["meta"]["source_pool_index"] == 1
    with pytest.raises(ValueError, match="K="):
        list(bp.iter_null_candidate_blocks(base, k_units=4, k_prefix=8))
    with pytest.raises(ValueError, match="K="):
        bp.positive_candidate_blocks(base, k_units=4, k_prefix=8)
    # the off-protocol study stays possible, but only with an explicit seed
    assert len(list(bp.iter_null_candidate_blocks(base, k_units=4, k_prefix=8,
                                                  seed=bp.child_seed(1)))) == 32


def test_stream_seed_never_falls_back_to_index_zero():
    """A pool without `meta.source_pool_index` can never resolve a pinned seed implicitly; the
    earlier silent fallback to index 0's seed is exactly the fail-open bug this closes."""
    orphan = mk_pool(b=9, c=7)
    orphan["meta"].pop("source_pool_index")
    with pytest.raises(ValueError, match="source_pool_index"):
        list(bp.iter_null_candidate_blocks(orphan, k_units=4, k_prefix=8))
    with pytest.raises(ValueError, match="source_pool_index"):
        bp.positive_candidate_blocks(orphan, k_units=bp.K, k_prefix=8)


# ------------------------- orientation arithmetic recomputed from committed JSON

def test_orientation_arithmetic_from_committed_json():
    """PREREG §1.1 (binding): gain == (total_chal - total_inc) / n and b + c == d.
    Recomputed from the committed round-4 artefacts, never copied from prose."""
    A = json.loads((ROUND4 / "trackA-merged.json").read_text(encoding="utf-8"))
    C = json.loads((ROUND4 / "trackC-qwen2-7b-heldout40.json").read_text(encoding="utf-8"))
    cases = [
        # (artefact, pair key, roster pool, chal, inc, declared b, declared c, declared gain, p)
        (A, "direct_vs_cot-zero", "positive-cotzero-vs-direct",
         "cot-zero", "direct", 159, 0, 0.795, 2.7369110631344083e-48),
        (C, "step-calc_vs_concise-reason", "marginal-stepcalc-vs-concise",
         "step-calc", "concise-reason", 2, 4, -0.050, 0.6875),
    ]
    for D, key, roster_name, chal, inc, exp_b, exp_c, exp_gain, exp_p in cases:
        details, n = D["details"], D["meta"]["n"]
        totals = _source_totals(details, D["meta"]["policies"])
        b, c = 0, 0
        for row in details.values():
            cp, ip = bool(row[chal]["passed"]), bool(row[inc]["passed"])
            b += cp and not ip
            c += ip and not cp
        assert (b, c) == (exp_b, exp_c)
        d = b + c
        assert abs((totals[chal] - totals[inc]) / n - exp_gain) < 1e-12
        assert abs((b - c) / n - exp_gain) < 1e-12, "gain == (b - c)/n on a paired pool"
        assert abs(bp.discordant_total_from_items(
            [{"chal": bool(r[chal]["passed"]), "inc": bool(r[inc]["passed"])}
             for r in details.values()]) - d) == 0
        rec = D["pairs"][key]
        assert abs(rec["p"] - exp_p) < 1e-12
        # the artefact's own convention (PREREG §7.2): better counts the SECOND-named policy's
        # only-passes, worse the first-named policy's only-passes, gain = (better - worse)/n
        assert sorted((rec["better"], rec["worse"])) == sorted((b, c))
        assert abs(rec["gain"] - (rec["better"] - rec["worse"]) / n) < 1e-12
        assert abs(rec["gain"]) == abs(exp_gain)
        # the pools produced by build_pools reproduce the same figures in the same orientation
        pool = next(p for p in bp.build_observed_pools()
                    if p["meta"]["source_pool"] == roster_name)
        pb, pc = bc_of(pool)
        assert (pb, pc) == (b, c)
        assert abs(gain_of(pool) - exp_gain) < 1e-12
        assert abs((totals[chal] - totals[inc]) / n - gain_of(pool)) < 1e-12
        assert pool["meta"]["discordant_total"] == d


def test_marginal_pool_reconciles_with_the_reverse_orientation_in_the_artefact():
    """PREREG §7.2: trackC stores the marginal pair in the REVERSE orientation
    (chal=concise-reason, inc=step-calc: b=4 c=2 gain=+0.05); the roster pool declares
    (chal=step-calc, inc=concise-reason: b=2 c=4 gain=-0.050). Same pool, same d, same p."""
    C = json.loads((ROUND4 / "trackC-qwen2-7b-heldout40.json").read_text(encoding="utf-8"))
    rec = C["pairs"]["step-calc_vs_concise-reason"]
    declared = next(p for p in bp.build_observed_pools()
                    if p["meta"]["source_pool"] == "marginal-stepcalc-vs-concise")
    b, c = bc_of(declared)
    assert (b, c) == (2, 4), "PREREG §1.1 worked example for the marginal pool"
    assert declared["meta"]["source_pool_index"] == 3
    assert abs(bp._gain(declared) - (-0.050)) < 1e-12
    assert abs(rec["gain"] - 0.05) < 1e-12
    assert abs(rec["gain"] + bp._gain(declared)) < 1e-12, "the two readings differ only by sign"
    assert (rec["better"], rec["worse"]) == (4, 2) == (c, b)
    assert abs(rec["p"] - declared["meta"]["discordant_checks"]["mcnemar_p"]) < 1e-12
    assert declared["meta"]["discordant_total"] == 6


def test_observed_roster_is_frozen_and_matches_prereg():
    """PREREG §1 Observed-pool roster (frozen): names, indices and d values.

    Indices 0-3 are the blind roster of the prereg; indices 4-9 are the non-blind
    selection-set pools added by the correction round (index 9 by fix round 3)."""
    expected = [("positive-cotzero-vs-direct", 159),
                ("mid-stepcalc-vs-cotzero", 16),
                ("mid-stepcalc-vs-fewshot", 23),
                ("marginal-stepcalc-vs-concise", 6),
                ("nonblind-concise-vs-direct", 20),
                ("nonblind-doublecheck-vs-direct", 6),
                ("nonblind-stepcalc-vs-concise", 10),
                ("nonblind-rectify-vs-concise", 8),
                ("nonblind-reflect-vs-stepcalc", 4),
                ("nonblind-roundingaware-vs-concise", 10)]
    assert [(r["source_pool"], r["index"]) for r in bp.ROSTER] == \
        [(name, i) for i, (name, _) in enumerate(expected)]
    observed = bp.build_observed_pools()
    got = [(p["meta"]["source_pool"], p["meta"]["discordant_total"]) for p in observed]
    assert got == expected
    assert [r["blind"] for r in bp.ROSTER] == [True] * 4 + [False] * 6
    assert [r["declared_null_source"] for r in bp.ROSTER] == [True] * 4 + [False] * 6

# ------------------------------------------- committed artefacts (pools.json / PILOT.json)

def check_pools_consistency(pools):
    """Structural consistency of a pools list.

    Used both by the committed-artefact test and by an out-of-band mutation check that
    proves the test actually bites (a deliberately corrupted pools list must fail it).
    """
    nulls = [p for p in pools if p["truth"] == "null"]
    obs = [p for p in pools if p["truth"] == "observed"]
    assert len(nulls) == bp.K * len(bp.DECLARED_NULL_SOURCES) == 800
    assert len(obs) == 10
    for p in pools:
        assert set(p) >= {"name", "n", "blind", "truth", "items", "meta", *GATE_KEYS}
        for key in GATE_KEYS:
            assert p[key] is True, (p["name"], key)
        assert p["n"] == len(p["items"])
        assert "candidates" not in p, "candidates are not null pools (PREREG §1/§5.2)"
        for field in ("source_pool", "discordant_total", "chal_policy", "inc_policy", "seed"):
            assert field in p["meta"], (p["name"], field)
        assert p["meta"]["chal_policy"] == p["chal_policy"]
        assert p["meta"]["inc_policy"] == p["inc_policy"]
        assert p["meta"]["discordant_total"] == bp.discordant_total_from_items(p["items"])
        b, c = bc_of(p)
        assert b + c == p["meta"]["discordant_total"], p["name"]
        n = len(p["items"])
        total_chal = sum(1 for it in p["items"] if it["chal"])
        total_inc = sum(1 for it in p["items"] if it["inc"])
        assert abs((total_chal - total_inc) / n - (b - c) / n) < 1e-12, p["name"]
        assert p["blind"] is p["meta"]["blind"], p["name"]
    return nulls, obs


def test_pools_json_is_the_committed_build_pools_output():
    """The evidence artefact must be exactly the module's output (recomputable, no drift)."""
    path = ROUND5 / "pools.json"
    assert path.exists(), "results/rounds/round5/pools.json must be committed evidence"
    pools = bp.load_pools_json(path)
    assert pools == bp.build_pools(), "pools.json must equal build_pools()"
    check_pools_consistency(pools)
    # the pinned randomness is recoverable from the artefact alone
    by_source = {}
    for p in pools:
        if p["truth"] == "null":
            by_source.setdefault(p["meta"]["source_pool"], []).append(p)
    for index in bp.DECLARED_NULL_SOURCES:
        entry = bp.ROSTER_BY_INDEX[index]
        group = by_source.get(entry["source_pool"])
        assert group, f"{entry['source_pool']!r} must be a declared null source"
        assert len(group) == bp.K
        assert all(p["meta"]["seed"] == bp.SEED + index for p in group)
        # recompute one null block of each source pool from the artefact's own item order
        assert group[7] == bp.permutation_nulls(
            next(p for p in pools if p["truth"] == "observed"
                 and p["meta"]["source_pool"] == entry["source_pool"]),
            8, bp.SEED + index)[7]
    # the non-blind observed pools contribute no nulls at all (rule 4 escape hatch)
    assert not (set(by_source) & {bp.ROSTER_BY_INDEX[i]["source_pool"]
                                  for i in bp.NOT_NULL_SOURCES})


def _pre_correction_artefact_text():
    """The pre-correction pools.json, read from the git commit the anchor names."""
    commit = bp.PRE_CORRECTION_0_3["commit"]
    rel = bp.PRE_CORRECTION_0_3["artefact"]
    try:
        proc = subprocess.run(["git", "show", f"{commit}:{rel}"], cwd=ROOT,
                              capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:      # no git / shallow clone
        pytest.skip(f"pre-correction artefact not reachable via git ({exc})")
    return proc.stdout


def test_indices_0_3_are_byte_identical_to_the_pre_correction_artefact():
    """Correction-round stability proof: adding roster indices 4-9 changed **nothing** for the
    blind pools of indices 0-3 -- the 4 observed rows and the 800 null rows are byte-identical.

    The reference is the committed pre-correction artefact, read from its git commit (not from a
    hand-copied hash), and the comparison is on the exact one-pool-per-line serialization used by
    the writer, so this is a byte-level claim.
    """
    old_text = _pre_correction_artefact_text()
    assert hashlib.sha256(old_text.encode("utf-8")).hexdigest() == \
        bp.PRE_CORRECTION_0_3["artefact_sha256"]
    old_pools = json.loads(old_text)["pools"]
    old_obs = [p for p in old_pools if p["truth"] == "observed"]
    old_null = [p for p in old_pools if p["truth"] == "null"]
    assert (len(old_obs), len(old_null)) == (bp.PRE_CORRECTION_0_3["n_observed"],
                                             bp.PRE_CORRECTION_0_3["n_null"])
    old_obs_sha = bp._block_sha256(old_obs)
    old_null_sha = bp._block_sha256(old_null)
    assert old_obs_sha == bp.PRE_CORRECTION_0_3["observed_block_sha256"]
    assert old_null_sha == bp.PRE_CORRECTION_0_3["null_block_sha256"]

    new_pools = bp.load_pools_json(ROUND5 / "pools.json")
    new_obs = [p for p in new_pools if p["truth"] == "observed"
               and p["meta"]["source_pool_index"] in bp.BLIND_SOURCE_INDICES]
    new_null = [p for p in new_pools if p["truth"] == "null"
                and p["meta"]["source_pool_index"] in bp.BLIND_SOURCE_INDICES]
    assert (len(new_obs), len(new_null)) == (4, 800)
    assert new_obs == old_obs, "the observed blind rows must be unchanged, dict for dict"
    assert new_null == old_null, "the 800 blind null rows must be unchanged, dict for dict"
    assert bp._block_sha256(new_obs) == old_obs_sha
    assert bp._block_sha256(new_null) == old_null_sha
    stability = bp.byte_stability_0_3(new_pools)
    assert stability["identical"] is True
    assert stability["observed"] == stability["expected"]
    # the whole-artefact description says so too, and the loader accepts it
    assert bp.pools_meta(new_pools)["byte_stability_0_3"]["identical"] is True


def test_pools_artefact_description_matches_the_pools_and_the_blind_labels():
    """The replacement for the earlier guard, which enforced the false claim that no non-blind
    pool exists.

    Now the artefact must (1) stay an object whose description is exactly what the pools imply --
    so it can never misdescribe them -- and (2) carry `blind` flags that match each pool's
    declared source.  Both rejections are exercised, so the guard is not vacuous.
    """
    path = ROUND5 / "pools.json"
    assert path.exists(), "results/rounds/round5/pools.json must be committed evidence"
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(doc, dict), "pools.json must be {'meta': ..., 'pools': [...]}, not a bare array"
    meta, pools = doc["meta"], doc["pools"]
    assert pools

    # (1) the description is exactly the computation over the pools, and R4 really is evaluated
    assert meta == bp.pools_meta(pools)
    assert meta["n_pools"] == len(pools) == 810
    assert meta["n_observed"] == 10 and meta["n_null"] == 800
    assert meta["n_nonblind_pools"] == 6 and meta["n_blind_pools"] == 804
    assert meta["all_artefact_pools_blind"] is False
    assert meta["no_nonblind_pool_in_artefact"] is False
    assert meta["r4_evaluable"] is True
    assert meta["r4_status"] == bp._r4_status(6) == \
        "evaluated (6 non-blind selection-set pool(s) in this artefact)"
    note = meta["r4_note"]
    assert note == bp._r4_note(pools)
    for phrase in ("R4 (non-blind) IS evaluated",
                   "the loop's own selection-set runs, which is exactly what 'non-blind' means",
                   "no synthetic pool was needed and none was used",
                   "the NULL set used for FPR is unchanged"):
        assert phrase in note, f"the r4 note must state {phrase!r}"
    assert set(meta["not_null_sources"]) == {t[0] for t in NONBLIND_TABLE}
    assert len(meta["declared_null_sources"]) == 4
    # the six non-blind pools are named, in roster order
    assert [n for n in meta["not_null_sources"]] == [t[0] for t in NONBLIND_TABLE]

    # (2) blind flags match the declared sources (delegated to the module's own guard)
    bp.check_blind_labels(pools)

    # (3) the guard bites: a bare array, a stale description and a mislabelled pool are rejected
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        bare = Path(td) / "bare.json"
        bare.write_text(json.dumps(pools), encoding="utf-8")
        with pytest.raises(ValueError, match="meta"):
            bp.load_pools_json(bare)

        # a description that no longer matches the pools (one non-blind row flipped to blind)
        flipped = json.loads(json.dumps(pools))
        for p in flipped:
            if p["truth"] == "observed" and p["meta"]["source_pool_index"] == 4:
                p["blind"] = True
                p["meta"]["blind"] = True
        mutated = Path(td) / "mutated.json"
        mutated.write_text(json.dumps({"meta": meta, "pools": flipped}), encoding="utf-8")
        with pytest.raises(ValueError):
            bp.load_pools_json(mutated)

        # a mislabelled pool whose description was *recomputed* (so only the label is wrong)
        recomputed = Path(td) / "recomputed.json"
        recomputed.write_text(json.dumps({"meta": bp.pools_meta(flipped), "pools": flipped}),
                              encoding="utf-8")
        with pytest.raises(ValueError, match="blind"):
            bp.load_pools_json(recomputed)


def test_pilot_json_records_an_explicit_k_and_seed_per_metric():
    """PREREG §7.1.3: one explicit (metric, K, seed) record per reported metric."""
    path = ROUND5 / "PILOT.json"
    assert path.exists(), "results/rounds/round5/PILOT.json must be committed pilot evidence"
    pilot = json.loads(path.read_text(encoding="utf-8"))
    metrics = pilot["metrics"]
    assert metrics
    names = {m["metric"] for m in metrics}
    assert {"mean_null_gain", "fpr_R1", "fpr_R2", "fpr_R6"} <= names
    assert {f"fpr_at_k_{k}" for k in range(1, 9)} <= names
    for m in metrics:
        assert isinstance(m["K"], int) and m["K"] > 0, m
        assert m["seeds"] and all(isinstance(s, int) for s in m["seeds"]), m
        assert m["scope"] in ("reconstruction-target", "transparency", "pooled")
        if m["metric"] != "mean_null_gain":
            assert 0.0 <= m["value"] <= 1.0, m
        sup = m["superseded_prose_value"]
        if sup is not None:
            assert m["agrees_with_superseded_prose"] == (abs(m["value"] - sup) < 1e-12), m
    # the superseded prose figures are carried for comparison only, never as results
    assert pilot["superseded"]["citable"] is False
    assert pilot["pinned"]["SEED"] == bp.SEED
    assert pilot["pinned"]["K_pilot"] == 2000
    assert pilot["pinned"]["K_deliverable"] == bp.K
    target = [m for m in metrics if m["scope"] == "reconstruction-target"]
    assert target
    # the superseded set of §7.1.1 has entries for exactly these metrics (its FPR@k curve
    # was recorded at k = 1, 2, 4, 8 only); each must carry its comparison value
    with_superseded = {m["metric"] for m in target if m["superseded_prose_value"] is not None}
    assert with_superseded == {"mean_null_gain", "fpr_R1", "fpr_R2", "fpr_R6",
                               "fpr_at_k_1", "fpr_at_k_2", "fpr_at_k_4", "fpr_at_k_8"}, \
        with_superseded
    assert pilot["reconstruction_target"]["inference_is_uncertain"] is True
    # every pilot row carries its own K and seed (a per-metric record, not a per-run one)
    for row in pilot["pool_rows"]:
        assert row["K"] == pilot["pinned"]["K_pilot"] and isinstance(row["seed"], int)
        assert row["n_candidate_blocks"] == row["K"] * bp.K_CANDIDATES
        assert len(row["fpr_at_k"]) == bp.K_CANDIDATES
        assert abs(row["mean_null_gain"]) < 0.01, "the null mean gain must be ~0 (PREREG §1)"
    # AMENDMENT 1 / §2.2: at d = 6, gain >= 0.02 and gain > 0 are the same event, so R6 == R2
    marginal = next(r for r in pilot["pool_rows"] if r["discordant_total"] == 6)
    assert marginal["fpr"]["R6"] == marginal["fpr"]["R2"]
    # the pilot is pilot evidence, not a deliverable result -- and the artefact must say so
    # consistently instead of carrying a bare `citable: true` next to "NOT a deliverable result"
    assert pilot["citable"] is False
    assert pilot["citable_as_deliverable_result"] is False
    assert pilot["citable_as_pilot_evidence"] is True
    assert "NOT a deliverable result" in pilot["status"]
    assert "NOT citable as a deliverable result" in pilot["citable_scope"]
    assert "design-validation evidence only" in pilot["citable_scope"]
    # the pilot's scope is the four blind null-source pools (the correction round's non-blind
    # pools are not pilot material)
    assert [r["source_pool"] for r in pilot["pool_rows"]] == \
        [bp.ROSTER_BY_INDEX[i]["source_pool"] for i in bp.DECLARED_NULL_SOURCES]
