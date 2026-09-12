"""Pool layer of the round-5 gate decision-rule ablation (PLAN-NOVELTY.md Task 1 + Task 3).

Frozen protocol (authoritative): ``results/rounds/round5/PREREG-round5.md``
  - §1 rules 1-5 ......... zero-effect construction, pinned randomness (SEED / child_seed /
                           one RNG per source pool / K = 200), ``d == 0`` is an error,
                           the R7 candidate streams of rule 5
  - §1.1 ................. orientation convention, binding for every pool row
  - §3 ................... pool families + observed-pool roster (0-based indices 0..3)
  - §8 ................... discordance granularity (large-d observed pools are required)

Two artefacts are produced here:

``results/rounds/round5/pools.json``
    exactly ``build_pools()`` -- the four observed pools plus, for each of them, ``K = 200``
    permutation-null pools. One pool per line (valid JSON, greppable, diffable).

``results/rounds/round5/PILOT.json``
    produced by ``scripts/pilot_round5.py``, which imports this module.

Construction (PREREG §1, verbatim in behaviour)
-----------------------------------------------
Given a paired pool whose discordant item set has size ``d > 0``, each discordant item is
independently swapped (chal <-> inc) with probability 0.5; concordant items are copied
through unchanged.  The true treatment effect of the result is identically 0 while the
discordant total stays ``d``.  Draws: one ``random.Random(seed)`` per source pool, consumed
sequentially -- for null index ``i = 0 .. k-1`` walk the pool's frozen item order and draw
one ``rng.random()`` per discordant item, swapping iff the draw is ``< 0.5``.  There is no
re-seeding between nulls.  ``d == 0`` raises ``ValueError`` (never a silent skip).

The R7 candidate streams of §1 rule 5 continue the *same* RNG instance, after every null
block has been drawn and never interleaved with them: first the NULL-family relabelling
stream and then (POSITIVE source pool only) the POSITIVE-family label-preserving item
bootstrap.  ``C(source_pool, i, j)`` is therefore a pure function of
``(SEED, source_pool_index, frozen item order, i, j)``.

Orientation (§1.1, binding)
---------------------------
``chal`` is the candidate being promoted, ``inc`` the incumbent;
``b`` = # items where chal passes and inc fails, ``c`` = the reverse,
``gain = (total_chal - total_inc) / n = (b - c) / n``.  Every pool row declares
``(chal_policy, inc_policy)``; a signed gain is never transcribed without its orientation.

Structural gate keys (§1, binding)
----------------------------------
Every pool built here -- observed and null alike -- carries ``hidden_passed``,
``safety_passed``, ``rollback_available`` and ``bundle_signature_valid`` set to ``True``.
They are constants of this study's schema, which is what makes R1's five-key conjunction
reduce to ``statistical_passed`` and makes the gate's negative conclusion non-vacuous.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evokit.stats import mcnemar_two_sided  # noqa: E402  (integrity check on observed pools)

ROUND4 = ROOT / "results" / "rounds" / "round4"
ROUND5 = ROOT / "results" / "rounds" / "round5"

# ---------------------------------------------------------------- pinned constants (§1)

SEED = 20260912            # §1 rule 1: literal constant, the date of the freeze
K = 200                    # §1: permutation-null pools per source pool
K_CANDIDATES = 8           # §1 rule 5 / §5.2: the pre-run-fixed k for R7's operative reading

GATE_KEYS = ("hidden_passed", "safety_passed", "rollback_available", "bundle_signature_valid")

# ------------------------------------------------- frozen observed-pool roster (§1/§3)
#
# This roster (together with its mirror in PLAN-NOVELTY.md Task 3) is the ONLY definition
# of ``source_pool_index`` -> ``child_seed``.  It must not be renumbered or reordered:
# renumbering would silently change every child seed and therefore every null pool.
ROSTER = (
    {
        "index": 0,
        "source_pool": "positive-cotzero-vs-direct",
        "source_file": "trackA-merged.json",
        "chal_policy": "cot-zero",
        "inc_policy": "direct",
        "declared_null_source": True,      # §1: all four roster entries are null sources
        "blind": True,                     # derived, see BLIND_POLICY note below
        "family": "POSITIVE",              # §3
        "provenance": "trackA, d = 159",
        "dataset": "examples/heldout40.json + examples/heldout-batch2-160.json",
    },
    {
        "index": 1,
        "source_pool": "mid-stepcalc-vs-cotzero",
        "source_file": "trackA-merged.json",
        "chal_policy": "step-calc",
        "inc_policy": "cot-zero",
        "declared_null_source": True,
        "blind": True,
        # §3 enumerates NULL / POSITIVE / MARGINAL only; this observed pool is not one of
        # §3's two named real pools, so it carries the explicit placeholder below rather
        # than an invented family name.
        "family": "OBSERVED_OTHER",
        "provenance": "trackA, d = 16 (PREREG §8: primary pool for the alpha/unpaired arms)",
        "dataset": "examples/heldout40.json + examples/heldout-batch2-160.json",
    },
    {
        "index": 2,
        "source_pool": "mid-stepcalc-vs-fewshot",
        "source_file": "trackA-merged.json",
        "chal_policy": "step-calc",
        "inc_policy": "few-shot",
        "declared_null_source": True,
        "blind": True,
        "family": "OBSERVED_OTHER",
        "provenance": "trackA, d = 23 (PREREG §8: large-discordance pool)",
        "dataset": "examples/heldout40.json + examples/heldout-batch2-160.json",
    },
    {
        "index": 3,
        "source_pool": "marginal-stepcalc-vs-concise",
        "source_file": "trackC-qwen2-7b-heldout40.json",
        "chal_policy": "step-calc",
        "inc_policy": "concise-reason",
        "declared_null_source": True,
        "blind": True,
        "family": "MARGINAL",              # §3
        "provenance": "qwen2:7b, d = 6",
        "dataset": "examples/heldout40.json",
    },
)

DECLARED_NULL_SOURCES = tuple(r["index"] for r in ROSTER if r["declared_null_source"])

POSITIVE_SOURCE_INDEX = 0      # §1 rule 5 / §3: the POSITIVE family has exactly one pool

# Both source artefacts are the round-4 *blind* held-out sets (ROUND4-TRACKA-RESULT.md:
# "该盲集"; ROUND4-TRACKC-RESULT.md: "n=200 合并盲集"), so every roster entry is blind and
# its nulls inherit that label (a null pool uses its source pool's own questions).
BLIND_POLICY = "inherited_from_source"
ITEM_ORDER_POLICY = "qid-ascending (equals the committed details key order of the source artefact)"


# ------------------------------------------------------------------------- little helpers

def child_seed(source_pool_index: int) -> int:
    """§1 rule 2: ``child_seed = SEED + source_pool_index`` (0-based roster position)."""
    if not isinstance(source_pool_index, int) or source_pool_index < 0:
        raise ValueError(f"source_pool_index must be a non-negative int, got {source_pool_index!r}")
    return SEED + source_pool_index


def discordant_total_from_items(items) -> int:
    """``d`` = number of items whose challenger/incumbent outcomes differ."""
    return sum(1 for it in items if bool(it["chal"]) != bool(it["inc"]))


def _discordant_ok(pool: dict) -> bool:
    return pool.get("meta", {}).get("discordant_total") == discordant_total_from_items(pool["items"])


def _items_bc(pool: dict):
    b = sum(1 for it in pool["items"] if it["chal"] and not it["inc"])
    c = sum(1 for it in pool["items"] if it["inc"] and not it["chal"])
    return b, c


def _gain(pool: dict) -> float:
    n = len(pool["items"])
    if n == 0:
        raise ValueError("pool has no items")
    total_chal = sum(1 for it in pool["items"] if it["chal"])
    total_inc = sum(1 for it in pool["items"] if it["inc"])
    return (total_chal - total_inc) / n


def _relabel(items, rng: random.Random):
    """§1 rules 1/3: copy the items, swapping each discordant item's labels independently
    with probability 0.5.  Exactly one ``rng.random()`` draw per discordant item, walked in
    the pool's frozen item order; concordant items are never drawn for."""
    out = [dict(it) for it in items]
    for it in out:
        if bool(it["chal"]) != bool(it["inc"]):
            if rng.random() < 0.5:
                it["chal"], it["inc"] = it["inc"], it["chal"]
    return out


def _structural_keys() -> dict:
    """§1: the four structural gate keys are true by construction on every pool."""
    return {key: True for key in GATE_KEYS}


def _base_row(pool: dict, items, truth: str, name: str, seed: int, **meta_extra) -> dict:
    meta = {
        "source_pool": pool["meta"]["source_pool"],
        "source_pool_index": pool["meta"]["source_pool_index"],
        "discordant_total": discordant_total_from_items(items),
        "chal_policy": pool["chal_policy"],
        "inc_policy": pool["inc_policy"],
        "seed": seed,
        "family": pool["meta"].get("family", "TEST"),
        "blind": pool["blind"],
        "blind_basis": pool["meta"].get("blind_basis", "supplied by the caller"),
        "blind_policy": BLIND_POLICY,
        "item_order": ITEM_ORDER_POLICY,
    }
    meta.update(meta_extra)
    return {
        "name": name,
        "n": len(items),
        "blind": pool["blind"],
        "truth": truth,
        "chal_policy": pool["chal_policy"],
        "inc_policy": pool["inc_policy"],
        "items": items,
        "meta": meta,
        **_structural_keys(),
    }


# ------------------------------------------------------------ observed pool construction

def _load_source(source_file: str) -> dict:
    path = ROUND4 / source_file
    return json.loads(path.read_text(encoding="utf-8"))


def build_observed_pools() -> list[dict]:
    """The four observed pools of the frozen roster, in roster order (Task 3).

    Every figure is recomputed from the committed round-4 artefact's per-question
    ``details``; the artefact's own ``pairs`` record is used only as a cross-check, so a
    hand-edited or truncated source file is caught rather than inherited.
    """
    pools = []
    for entry in ROSTER:
        pools.append(_build_observed_pool(entry))
    return pools


def _build_observed_pool(entry: dict) -> dict:
    data = _load_source(entry["source_file"])
    details = data["details"]
    policies = data["meta"]["policies"]
    n = data["meta"]["n"]
    chal, inc = entry["chal_policy"], entry["inc_policy"]
    for policy in (chal, inc):
        if policy not in policies:
            raise ValueError(f"{entry['source_pool']}: policy {policy!r} not in {policies}")

    # §1: the pool's frozen item order is the committed details key order; verify that it is
    # qid-ascending so the order cannot drift with a different JSON writer.
    keys = list(details)
    if keys != sorted(keys):
        raise ValueError(
            f"{entry['source_pool']}: committed details key order is not qid-ascending; "
            "the frozen item order of §1 must be re-declared explicitly instead of assumed")

    items = [{"qid": qid, "chal": bool(details[qid][chal]["passed"]),
              "inc": bool(details[qid][inc]["passed"])} for qid in keys]
    if len(items) != n:
        raise ValueError(f"{entry['source_pool']}: {len(items)} items but meta.n = {n}")

    b, c = _items_bc({"items": items})
    d = b + c
    gain = _gain({"items": items})
    totals = {p: sum(1 for row in details.values() if row[p]["passed"]) for p in policies}
    if d == 0:
        raise ValueError(f"{entry['source_pool']}: discordant_total == 0; the frozen roster "
                         "declares all four entries as null sources (PREREG §1 rule 4)")

    # §1.1 arithmetic, recomputed from details only.
    if (b - c) != (totals[chal] - totals[inc]):
        raise ValueError(f"{entry['source_pool']}: (b - c) != totals[chal] - totals[inc]")
    if abs(gain - (totals[chal] - totals[inc]) / n) > 1e-12:
        raise ValueError(f"{entry['source_pool']}: gain != (total_chal - total_inc)/n")

    # Cross-check against the artefact's own pair record (orientation-aware).
    key = f"{chal}_vs_{inc}"
    reversed_key = f"{inc}_vs_{chal}"
    if key in data["pairs"]:
        rec = data["pairs"][key]            # better counts the second-named (inc) policy
        exp_better, exp_worse = c, b
        exp_gain = -gain
    elif reversed_key in data["pairs"]:
        rec = data["pairs"][reversed_key]
        exp_better, exp_worse = b, c
        exp_gain = gain
    else:
        raise ValueError(f"{entry['source_pool']}: no pair record for {chal} vs {inc}")
    for field, want in (("better", exp_better), ("worse", exp_worse)):
        if rec[field] != want:
            raise ValueError(f"{entry['source_pool']}: pair record {field}={rec[field]} "
                             f"but orientation arithmetic gives {want}")
    if abs(rec["gain"] - exp_gain) > 1e-12:
        raise ValueError(f"{entry['source_pool']}: pair record gain={rec['gain']} "
                         f"but orientation arithmetic gives {exp_gain}")
    p_exact = mcnemar_two_sided(b, c)
    if abs(rec["p"] - p_exact) > 1e-12:
        raise ValueError(f"{entry['source_pool']}: pair record p={rec['p']} != {p_exact}")

    pool = {
        "name": entry["source_pool"],
        "n": n,
        "blind": entry["blind"],
        "truth": "observed",
        "chal_policy": chal,
        "inc_policy": inc,
        "items": items,
        "meta": {
            "source_pool": entry["source_pool"],
            "source_pool_index": entry["index"],
            "discordant_total": d,
            "chal_policy": chal,
            "inc_policy": inc,
            "seed": child_seed(entry["index"]),
            "seed_basis": "child_seed = SEED + source_pool_index (PREREG §1 rule 2)",
            "family": entry["family"],
            "provenance": entry["provenance"],
            "source_file": f"results/rounds/round4/{entry['source_file']}",
            "dataset": entry["dataset"],
            "model": data["meta"]["model"],
            "blind": entry["blind"],
            "blind_basis": f"source artefact is a round-4 blind held-out set: {entry['dataset']}",
            "blind_policy": BLIND_POLICY,
            "item_order": ITEM_ORDER_POLICY,
            "discordant_checks": {"b": b, "c": c, "d": d, "gain": gain, "mcnemar_p": p_exact},
            "declared_null_source": entry["declared_null_source"],
        },
        **_structural_keys(),
    }
    return pool


# --------------------------------------------------- permutation nulls (§1 rules 1-3)

def permutation_nulls(pool: dict, k: int, seed: int) -> list[dict]:
    """``k`` permutation-null pools of ``pool`` under the pinned construction of §1.

    One ``random.Random(seed)`` instance is consumed sequentially over the ``k`` null
    blocks (no per-null re-seeding); per block, each discordant item is drawn once in the
    pool's frozen item order and swapped iff the draw is ``< 0.5``.  Raises ``ValueError``
    if the pool has no discordant item (§1 rule 4 -- a ``d == 0`` pool is never a null
    source, and a silent skip would shrink the FPR denominator without a record).
    """
    if k <= 0:
        raise ValueError(f"k must be positive, got {k!r}")
    d = discordant_total_from_items(pool["items"])
    if d == 0:
        raise ValueError(
            f"source pool {pool.get('name')!r} has discordant_total == 0: there is no "
            "discordant item to relabel, so it cannot be a null source (PREREG §1 rule 4); "
            "it may appear only as an observed pool explicitly declared 'not a null source'")
    rng = random.Random(seed)
    nulls = []
    for i in range(k):
        items = _relabel(pool["items"], rng)
        nulls.append(_base_row(
            pool, items, "null", f"{pool['meta']['source_pool']}#null-{i:04d}", seed,
            null_index=i,
            truth_basis="permutation relabelling of the discordant items; true effect identically 0",
            r2_expectation_note=("E[FPR_R2] = (1 - P(tie))/2, PREREG §4.1 -- constructive, "
                                 "not a measurement"),
        ))
    return nulls


# ------------------------------------------------- R7 candidate streams (§1 rule 5)

def _candidate_row(pool: dict, items, name: str, seed: int, unit: int, j: int,
                   candidate_family: str, k_units: int, basis: str) -> dict:
    return _base_row(
        pool, items,
        "null" if candidate_family == "NULL" else "observed",
        name, seed,
        candidate_unit=unit, candidate_index=j, candidate_family=candidate_family,
        is_candidate=True, k_units=k_units, candidate_basis=basis)


def iter_null_candidate_blocks(pool: dict, k_units: int = K, k_prefix: int = K_CANDIDATES,
                               seed: int | None = None):
    """Yield ``(unit_index, candidate_index, candidate_pool)`` for the NULL-family stream.

    §1 rule 5: the source pool's single RNG instance is continued *after* all ``k_units``
    null blocks have been drawn (never interleaved); blocks are consumed ``i`` outer,
    ``j`` inner, and each block relabels exactly as a null pool does.  ``C(source_pool, i, j)``
    is a pure function of ``(SEED, source_pool_index, frozen item order, i, j)``.

    The stream itself is always the pinned ``j = 1..K_CANDIDATES`` stream: ``k_prefix`` only
    *filters* which blocks of that one stream are yielded, so the ``k``-subset of a unit
    (PREREG §4: "the prefix ``j = 1..k``") is literally a prefix of the same nested stream
    and the reported ``k`` can never reshape or re-draw it.
    """
    if not 0 < k_prefix <= K_CANDIDATES or k_units < 0:
        raise ValueError(f"bad stream shape: k_prefix={k_prefix!r} k_units={k_units!r}")
    if seed is None:
        seed = child_seed(pool.get("meta", {}).get("source_pool_index", 0))
    rng = random.Random(seed)
    for _ in range(k_units):                      # the null blocks come first (§1 rule 5)
        _relabel(pool["items"], rng)
    for i in range(k_units):
        for j in range(1, K_CANDIDATES + 1):      # this draw budget never depends on k_prefix
            items = _relabel(pool["items"], rng)
            if j > k_prefix:
                continue
            yield i, j, _candidate_row(
                pool, items, f"{pool['meta']['source_pool']}#C{i}-{j}", seed, i, j, "NULL",
                k_units,
                "relabelling candidate: true effect identically 0 (NULL-family use only)")


def positive_candidate_blocks(pool: dict, k_units: int = K, k_prefix: int = K_CANDIDATES,
                              seed: int | None = None) -> list[dict]:
    """The POSITIVE-family label-preserving item bootstrap of §1 rule 5 (one unit, ``i = 0``).

    Drawn only after the pool's ``k_units`` null blocks *and* its whole NULL-family stream
    (``k_units x K_CANDIDATES`` relabelling blocks, with the pinned ``j = 1..8``) have been
    consumed.  Each of the ``k_prefix`` candidates resamples ``n`` items with replacement,
    drawing one ``rng.random()`` per resampled position and taking index ``int(u x n)`` of the
    pool's frozen item order, leaving every ``chal``/``inc`` label exactly as observed: the
    observed positive effect survives the draw.  Nothing is relabelled.  As in the NULL-family
    stream, the pinned ``j = 1..K_CANDIDATES`` stream is always drawn and ``k_prefix`` only
    filters it, so ``k_prefix`` can never reshape the stream.
    """
    if not 0 < k_prefix <= K_CANDIDATES or k_units < 0:
        raise ValueError(f"bad stream shape: k_prefix={k_prefix!r} k_units={k_units!r}")
    d = discordant_total_from_items(pool["items"])
    if d == 0:
        raise ValueError("a POSITIVE-family bootstrap candidate needs a pool with a real effect")
    if seed is None:
        seed = child_seed(pool.get("meta", {}).get("source_pool_index", 0))
    n = len(pool["items"])
    rng = random.Random(seed)
    for _ in range(k_units):                                  # null blocks
        _relabel(pool["items"], rng)
    for _ in range(k_units * K_CANDIDATES):                   # whole NULL-family stream
        _relabel(pool["items"], rng)
    out = []
    for j in range(1, K_CANDIDATES + 1):
        items = []
        for _ in range(n):
            u = rng.random()
            idx = int(u * n)
            if idx >= n:                                      # rng.random() < 1.0, kept for safety
                idx = n - 1
            items.append(dict(pool["items"][idx]))
        if j > k_prefix:
            continue
        out.append(_candidate_row(
            pool, items, f"{pool['meta']['source_pool']}#Cpos0-{j}", seed, 0, j, "POSITIVE",
            k_units,
            "label-preserving item bootstrap: resampled with replacement, labels exactly as "
            "observed; a construction (not a measurement), never a null pool (PREREG §1 rule 5)"))
    return out


# --------------------------------------------------------------------- assembly (Task 3)

def build_pools() -> list[dict]:
    """All pools of the ablation's pool layer: the observed pools + their permutation nulls.

    Observed pools come first in roster order, then each source pool's ``K`` nulls grouped
    by source pool.  Every declared null source contributes exactly ``K`` nulls (§1 rule 4);
    a source pool with ``d == 0`` raises ``ValueError`` through ``permutation_nulls``.
    R7's candidate pools are deliberately NOT part of this list: they are candidates, not
    null pools, and must never be counted in the NULL set (PREREG §1 / §5.2).  Generate them
    with ``iter_null_candidate_blocks`` / ``positive_candidate_blocks``.
    """
    observed = build_observed_pools()
    pools = list(observed)
    for pool in observed:
        index = pool["meta"]["source_pool_index"]
        pools.extend(permutation_nulls(pool, K, child_seed(index)))
    return pools


def write_pools_json(path: Path | None = None) -> Path:
    """Write ``pools.json`` as one pool per line (valid JSON array, diffable and greppable)."""
    pools = build_pools()
    out = Path(path) if path is not None else ROUND5 / "pools.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    body = ",\n".join(json.dumps(p, ensure_ascii=False, separators=(",", ":")) for p in pools)
    out.write_text("[\n" + body + "\n]\n", encoding="utf-8")
    return out


def main() -> int:
    pools = build_pools()
    path = write_pools_json()
    observed = [p for p in pools if p["truth"] == "observed"]
    nulls = [p for p in pools if p["truth"] == "null"]
    print(f"SEED={SEED} K={K} K_CANDIDATES={K_CANDIDATES} "
          f"declared_null_sources={list(DECLARED_NULL_SOURCES)}")
    print(f"observed={len(observed)} nulls={len(nulls)} total={len(pools)} "
          f"-> {path.relative_to(ROOT)} ({path.stat().st_size} bytes)")
    print("observed roster (index, source_pool, n, d, b, c, gain, blind, chal->inc):")
    for p in observed:
        b, c = _items_bc(p)
        print(f"  {p['meta']['source_pool_index']} {p['name']:32s} n={p['n']:4d} "
              f"d={p['meta']['discordant_total']:4d} b={b:4d} c={c:4d} "
              f"gain={_gain(p):+.4f} blind={p['blind']} "
              f"({p['chal_policy']} vs {p['inc_policy']})")
    print("nulls per source pool: " + ", ".join(
        f"{src}={sum(1 for p in nulls if p['meta']['source_pool'] == src)}"
        for src in (r["source_pool"] for r in ROSTER)))
    assert all(p[key] is True for p in pools for key in GATE_KEYS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
