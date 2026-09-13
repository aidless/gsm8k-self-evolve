# tests/test_gate_rules.py
"""Tests for the canonical gate decision rules (PLAN-NOVELTY.md Task 2).

Frozen protocol (authoritative): ``results/rounds/round5/PREREG-round5.md``
  - S2 ........ the seven decision rules (exact semantics)
  - S2.1 ...... R7 interface note (absent ``candidates`` -> k = 1 degeneracy, behaviourally R2)
  - S2.2 / AMENDMENT 1 ... R6 ``no-stat`` = keep ``gain >= eps``, drop ONLY the significance test
  - S1.1 ...... orientation convention (gain = (total_chal - total_inc) / n = (b - c) / n)
  - S5.2 ...... R7 operative statistic pinned at ``k = 8``

Ruling 18 (binding): ``scripts/gate_rules.py`` is the **canonical** rule implementation.  This
file asserts equivalence with the pilot-local rule code (``scripts/pilot_round5.py``) at the
pilot's parameters (``alpha = 0.05``, ``eps = 0.02``, AMENDMENT 1 R6), so the two implementations
are checked against each other rather than left divergent.

These tests are hand-built pools (test fixtures, not evidence about any policy) and are written to
fail first (TDD step 1) before ``scripts/gate_rules.py`` exists.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.gate_rules as gr          # noqa: E402
from evokit.stats import mcnemar_two_sided  # noqa: E402

GATE_KEYS = ("hidden_passed", "safety_passed", "rollback_available", "bundle_signature_valid")


def mk_pool(b, c, n=None, blind=True, structural=None, candidates=None,
            name="test-pool", truth="observed"):
    """A paired pool with ``b`` chal-only items, ``c`` inc-only items, and the remaining
    ``n - b - c`` items concordant both-pass.  ``gain = (b - c) / n`` (PREREG S1.1)."""
    if n is None:
        n = b + c
    if n < b + c:
        raise ValueError("n must be >= b + c")
    items = []
    idx = 0
    for _ in range(b):
        items.append({"qid": f"q{idx}", "chal": True, "inc": False})
        idx += 1
    for _ in range(c):
        items.append({"qid": f"q{idx}", "chal": False, "inc": True})
        idx += 1
    for _ in range(n - b - c):
        items.append({"qid": f"q{idx}", "chal": True, "inc": True})
        idx += 1
    pool = {
        "name": name, "n": n, "blind": blind, "truth": truth,
        "chal_policy": "chal", "inc_policy": "inc", "items": items,
    }
    if structural is None:
        structural = dict.fromkeys(GATE_KEYS, True)
    pool.update(structural)
    if candidates is not None:
        pool["candidates"] = candidates
    return pool


def _assert_schema(d):
    assert isinstance(d, dict)
    assert set(d) == {"promote", "p", "gain", "reasons", "recomputable"}
    assert isinstance(d["promote"], bool)
    assert d["p"] is None or isinstance(d["p"], float)
    assert isinstance(d["gain"], float)
    assert isinstance(d["reasons"], list) and all(isinstance(r, str) for r in d["reasons"])
    assert d["recomputable"] is True


# --------------------------------------------------------------------------- required tests

def test_r2_point_promotes_on_any_positive_gain():
    pool = mk_pool(b=3, c=2)              # gain = (3-2)/5 = 0.2 > 0, but p = 1.0 (not significant)
    d = gr.decide("R2", pool)
    _assert_schema(d)
    assert d["promote"] is True
    assert d["p"] is None
    assert gr.decide("R1", pool)["promote"] is False


def test_gate_never_promotes_on_exact_tie():
    d = gr.decide("R1", mk_pool(b=2, c=2))   # gain = 0
    assert d["promote"] is False
    assert d["gain"] == 0.0


def test_r6_without_stat_key_promotes_on_gain_alone():
    pos = mk_pool(b=3, c=2)               # gain = 0.2 >= eps, but p = 1.0 (no significance required)
    assert gr.decide("R6", pos)["promote"] is True
    assert gr.decide("R6", pos)["p"] is None
    assert gr.decide("R1", pos)["promote"] is False
    # proving not the degenerate all-promote reading: R6 refuses zero / negative gain
    assert gr.decide("R6", mk_pool(b=2, c=2))["promote"] is False   # gain == 0
    assert gr.decide("R6", mk_pool(b=2, c=3))["promote"] is False   # gain == -0.2


def test_r4_ignores_blindness():
    # b = 9, c = 1, n = 40 -> gain = 8/40 = 0.2 >= eps, exact McNemar p(9,1) = 0.0215 < 0.05.
    nonblind = mk_pool(b=9, c=1, n=40, blind=False)
    assert gr.decide("R4", nonblind)["promote"] is True            # paired test, no blind gate
    assert gr.decide("R1", nonblind)["promote"] is False           # R1 requires blind is True
    # R4 is still fail-closed on the structural-key conjunction (the gate minus blindness)
    broken = mk_pool(b=9, c=1, n=40, blind=False, structural={"hidden_passed": False,
                                                              "safety_passed": True,
                                                              "rollback_available": True,
                                                              "bundle_signature_valid": True})
    assert gr.decide("R4", broken)["promote"] is False


def test_r7_reads_candidates_and_pins_k8():
    assert gr.K_R7 == 8
    neg = mk_pool(b=1, c=2, name="neg")    # gain = -1/3
    pos = mk_pool(b=3, c=1, name="pos")    # gain = +0.5

    # 8 candidates, one positive among them -> promote on the best candidate.
    pool = mk_pool(b=1, c=2)
    pool["candidates"] = [neg] * 7 + [pos]
    d = gr.decide("R7", pool)
    assert d["promote"] is True
    assert d["p"] is None
    assert abs(d["gain"] - 0.5) < 1e-12    # the point-estimate best candidate's gain

    # all-8-non-positive -> refuse.
    pool["candidates"] = [neg] * 8
    assert gr.decide("R7", pool)["promote"] is False

    # Pinning k = 8: a 9th candidate (index 8) is OUTSIDE the k = 8 prefix and must be ignored.
    pool["candidates"] = [neg] * 8 + [pos]
    assert gr.decide("R7", pool)["promote"] is False

    # Degenerate interface path (no candidates): k = 1, the pool itself, behaviourally R2.
    no_cands = mk_pool(b=3, c=1)           # gain = +0.5 > 0
    d = gr.decide("R7", no_cands)
    assert d["promote"] is True
    assert any("degenerate" in r.lower() for r in d["reasons"])
    assert gr.decide("R7", mk_pool(b=1, c=3))["promote"] is False   # gain < 0 -> refuse


def test_all_rules_are_pure():
    pool = mk_pool(b=9, c=1, n=40, blind=True)
    pool["candidates"] = [mk_pool(b=3, c=1) for _ in range(8)]
    for rule in gr.RULES:
        d1 = gr.decide(rule, pool)
        d2 = gr.decide(rule, pool)
        assert d1 == d2, f"{rule} not pure"
        _assert_schema(d1)
        assert d1["recomputable"] is True


def test_mcnemar_agreement_with_evokit():
    for b, c in [(1, 0), (2, 4), (9, 1), (33, 4), (3, 2), (0, 5), (1, 1)]:
        pool = mk_pool(b=b, c=c, n=max(b + c, 1), blind=True)
        want = mcnemar_two_sided(b, c)
        for rule in ("R1", "R4", "R5"):
            got = gr.decide(rule, pool)["p"]
            assert got is not None
            assert abs(got - want) < 1e-15, (rule, b, c, got, want)


def test_ruling18_pilot_equivalence():
    import scripts.pilot_round5 as pilot
    cases = [
        (1, 0, True), (0, 1, True), (2, 2, True), (3, 2, True), (2, 3, True),
        (9, 1, True), (1, 9, True), (33, 4, True), (9, 1, False), (3, 2, False),
    ]
    for b, c, blind in cases:
        n = b + c
        if n == 0:
            continue
        pool = mk_pool(b=b, c=c, n=n, blind=blind)
        assert gr.decide("R1", pool)["promote"] is pilot.promote_r1(pool), ("R1", b, c, blind)
        assert gr.decide("R2", pool)["promote"] is pilot.promote_r2(pool), ("R2", b, c, blind)
        assert gr.decide("R6", pool)["promote"] is pilot.promote_r6(pool), ("R6", b, c, blind)


# ---------------------------------------------------------------------------- extra coverage

def test_r3_unpaired_fisher_exact_form_is_pinned():
    # b = 9 chal-only + c = 1 inc-only, no concordant -> n = 10, x1 = 9, x2 = 1.
    pool = mk_pool(b=9, c=1, n=10)
    d = gr.decide("R3", pool)
    # Two-sided Fisher exact (independent-sample 2x2 table with row totals n, n): p = 202/184756.
    assert abs(d["p"] - 202 / 184756) < 1e-9
    assert d["promote"] is True            # p < 0.05 AND gain = 0.8 >= 0.02
    # The paired test (R1) on the same pool uses only the discordant b, c, and must differ:
    assert gr.decide("R1", pool)["p"] == mcnemar_two_sided(9, 1)
    # A tied margin (x1 == x2) -> Fisher p == 1.0.
    tied = mk_pool(b=1, c=1, n=2)
    assert abs(gr.decide("R3", tied)["p"] - 1.0) < 1e-12
    assert gr.decide("R3", tied)["promote"] is False   # gain == 0


def test_r5_loose_alpha_020_promotes_where_r1_refuses():
    # b = 7, c = 2 -> d = 9, exact McNemar p = 92/512 = 0.1796875 in [0.05, 0.20).
    pool = mk_pool(b=7, c=2)
    assert gr.decide("R5", pool)["promote"] is True    # p < 0.20 and gain >= eps
    assert gr.decide("R1", pool)["promote"] is False   # p >= 0.05
    assert abs(gr.decide("R5", pool)["p"] - 0.1796875) < 1e-12


def test_gate_fails_closed_on_missing_structural_key():
    missing = mk_pool(b=9, c=1, n=40, blind=True)
    del missing["hidden_passed"]                        # missing key must read as False
    assert gr.decide("R1", missing)["promote"] is False
    assert gr.decide("R5", missing)["promote"] is False
    assert gr.decide("R6", missing)["promote"] is False
    falsified = mk_pool(b=9, c=1, n=40, blind=True)
    falsified["safety_passed"] = False
    assert gr.decide("R1", falsified)["promote"] is False


def test_unknown_rule_is_rejected():
    with pytest.raises(ValueError):
        gr.decide("R8", mk_pool(b=1, c=1))