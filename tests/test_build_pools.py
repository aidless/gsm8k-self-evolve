# tests/test_build_pools.py
"""Tests for the round-5 pool layer (Task 1 + Task 3).

Frozen protocol (authoritative): results/rounds/round5/PREREG-round5.md
  §1     rules 1-5: zero-effect construction, pinned randomness (SEED / child_seed /
         one RNG per source pool / K=200), d == 0 is an error, R7 candidate streams
  §1.1   orientation convention (binding for every pool row)
  §3     pool families + observed-pool roster (indices 0..3)
  §4.1   R2's tie-corrected null expectation (background for the gain assertions)

These tests were written before the implementation and run to failure first
(TDD step 1 of PLAN-NOVELTY.md Task 1); the observed-pool figures are recomputed
from the committed round-4 artefacts, never copied from prose.
"""
import json
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.build_pools as bp

ROUND4 = ROOT / "results" / "rounds" / "round4"
ROUND5 = ROOT / "results" / "rounds" / "round5"

GATE_KEYS = ("hidden_passed", "safety_passed", "rollback_available", "bundle_signature_valid")


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


def test_discordant_polarity_does_not_change_the_draw_budget():
    """Only the item order (not the b/c split) fixes the draw sequence: a pool whose
    discordant items are stored in reverse order consumes the same number of draws."""
    base = mk_pool(b=9, c=7)
    flipped = mk_pool(b=9, c=7, swap_facing=True)
    assert len(bp.permutation_nulls(base, k=1, seed=5)[0]["items"]) == \
        len(bp.permutation_nulls(flipped, k=1, seed=5)[0]["items"])
    b, c = bc_of(bp.permutation_nulls(flipped, k=200, seed=5)[-1])
    assert b + c == 16


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
    monkeypatch.setattr(bp, "build_observed_pools", lambda: [zero])
    with pytest.raises(ValueError):
        bp.build_pools()


def test_null_pool_count_equals_k_times_declared_null_sources():
    """PREREG §1 rule 4: len(nulls) == K x (number of declared null sources)."""
    pools = bp.build_pools()
    nulls = [p for p in pools if p["truth"] == "null"]
    assert len(bp.DECLARED_NULL_SOURCES) == 4          # all four roster entries
    assert len(nulls) == bp.K * len(bp.DECLARED_NULL_SOURCES) == 800


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
    assert len(obs) == 4, "the frozen roster has exactly four observed pools"
    srcs = {p["meta"]["source_pool"] for p in obs}
    assert len(srcs) == 4
    assert any(s.startswith("positive") for s in srcs)   # cot-zero vs direct
    assert any(s.startswith("mid") for s in srcs)        # large-d pools
    assert any(s.startswith("marginal") for s in srcs)   # step-calc vs concise-reason
    # hard constraint (PREREG §8): the alpha/unpaired arms need a large-discordance pool
    assert any(p["meta"]["discordant_total"] >= 15 for p in obs), \
        "need a large-discordance observed pool for the alpha/unpaired arms"
    assert all(p["n"] > 0 for p in pools)
    assert all(p["blind"] in (True, False) for p in obs)
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
    assert len(pools) == 804                           # 4 observed + 800 nulls
    for p in pools:
        for key in GATE_KEYS:
            assert p[key] is True, (p["name"], key)
        assert set(p) >= {"name", "n", "blind", "truth", "items", "meta", *GATE_KEYS}
        for field in ("source_pool", "discordant_total", "chal_policy", "inc_policy", "seed"):
            assert field in p["meta"], (p["name"], field)


def test_observed_pool_blind_flags_and_null_inheritance():
    """PREREG §3: pools taken from the blind held-out sets must be labelled blind.
    Both source artefacts of the roster are the round-4 blind held-out sets
    (examples/heldout40.json / examples/heldout-batch2-160.json)."""
    observed = bp.build_observed_pools()
    assert all(p["blind"] is True for p in observed)
    for p in observed:
        assert "blind" in p["meta"] and p["meta"]["blind"] == p["blind"]
        assert p["meta"]["blind_basis"]
    nulls = bp.permutation_nulls(observed[3], k=2, seed=bp.child_seed(3))
    assert all(p["blind"] is observed[3]["blind"] for p in nulls)


# ------------------------------------- PREREG §1 (children of a real pool are named)

def test_null_pool_identity_and_naming():
    pools = bp.build_pools()
    by_source = {}
    for p in pools:
        if p["truth"] == "null":
            by_source.setdefault(p["meta"]["source_pool"], []).append(p)
    assert set(by_source) == {r["source_pool"] for r in bp.ROSTER}
    for src, group in by_source.items():
        assert len(group) == bp.K
        assert [p["meta"]["null_index"] for p in group] == list(range(bp.K))
        assert len({p["name"] for p in group}) == bp.K
    # the child seed of a source pool is pinned by its roster index, not by its name
    for idx, entry in enumerate(bp.ROSTER):
        group = by_source[entry["source_pool"]]
        assert all(p["meta"]["seed"] == bp.SEED + idx for p in group)


# --------------------------------------------------- R7 candidate streams (§1 rule 5)

def test_null_candidate_blocks_are_pure_and_not_the_units_own_null_pool():
    base = bp.build_observed_pools()[1]                # d = 16, large discordance
    blocks = {}
    for unit, j, cand in bp.iter_null_candidate_blocks(base, k_units=4, k_prefix=8):
        blocks[(unit, j)] = cand
    assert sorted(blocks) == [(i, j) for i in range(4) for j in range(1, 9)]
    # NULL-family candidates are relabellings: true effect identically 0, d preserved
    for cand in blocks.values():
        b, c = bc_of(cand)
        assert b + c == base["meta"]["discordant_total"]
        assert cand["meta"]["is_candidate"] is True
        assert cand["meta"]["candidate_family"] == "NULL"
    # the unit's own R2 null pool is NOT one of its candidates (PREREG §5.2)
    own_nulls = bp.permutation_nulls(base, k=4, seed=bp.child_seed(1))
    for i in range(4):
        own = [it["qid"] for it in own_nulls[i]["items"] if it["chal"] != it["inc"]]
        for j in range(1, 9):
            cand = blocks[(i, j)]
            assert cand != own_nulls[i]
            assert sorted(it["qid"] for it in cand["items"] if it["chal"] != it["inc"]) \
                == sorted(own)
    # purity: recomputing block (2, 3) in a fresh call gives the identical pool
    again = [c for u, j, c in bp.iter_null_candidate_blocks(base, k_units=4, k_prefix=8)
             if (u, j) == (2, 3)]
    assert again == [blocks[(2, 3)]]
    # PREREG §4: the k-subset is the prefix j = 1..k of that unit's nested block stream, and
    # the reported k only filters the pinned stream -- it never reshapes or re-draws it
    prefix = [c for u, j, c in bp.iter_null_candidate_blocks(base, k_units=4, k_prefix=2)
              if u == 1]
    assert prefix == [blocks[(1, 1)], blocks[(1, 2)]]
    assert [c for u, j, c in bp.iter_null_candidate_blocks(base, k_units=4, k_prefix=1)] == \
        [blocks[(0, 1)], blocks[(1, 1)], blocks[(2, 1)], blocks[(3, 1)]]
    # and the k=8 endpoint (R7's operative reading, PREREG §5.2) is candidate block (i, 8)
    last = [c for u, j, c in bp.iter_null_candidate_blocks(base, k_units=3, k_prefix=8)
            if j == 8]
    assert [c["meta"]["candidate_index"] for c in last] == [8, 8, 8]


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
    null_family = [c for u, j, c in bp.iter_null_candidate_blocks(positive, k_units=bp.K, k_prefix=8)
                   if (u, j) == (0, 1)][0]
    assert bc_of(null_family) != bc_of(cands[0])


# ------------------------- orientation arithmetic recomputed from committed JSON

def test_orientation_arithmetic_from_committed_json():
    """PREREG §1.1 (binding): gain == (total_chal - total_inc) / n and b + c == d.
    Recomputed from the committed round-4 artefacts, never copied from prose."""
    A = json.loads((ROUND4 / "trackA-merged.json").read_text(encoding="utf-8"))
    C = json.loads((ROUND4 / "trackC-qwen2-7b-heldout40.json").read_text(encoding="utf-8"))
    cases = [
        # (artefact, pair key, chal, inc, declared b, declared c, declared gain, declared p)
        (A, "direct_vs_cot-zero", "cot-zero", "direct", 159, 0, 0.795, 2.7369110631344083e-48),
        (C, "step-calc_vs_concise-reason", "step-calc", "concise-reason", 2, 4, -0.050, 0.6875),
    ]
    for D, key, chal, inc, exp_b, exp_c, exp_gain, exp_p in cases:
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
                    if p["chal_policy"] == chal and p["inc_policy"] == inc)
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
    """PREREG §1 Observed-pool roster (frozen): names, indices and d values."""
    expected = [("positive-cotzero-vs-direct", 159),
                ("mid-stepcalc-vs-cotzero", 16),
                ("mid-stepcalc-vs-fewshot", 23),
                ("marginal-stepcalc-vs-concise", 6)]
    assert [(r["source_pool"], r["index"]) for r in bp.ROSTER] == \
        [(name, i) for i, (name, _) in enumerate(expected)]
    observed = bp.build_observed_pools()
    got = [(p["meta"]["source_pool"], p["meta"]["discordant_total"]) for p in observed]
    assert got == expected

# ------------------------------------------- committed artefacts (pools.json / PILOT.json)

def check_pools_consistency(pools):
    """Structural consistency of a pools list.

    Used both by the committed-artefact test and by an out-of-band mutation check that
    proves the test actually bites (a deliberately corrupted pools list must fail it).
    """
    nulls = [p for p in pools if p["truth"] == "null"]
    obs = [p for p in pools if p["truth"] == "observed"]
    assert len(nulls) == bp.K * len(bp.DECLARED_NULL_SOURCES) == 800
    assert len(obs) == 4
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
    pools = json.loads(path.read_text(encoding="utf-8"))
    assert pools == bp.build_pools(), "pools.json must equal build_pools()"
    check_pools_consistency(pools)
    # the pinned randomness is recoverable from the artefact alone
    by_source = {}
    for p in pools:
        if p["truth"] == "null":
            by_source.setdefault(p["meta"]["source_pool"], []).append(p)
    for index, entry in enumerate(bp.ROSTER):
        group = by_source[entry["source_pool"]]
        assert len(group) == bp.K
        assert all(p["meta"]["seed"] == bp.SEED + index for p in group)
        # recompute one null block of each source pool from the artefact's own item order
        assert group[7] == bp.permutation_nulls(
            next(p for p in pools if p["truth"] == "observed"
                 and p["meta"]["source_pool"] == entry["source_pool"]),
            8, bp.SEED + index)[7]


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
        assert 0.0 <= m["value"] <= 1.0 if m["metric"] != "mean_null_gain" else True
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
