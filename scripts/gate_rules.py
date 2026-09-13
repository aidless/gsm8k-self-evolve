"""Canonical implementation of the round-5 gate decision rules.

Frozen protocol (authoritative): ``results/rounds/round5/PREREG-round5.md``; this module is the
**single canonical** implementation of its S2 (the seven rules) that the ablation (Task 4) and the
audit (Task 5) both consume.  ``scripts/pilot_round5.py`` carries *pilot-local* rule code that was
written before this module existed; ruling 18 requires the two to be reconciled (see
``tests/test_gate_rules.py::test_ruling18_pilot_equivalence``).  No other implementation of these
rules is sanctioned.

The seven rules (S2), with their exact semantics:

================  ======================================================================
rule              semantics
================  ======================================================================
``R1``  ``gate``  five-key gate: promote iff ``blind is True`` AND all four structural
                  keys hold AND the statistical key holds; the statistical key is
                  ``exact two-sided McNemar p < alpha = 0.05`` AND ``gain >= eps = 0.02``.
                  Fail-closed: a MISSING structural key reads as ``False`` (never defaulted
                  true), and a missing/false ``blind`` refuses.
``R2``  ``point`` promote iff ``gain > 0`` (no test at all).
``R3``  ``unpaired``  two-sample proportion test (NOT paired): ``p < 0.05`` AND
                  ``gain >= 0.02``.  The exact test form is stated in
                  ``_fisher_exact_two_sided`` below (two-sided Fisher exact test on the
                  independent-sample 2x2 table of the two policy marginals).
``R4``  ``nonblind``  the gate's paired test ignoring the blindness requirement: the
                  structural-key conjunction and the paired exact McNemar criterion
                  (``p < 0.05`` AND ``gain >= 0.02``) with **no** ``blind`` condition, so on
                  a non-blind pool R4 can promote where R1 refuses by construction.
``R5``  ``loose``  the gate with ``alpha = 0.20`` (everything else unchanged).
``R6``  ``no-stat``  AMENDMENT 1 (adopted reading): keep ``gain >= eps = 0.02``, drop ONLY
                  the significance test (and the blindness condition), keep the four
                  structural keys.  This is **not** the degenerate all-promote reading.
``R7``  ``bestofk``  promote iff the point-estimate best of its ``k = 8`` candidates has
                  ``gain > 0``.  Candidates are read from ``pool["candidates"]`` (the pinned
                  ``k = 8`` candidate blocks of PREREG S1 rule 5, built family-appropriately
                  by Task 1 -- relabelling for a NULL-family unit, label-preserving item
                  bootstrap for the POSITIVE family; this module never mixes or builds them).
                  The absent-``candidates`` degeneracy is ``k = 1`` (the best of one candidate
                  is the pool itself, behaviourally R2) and is an **interface note only, never
                  an operative reading** (PREREG S2.1); it is surfaced in ``reasons`` so a
                  caller can never take it silently.
================  ======================================================================

Orientation convention (S1.1, binding): ``gain = (total_chal - total_inc) / n`` and this equals
``(b - c) / n`` where ``b`` counts items the challenger passes and the incumbent fails and ``c``
the reverse; a signed gain is only meaningful with its ``(chal_policy, inc_policy)`` declaration,
which is carried by the pool row and never transcribed here without it.

Purity: ``decide`` is a pure function -- identical inputs give identical outputs -- and performs
no network, clock, filesystem or random access.  ``recomputable`` is therefore always ``True``
and every decision is re-derivable from the pool's ``items`` and the constants below.
"""
from __future__ import annotations

import math

from evokit.stats import mcnemar_two_sided

ALPHA = 0.05            # PREREG S2 R1/R3/R4 significance threshold
ALPHA_LOOSE = 0.20      # PREREG S2 R5
EPS = 0.02              # PREREG S2 R1/R3/R4/R5/R6 effect-size threshold
K_R7 = 8                # PREREG S5.2: the pre-run-fixed k of R7's operative reading

# PREREG S1: the four structural gate keys, true by construction on every study pool.
GATE_KEYS = ("hidden_passed", "safety_passed", "rollback_available", "bundle_signature_valid")

RULES = ("R1", "R2", "R3", "R4", "R5", "R6", "R7")


# ----------------------------------------------------------------------- little helpers

def _items_bc(items) -> tuple[int, int]:
    """``(b, c)`` = (# items chal passes and inc fails, # items inc passes and chal fails)."""
    b = sum(1 for it in items if it["chal"] and not it["inc"])
    c = sum(1 for it in items if it["inc"] and not it["chal"])
    return b, c


def _totals(items) -> tuple[int, int]:
    """``(total_chal, total_inc)`` = the two policy marginal pass counts."""
    chal = sum(1 for it in items if it["chal"])
    inc = sum(1 for it in items if it["inc"])
    return chal, inc


def _gain(pool: dict) -> float:
    """``gain = (total_chal - total_inc) / n`` (PREREG S1.1); n is the number of items."""
    items = pool["items"]
    n = len(items)
    if n == 0:
        raise ValueError("pool has no items")
    chal, inc = _totals(items)
    return (chal - inc) / n


def _structural_ok(pool: dict) -> bool:
    """The four key conjunction, fail-closed: a MISSING key reads as ``False``."""
    return all(pool.get(key) is True for key in GATE_KEYS)


def _fisher_exact_two_sided(x1: int, x2: int, n: int) -> float:
    """Two-sided Fisher exact test on the independent-sample 2x2 proportion table.

    **R3's exact form** (PREREG S2 requires it to be named; it is Fisher exact, NOT the normal
    approximation and NOT the paired McNemar test).

    R3 treats the challenger's ``n`` pass/fail outcomes and the incumbent's ``n`` outcomes as two
    **independent** samples and tests equality of the two pass proportions.  The 2x2 table is::

        row 1 (challenger) : x1 passes, n - x1 fails        (total n)
        row 2 (incumbent)  : x2 passes, n - x2 fails        (total n)

    Conditioning on the column margins (``x1 + x2`` passes, ``2n - (x1 + x2)`` fails) and the
    fixed row totals, the number of challenger passes ``k`` is hypergeometric:

        P(k) = C(x1+x2, k) * C(2n - (x1+x2), n - k) / C(2n, n).

    The two-sided p-value is the sum of ``P(k)`` over every ``k`` in the support whose probability
    does not exceed that of the observed ``x1`` (the min-likelihood convention, identical to
    ``scipy.stats.fisher_exact(..., alternative="two-sided")``).  Exact: no normal approximation,
    no continuity correction.  Row totals are n and n because both policies score the same items.
    """
    n1 = n
    n2 = n
    col1 = x1 + x2            # total passes
    col2 = 2 * n - col1       # total fails
    N = n1 + n2
    lo = max(0, col1 - n2)
    hi = min(col1, n1)
    if lo > hi:
        return 1.0
    denom = math.comb(N, n1)
    obs_num = math.comb(col1, x1) * math.comb(N - col1, n1 - x1)
    if obs_num == 0:
        return 1.0
    p = 0.0
    for k in range(lo, hi + 1):
        num = math.comb(col1, k) * math.comb(N - col1, n1 - k)
        if num <= obs_num:
            p += num / denom
    return min(1.0, p)


def _gate(pool: dict, alpha: float, eps: float, require_blind: bool, use_significance: bool):
    """Shared core of R1 / R4 / R5 / R6 (PLAN-NOVELTY.md Task 2 step 3).

    * structural conjunction: all four ``GATE_KEYS`` present and ``True`` (fail-closed);
    * ``require_blind``: demand ``pool["blind"] is True`` (R1/R5 yes; R4/R6 no);
    * ``use_significance``: promotion needs ``p < alpha AND gain >= eps`` (R1/R4/R5) vs
      the magnitude-only ``gain >= eps`` (R6, AMENDMENT 1).

    Returns ``(promote, p, gain, b, c, structural_ok, blind_ok, stat_ok)`` so each rule can
    assemble an auditable ``reasons`` list.
    """
    struct = _structural_ok(pool)
    blind_ok = (pool.get("blind") is True) if require_blind else True
    b, c = _items_bc(pool["items"])
    gain = _gain(pool)
    if use_significance:
        p = mcnemar_two_sided(b, c)
        stat_ok = (p < alpha) and (gain >= eps)
    else:
        p = None
        stat_ok = gain >= eps
    promote = struct and blind_ok and stat_ok
    return promote, p, gain, b, c, struct, blind_ok, stat_ok


def _result(promote: bool, p, gain: float, reasons: list[str]) -> dict:
    return {
        "promote": bool(promote),
        "p": p,
        "gain": float(gain),
        "reasons": list(reasons),
        "recomputable": True,
    }


# ------------------------------------------------------------------------------ decide

def decide(rule: str, pool: dict) -> dict:
    """Return ``{"promote", "p", "gain", "reasons", "recomputable"}`` for one decision rule.

    ``pool`` is a paired pool row::

        {"name": str, "n": int, "blind": bool, "truth": str,
         "chal_policy": str, "inc_policy": str,
         "hidden_passed": bool, "safety_passed": bool,
         "rollback_available": bool, "bundle_signature_valid": bool,
         "items": [{"qid": str, "chal": bool, "inc": bool}, ...],
         # optional, R7 only:
         "candidates": [<pool>, ...]}

    Pure: same input -> same output; no network, clock, filesystem or random access.  ``p`` is the
    exact two-sided significance (float) for R1/R3/R4/R5 and ``None`` for R2/R6/R7 (rules with no
    significance test).  ``recomputable`` is ``True`` for every rule.
    """
    if not isinstance(rule, str):
        raise TypeError(f"rule must be a string, got {rule!r}")
    rule = rule.upper()
    if rule not in RULES:
        raise ValueError(f"unknown rule {rule!r}; expected one of {RULES}")

    gain = _gain(pool)
    b, c = _items_bc(pool["items"])

    if rule == "R2":
        return _result(
            gain > 0, None, gain,
            [f"R2 point: gain={gain!r} = (b-c)/n with b={b} c={c}; promote iff gain > 0"])

    if rule == "R3":
        chal, inc = _totals(pool["items"])
        n = len(pool["items"])
        p = _fisher_exact_two_sided(chal, inc, n)
        promote = (p < ALPHA) and (gain >= EPS)
        return _result(
            promote, p, gain,
            [f"R3 unpaired: two-sided Fisher exact test on the independent-sample 2x2 table "
             f"(chal {chal}/{n} pass, inc {inc}/{n} pass); p={p!r}, gain={gain!r}; "
             f"promote iff p < {ALPHA} and gain >= {EPS}"])

    if rule == "R7":
        return _decide_r7(pool)

    gate_kwargs = {
        "R1": dict(alpha=ALPHA, eps=EPS, require_blind=True, use_significance=True),
        "R4": dict(alpha=ALPHA, eps=EPS, require_blind=False, use_significance=True),
        "R5": dict(alpha=ALPHA_LOOSE, eps=EPS, require_blind=True, use_significance=True),
        "R6": dict(alpha=ALPHA, eps=EPS, require_blind=False, use_significance=False),
    }
    kw = gate_kwargs[rule]
    promote, p, gain, b, c, struct, blind_ok, stat_ok = _gate(pool, **kw)
    label = {
        "R1": "R1 gate (alpha=0.05, eps=0.02, blind set)",
        "R4": "R4 nonblind (gate's paired test, blindness ignored)",
        "R5": "R5 loose (alpha=0.20, eps=0.02, blind set)",
        "R6": "R6 no-stat (AMENDMENT 1: magnitude gain>=eps kept, significance test dropped)",
    }[rule]
    statistical = (f"exact McNemar p={p!r}" if p is not None
                   else "no significance test")
    reasons = [
        f"{label}: b={b} c={c} d={b+c} gain={gain!r}; {statistical}",
        f"structural_keys_ok={struct} (fail-closed: a missing key is False)",
    ]
    if kw["require_blind"]:
        reasons.append(f"blind_ok={blind_ok} (requires pool['blind'] is True)")
    else:
        reasons.append("blindness NOT required")
    return _result(promote, p, gain, reasons)


def _decide_r7(pool: dict) -> dict:
    """R7 ``bestofk``: promote iff the point-estimate best of ``k = 8`` candidates has gain > 0.

    The operative reading reads ``pool["candidates"]`` as the pinned ``k = 8`` candidate blocks of
    PREREG S1 rule 5 (prefix ``j = 1..8``); this module uses the **first eight** candidates and
    never builds or mixes their families (family-appropriate construction is Task 1's job).  The
    absent-``candidates`` case degenerates to ``k = 1`` -- the best of one candidate is the pool
    itself, behaviourally R2 -- and is recorded in ``reasons`` so it can never be taken silently;
    it is an interface note only, never an operative reading (PREREG S2.1 / S5.2).
    """
    candidates = pool.get("candidates") if isinstance(pool, dict) else None
    if candidates is None or (isinstance(candidates, list) and not candidates):
        gain = _gain(pool)
        return _result(
            gain > 0, None, gain,
            [f"R7 bestofk: DEGENERATE (no candidates) -> k = 1, best of one candidate is the "
             f"pool itself, behaviourally R2 (interface note, never an operative reading); "
             f"gain={gain!r}; promote iff gain > 0"])
    if not isinstance(candidates, list):
        raise TypeError(f"pool['candidates'] must be a list of candidate pools, got {type(candidates)!r}")
    cands = candidates[:K_R7]              # prefix j = 1..k of the pinned stream
    best_gain = max(_gain(c) for c in cands)
    promote = best_gain > 0
    used = len(cands)
    note = (f"pinned k={K_R7} prefix used" if used == K_R7
            else f"WARNING: only {used} candidate(s) supplied (fewer than pinned k={K_R7})")
    return _result(
        promote, None, best_gain,
        [f"R7 bestofk: best point-estimate gain over the first min(8, len) candidates = "
         f"{best_gain!r} ({used} candidate(s), {note}); promote iff best gain > 0"])