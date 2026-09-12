"""Pool layer of the round-5 gate decision-rule ablation (PLAN-NOVELTY.md Task 1 + Task 3).

Frozen protocol (authoritative): ``results/rounds/round5/PREREG-round5.md``
  - §1 rules 1-5 ......... zero-effect construction, pinned randomness (SEED / child_seed /
                           one RNG per source pool / K = 200), ``d == 0`` is an error,
                           the R7 candidate streams of rule 5
  - §1.1 ................. orientation convention, binding for every pool row
  - §3 ................... pool families + observed-pool roster
  - §5A .................. R4 (non-blind arm) -- **EVALUATED** (correction round, 2026-09-12)
  - §8 ................... discordance granularity (large-d observed pools are required)

Two artefacts are produced here:

``results/rounds/round5/pools.json``
    an object ``{"meta": ..., "pools": [...]}`` whose ``pools`` key is exactly ``build_pools()``:
    the observed pools (roster indices 0-9) first, then, for **each declared null source** of
    indices 0-3, ``K = 200`` permutation-null pools.  One pool per line (valid JSON, greppable,
    diffable).

``results/rounds/round5/PILOT.json``
    produced by ``scripts/pilot_round5.py``, which imports this module.

Observed-pool roster (frozen)
-----------------------------
* **Indices 0-3 -- blind held-out sets.**  Four observed pools derived from the committed round-4
  blind artefacts; these are the study's **declared null sources**, so each contributes exactly
  ``K = 200`` permutation nulls (the whole NULL set of this study).
* **Indices 4-9 -- non-blind selection sets (correction round, 2026-09-12; index 9 added by fix
  round 3).**  Six observed pools derived from the loop's own **selection-set** runs, declared
  ``blind = False``.  They are
  declared **``declared_null_source = False``**: rule 4's *not a null source* escape hatch is
  honoured, so they contribute **no** null pools and the NULL set of this study stays exactly the
  800 blind nulls of indices 0-3.  Adding them therefore cannot move any blind FPR, and indices
  0-3 stay byte-identical to the pre-correction artefact (see ``PRE_CORRECTION_0_3``, anchored and
  asserted by ``tests/test_build_pools.py``).

Exhaustiveness of the non-blind block (fix round 3)
---------------------------------------------------
The non-blind block is **exhaustive over the candidate arms the committed artefacts contain**:
both ``results/runs/*.json`` run reports, plus ``results/rounds/round3/pilot-train40.json``, were
enumerated arm by arm, and every arm is either a rostered pool (indices 4-9) or the **one**
explicitly disclosed exclusion -- the ``reworded-direct`` arm of run ``20260907-135728``, whose
candidate re-labels the baseline policy, so ``b = c = d = 0`` and there is no discordance structure
to pool (PREREG §1 rule 4).  Earlier fix rounds listed only five of the six eligible arms and still
asserted exhaustiveness; the omitted arm -- ``rounding-aware`` vs ``concise-reason`` in run
``20260908-235617`` (n=40, b=8, c=2, d=10, gain=+0.150, exact McNemar p=0.109375) -- is index 9.
The enumeration is pinned as a test
(``tests/test_build_pools.py::test_the_nonblind_roster_is_exhaustive_over_the_committed_arms``).

Correction-round record (R4 **is** evaluable)
---------------------------------------------
The earlier fix round recorded that "``results/runs/*.json`` carry only aggregate fields and
contain no per-question details", and on that basis marked R4 ``not evaluated`` and installed a
machine guard that refused any non-blind pool.  **That premise was false** -- a controller
inspection error at the top-level-key depth only.  ``baseline.outcomes[]`` and
``candidates[].evaluation.outcomes[]`` do carry per-question ``{task_id, passed, details{policy}}``
records over the 40 selection-set ids ``gsm8k-01..40``, and
``results/rounds/round3/pilot-train40.json`` carries the same per-id detail
(``"oracle": "train-only"``).  The six non-blind pools of indices 4-9 are re-derived from those
files here.  R4 is evaluable and IS evaluated; no synthetic pool was needed and none was used.

Provenance of the cross-check (restated in fix round 3, corrected in fix round 4 -- **not** an
independence claim)
-----------------------------------------------------------------------------------------------
What the derived counts are checked against is the **same artefact they are derived from**, and
*which* recorded figure each roster row is checked against differs by row.  Fix round 4 corrected
the earlier sentence here that said the four non-active arms "carry no recorded n=40 aggregate at
all": that sentence was false, and the accurate per-row account is --

* **rows 4 and 6** -- the arm each run promoted as its **active candidate** -- are checked against
  that run's own ``statistical_decision`` block, ``(better, worse, p_value, mean_gain)``;
* **rows 5, 7 and 9** -- the other arms of the same two runs -- are checked only against their own
  recorded **marginal** aggregates, the located candidate's
  ``candidates[].evaluation.passed/total`` and the run's ``baseline.passed/total``.  **No paired
  ``(b, c, gain, p)`` aggregate for those rows is recorded in any artefact**, so their four paired
  figures are pure re-derivations;
* **row 8** (the round-3 pilot) is checked against the pilot's recorded paired counts
  (``paired.reflect_better`` for ``better``, ``paired.step_better`` for ``worse``), its recorded
  exact McNemar ``paired.mcnemar_p_value``, and its per-arm recorded marginal ``passed/total``.  The
  pilot records no ``gain`` field, so row 8's gain is a pure re-derivation.

``_source_run`` / ``_source_pilot`` recompute the counts from the source's per-question records
(``baseline.outcomes[]`` / ``candidates[].evaluation.outcomes[]``; the pilot's per-policy
``details``) and require the artefact's own records to agree with that recomputation.  That is a
**same-source consistency check** -- it catches a truncated or hand-edited run file -- and it is not
an independent record.  The registry's
``history[1]`` / ``history[3]`` entries under ``registry/version-registry.json`` carry a
byte-identical copy of those same two blocks (asserted in
``tests/test_build_pools.py::test_registry_carries_a_verbatim_copy_not_an_independent_record``), so
citing the registry adds no independence.  The registry's *current* evidence entry for run
``eecacc0312d7`` (``history[4]``) records a different quantity -- the merged n=200 held-out result
(``paired_better 33`` / ``paired_worse 4``, ``p = 1.08e-6``) -- which is **not** the n=40
selection-set count and does not corroborate it.  An earlier round described these n=40 numbers as
"independently recorded by the registry"; that was an overstatement and is corrected here.

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

import hashlib
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evokit.stats import mcnemar_two_sided  # noqa: E402  (integrity check on observed pools)

ROUND3 = ROOT / "results" / "rounds" / "round3"
ROUND4 = ROOT / "results" / "rounds" / "round4"
ROUND5 = ROOT / "results" / "rounds" / "round5"
RUNS = ROOT / "results" / "runs"

# ---------------------------------------------------------------- pinned constants (§1)

SEED = 20260912            # §1 rule 1: literal constant, the date of the freeze
K = 200                    # §1: permutation-null pools per source pool
K_CANDIDATES = 8           # §1 rule 5 / §5.2: the pre-run-fixed k for R7's operative reading

GATE_KEYS = ("hidden_passed", "safety_passed", "rollback_available", "bundle_signature_valid")

# ------------------------------------------------------- source classification (blindness)
#
# A pool's ``blind`` flag is not a free choice: it must match the *declared source* of the pool.
# A blind held-out artefact -> blind=True; a selection-set run (the loop's own development set,
# which is what "non-blind" means) -> blind=False.  ``check_blind_labels()`` enforces this on the
# artefact and the observed-pool loader enforces it at build time, so a mislabelled pool fails
# loudly instead of making R4 look evaluable (or unevaluable) for the wrong reason.
BLIND_SOURCE_CLASS = "blind-heldout-set"
NONBLIND_SOURCE_CLASS = "selection-set (non-blind)"
_BLIND_BY_SOURCE_CLASS = {BLIND_SOURCE_CLASS: True, NONBLIND_SOURCE_CLASS: False}

# --------------------------------------------- frozen observed-pool roster (indices 0-9)
#
# This roster (together with its mirror in PLAN-NOVELTY.md Task 3) is the ONLY definition
# of ``source_pool_index`` -> ``child_seed``.  Indices 0-3 must not be renumbered or reordered:
# renumbering would silently change every child seed and therefore every null pool.  Indices 4-9
# are appended after them for exactly that reason (each source pool owns its own RNG, so appending
# cannot perturb the earlier child seeds), and they are *not* null sources.
ROSTER = (
    {
        "index": 0,
        "source_pool": "positive-cotzero-vs-direct",
        "source_kind": "round4",
        "source_file": "trackA-merged.json",
        "chal_policy": "cot-zero",
        "inc_policy": "direct",
        "declared_null_source": True,      # §1: all four blind roster entries are null sources
        "blind": True,                     # derived from the source class, see BLIND_POLICY note
        "family": "POSITIVE",              # §3
        "provenance": "trackA, d = 159",
        "dataset": "examples/heldout40.json + examples/heldout-batch2-160.json",
    },
    {
        "index": 1,
        "source_pool": "mid-stepcalc-vs-cotzero",
        "source_kind": "round4",
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
        "source_kind": "round4",
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
        "source_kind": "round4",
        "source_file": "trackC-qwen2-7b-heldout40.json",
        "chal_policy": "step-calc",
        "inc_policy": "concise-reason",
        "declared_null_source": True,
        "blind": True,
        "family": "MARGINAL",              # §3
        "provenance": "qwen2:7b, d = 6",
        "dataset": "examples/heldout40.json",
    },
    # -------------------------------------------------- indices 4-9: correction + fix round 3
    {
        "index": 4,
        "source_pool": "nonblind-concise-vs-direct",
        "source_kind": "run",
        # Located by (baseline policy, candidate policy), never by trusting a filename; the
        # located path is then asserted to equal the declaration below.
        "source_probe": {"baseline_policy": "direct", "candidate_policy": "concise-reason"},
        "declared_source_file": "results/runs/20260907-135728.json",
        "chal_policy": "concise-reason",
        "inc_policy": "direct",
        "declared_null_source": False,     # rule 4's "not a null source" escape hatch, honoured
        "blind": False,
        "family": "NONBLIND_SELECTION",
        "provenance": "selection set, d = 20",
        "dataset": "the loop's own development/selection set, 40 ids gsm8k-01..40",
    },
    {
        "index": 5,
        "source_pool": "nonblind-doublecheck-vs-direct",
        "source_kind": "run",
        "source_probe": {"baseline_policy": "direct", "candidate_policy": "double-check"},
        "declared_source_file": "results/runs/20260907-135728.json",
        "chal_policy": "double-check",
        "inc_policy": "direct",
        "declared_null_source": False,
        "blind": False,
        "family": "NONBLIND_SELECTION",
        "provenance": "selection set, d = 6",
        "dataset": "the loop's own development/selection set, 40 ids gsm8k-01..40",
    },
    {
        "index": 6,
        "source_pool": "nonblind-stepcalc-vs-concise",
        "source_kind": "run",
        "source_probe": {"baseline_policy": "concise-reason", "candidate_policy": "step-calc"},
        "declared_source_file": "results/runs/20260908-235617.json",
        "chal_policy": "step-calc",
        "inc_policy": "concise-reason",
        "declared_null_source": False,
        "blind": False,
        "family": "NONBLIND_SELECTION",
        "provenance": "selection set, d = 10",
        "dataset": "the loop's own development/selection set, 40 ids gsm8k-01..40",
    },
    {
        "index": 7,
        "source_pool": "nonblind-rectify-vs-concise",
        "source_kind": "run",
        "source_probe": {"baseline_policy": "concise-reason", "candidate_policy": "rectify"},
        "declared_source_file": "results/runs/20260908-235617.json",
        "chal_policy": "rectify",
        "inc_policy": "concise-reason",
        "declared_null_source": False,
        "blind": False,
        "family": "NONBLIND_SELECTION",
        "provenance": "selection set, d = 8",
        "dataset": "the loop's own development/selection set, 40 ids gsm8k-01..40",
    },
    {
        "index": 8,
        "source_pool": "nonblind-reflect-vs-stepcalc",
        "source_kind": "pilot",
        "source_probe": {"oracle": "train-only"},
        "declared_source_file": "results/rounds/round3/pilot-train40.json",
        "chal_policy": "reflect-retry",
        "inc_policy": "step-calc",
        "declared_null_source": False,
        "blind": False,
        "family": "NONBLIND_SELECTION",
        "provenance": "selection set (round-3 train-40 pilot), d = 4",
        "dataset": "the loop's own development/selection set, 40 ids gsm8k-01..40",
    },
    # -------------------------------------------------- index 9: fix round 3 (exhaustiveness)
    #
    # The selection-set run of 2026-09-08 carries a THIRD complete candidate arm that the earlier
    # roster silently omitted.  It is status-equivalent to the ``rectify`` arm of index 7 (same
    # run, same baseline, same n / d), so excluding it while asserting exhaustiveness was wrong.
    # Appended at the END so no earlier child seed moves; like 4-8 it is *not* a null source.
    {
        "index": 9,
        "source_pool": "nonblind-roundingaware-vs-concise",
        "source_kind": "run",
        "source_probe": {"baseline_policy": "concise-reason", "candidate_policy": "rounding-aware"},
        "declared_source_file": "results/runs/20260908-235617.json",
        "chal_policy": "rounding-aware",
        "inc_policy": "concise-reason",
        "declared_null_source": False,
        "blind": False,
        "family": "NONBLIND_SELECTION",
        "provenance": "selection set, d = 10",
        "dataset": "the loop's own development/selection set, 40 ids gsm8k-01..40",
    },
)

# The pinned figures of fix round 3's added arm, re-derived from the run artefact by
# ``tests/test_build_pools.py::test_roundingaware_pool_counts_and_exact_mcnemar_are_pinned``
# (n, b, c, d, gain, exact two-sided McNemar p).  They are recorded here only as the *disclosure*
# of what index 9 is; the pools themselves are never built from these numbers.
ROUNDINGAWARE_PINNED = {"n": 40, "b": 8, "c": 2, "d": 10, "gain": 0.150, "mcnemar_p": 0.109375}

ROSTER_BY_INDEX = {entry["index"]: entry for entry in ROSTER}

DECLARED_NULL_SOURCES = tuple(r["index"] for r in ROSTER if r["declared_null_source"])
NOT_NULL_SOURCES = tuple(r["index"] for r in ROSTER if not r["declared_null_source"])
BLIND_SOURCE_INDICES = tuple(r["index"] for r in ROSTER if r["blind"])

POSITIVE_SOURCE_INDEX = 0      # §1 rule 5 / §3: the POSITIVE family has exactly one pool

# Every source artefact is classified before its pool may carry a ``blind`` flag: the round-4
# artefacts are the *blind* held-out sets (ROUND4-TRACKA-RESULT.md: "该盲集";
# ROUND4-TRACKC-RESULT.md: "n=200 合并盲集"), while the runs and the round-3 train-40 pilot are the
# loop's own *selection* sets (non-blind).  Null pools inherit their source pool's label
# (a null pool uses its source pool's own questions).
BLIND_POLICY = "inherited_from_source"
ITEM_ORDER_POLICY = "qid-ascending (equals the committed details key order of the source artefact)"

# ------------------------------------------ byte-stability anchor for roster indices 0-3
#
# The pre-correction artefacts of this repository are pinned here so the correction round can
# *prove* that adding indices 4-9 changed nothing for indices 0-3.  The hashes are over the
# exact one-pool-per-line serialization used by ``write_pools_json()``, so they are byte-level
# claims and not merely structural ones.  ``pools_meta()`` recomputes them from the pools it is
# given and refuses to call the artefact correct if they moved; the test suite additionally
# recomputes them from the committed pre-correction artefact at its git commit.
PRE_CORRECTION_0_3 = {
    "commit": "be2c5873e6bfed2ffd70944b5534425de671a443",
    "artefact": "results/rounds/round5/pools.json",
    "artefact_sha256": "8912d8a385a7f5b43ff7ea4b6dbe02dd3c3d1986f0b7c0fd66fbce48c5243547",
    "schema_version": 1,
    "n_observed": 4,
    "n_null": 800,
    "observed_block_sha256": "749ca18196023fecf52a8812845a5cb4b061fb293b376224cd46045ef5c555b5",
    "null_block_sha256": "722a4ed15aeb528fdd89939ed315d2fcccc98af09048bd7d770c4361ce1a9acf",
    "basis": ("computed in the correction round from `git show "
              "be2c5873e6bfed2ffd70944b5534425de671a443:results/rounds/round5/pools.json`, whose own "
              "sha256 is the artefact_sha256 field; the two block hashes cover the 4 observed "
              "pools (roster indices 0-3) and the 800 null pools of those four sources, each "
              "serialized exactly as write_pools_json() does"),
}


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


# ------------------------------------------------------------------- source classification

def classify_source_path(rel_path: str) -> str:
    """Classify a pool source by its *declared path* -- never by a flag the caller supplies.

    The round-4 merged artefacts are blind held-out sets; ``results/runs/*.json`` and the round-3
    ``pilot-train40.json`` are the loop's own selection sets (non-blind).  An unknown path is an
    error: a source must be classified before its pool may carry a ``blind`` flag.
    """
    rel = rel_path.replace("\\", "/")
    name = rel.rsplit("/", 1)[-1]
    if rel.startswith("results/rounds/round4/") and name in (
            "trackA-merged.json", "trackC-qwen2-7b-heldout40.json"):
        return BLIND_SOURCE_CLASS
    if rel.startswith("results/runs/") and name.endswith(".json"):
        return NONBLIND_SOURCE_CLASS
    if rel == "results/rounds/round3/pilot-train40.json":
        return NONBLIND_SOURCE_CLASS
    raise ValueError(
        f"unclassified pool source {rel_path!r}: every pool source must be classifiable as a "
        f"blind held-out set or as a selection-set (non-blind) run before a pool may be labelled")


def blind_for_source_path(rel_path: str) -> bool:
    return _BLIND_BY_SOURCE_CLASS[classify_source_path(rel_path)]


# ------------------------------------------------------------ observed pool construction

def _run_docs():
    """All committed run artefacts, in path order (used to locate a run by its policies)."""
    return [(p, json.loads(p.read_text(encoding="utf-8"))) for p in sorted(RUNS.glob("*.json"))]


def _single_policy(outcomes, where: str) -> str:
    policies = {o.get("details", {}).get("policy") for o in outcomes}
    if len(policies) != 1 or None in policies:
        raise ValueError(f"{where}: expected exactly one recorded policy, got {policies!r}")
    return policies.pop()


def _run_policies(doc: dict):
    """``(baseline_policy, {candidate_policy: candidate_entry})`` for a run artefact."""
    baseline = _single_policy(doc["baseline"]["outcomes"], f"run {doc.get('run_id')!r} baseline")
    cands = {}
    for cand in doc["candidates"]:
        policy = (cand.get("candidate") or {}).get("answer_policy") or \
            _single_policy(cand["evaluation"]["outcomes"], f"run {doc.get('run_id')!r} candidate")
        if policy in cands:
            raise ValueError(f"run {doc.get('run_id')!r}: duplicate candidate policy {policy!r}")
        cands[policy] = cand
    return baseline, cands


def _locate_run_source(baseline_policy: str, candidate_policy: str):
    """Locate the run artefact by its (baseline policy, candidate policy) -- never by filename."""
    hits = []
    for path, doc in _run_docs():
        baseline, cands = _run_policies(doc)
        if baseline == baseline_policy and candidate_policy in cands:
            hits.append((path, doc, cands[candidate_policy]))
    if len(hits) != 1:
        raise ValueError(
            f"expected exactly one run artefact with baseline policy {baseline_policy!r} and a "
            f"candidate {candidate_policy!r}, found {[str(p) for p, _, _ in hits]}")
    return hits[0]


def _pilot_policy_key(policy: str) -> str:
    return policy.replace("-", "_")


# The pilot's ``paired`` block does NOT name its only-pass counts by the policy key used for the
# per-id ``details``: it uses a shorter stem (``reflect_retry`` -> ``reflect``, ``step_calc`` ->
# ``step``), so the paired lookup cannot simply reuse ``_pilot_policy_key``.  The mapping is
# declared explicitly, and every lookup must HIT: fix round 4 found that reading
# ``paired[f"{key}_better"]`` for a key that is not there yielded ``None``, so index 8's
# ``(better, worse)`` counts were never checked while the check looked present.
_PILOT_PAIRED_STEM = {"reflect_retry": "reflect", "step_calc": "step"}


def _pilot_paired_key(policy_key: str, where: str) -> str:
    """The ``paired`` block key that records this policy's only-pass count (loud on unknown)."""
    stem = _PILOT_PAIRED_STEM.get(policy_key)
    if stem is None:
        raise ValueError(
            f"{where}: pilot policy {policy_key!r} has no paired-count stem; declare it in "
            f"_PILOT_PAIRED_STEM (declared: {sorted(_PILOT_PAIRED_STEM)})")
    return f"{stem}_better"


def _pilot_paired_better(paired: dict, policy_key: str, where: str) -> int:
    """The pilot's recorded count of items this policy passes and the other policy fails.

    Fails loudly when the policy has no declared stem or the key is absent from the pilot's
    ``paired`` block: a renamed key must break the cross-check, never degrade it to ``None`` (a
    silent no-op check is worse than no check -- it is reported as verification while verifying
    nothing).
    """
    key = _pilot_paired_key(policy_key, where)
    if key not in paired:
        raise ValueError(
            f"{where}: the pilot's paired block has no {key!r} for policy {policy_key!r}; present "
            f"keys: {sorted(paired)}.  A missing paired key must fail here rather than degrade to "
            "None, which would leave the (better, worse) counts silently unchecked")
    value = paired[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{where}: pilot paired[{key!r}] = {value!r} is not an integer count")
    return value


def _pilot_policies(doc: dict):
    out = []
    for key, value in doc.items():
        if isinstance(value, dict) and isinstance(value.get("details"), list) and value["details"] \
                and isinstance(value["details"][0], dict) and "id" in value["details"][0]:
            out.append((key, value))
    return out


def _locate_pilot_source(oracle: str):
    """Locate the round-3 pilot artefact by its ``oracle`` field -- never by filename."""
    hits = []
    for path in sorted(ROUND3.glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(doc, dict) and doc.get("oracle") == oracle and _pilot_policies(doc):
            hits.append((path, doc))
    if len(hits) != 1:
        raise ValueError(
            f"expected exactly one round-3 artefact with oracle {oracle!r} and per-id detail, "
            f"found {[str(p) for p, _ in hits]}")
    return hits[0]


def _ordered_qids(qids, where: str):
    if len(set(qids)) != len(qids):
        raise ValueError(f"{where}: duplicate question ids in the committed record")
    if list(qids) != sorted(qids):
        raise ValueError(
            f"{where}: committed key order is not qid-ascending; the frozen item order of §1 "
            "must be re-declared explicitly instead of assumed")
    return list(qids)


def _source_round4(entry: dict) -> dict:
    path = ROUND4 / entry["source_file"]
    data = json.loads(path.read_text(encoding="utf-8"))
    details = data["details"]
    policies = data["meta"]["policies"]
    chal, inc = entry["chal_policy"], entry["inc_policy"]
    for policy in (chal, inc):
        if policy not in policies:
            raise ValueError(f"{entry['source_pool']}: policy {policy!r} not in {policies}")

    qids = _ordered_qids(list(details), entry["source_pool"])
    items = [{"qid": qid, "chal": bool(details[qid][chal]["passed"]),
              "inc": bool(details[qid][inc]["passed"])} for qid in qids]

    # Cross-check against the artefact's own pair record (orientation-aware): in this artefact
    # ``better`` counts the second-named policy's only-passes, ``worse`` the first-named's.
    key = f"{chal}_vs_{inc}"
    reversed_key = f"{inc}_vs_{chal}"
    if key in data["pairs"]:
        rec = data["pairs"][key]
    elif reversed_key in data["pairs"]:
        rec = data["pairs"][reversed_key]
    else:
        raise ValueError(f"{entry['source_pool']}: no pair record for {chal} vs {inc}")
    policy_totals = {p: sum(1 for row in details.values() if row[p]["passed"]) for p in policies}
    return {
        "items": items,
        "n": data["meta"]["n"],
        "model": data["meta"].get("model"),
        "source_file": path.relative_to(ROOT).as_posix(),
        "source_class": BLIND_SOURCE_CLASS,
        "aggregates": {"chal": policy_totals[chal], "inc": policy_totals[inc]},
        "policy_totals": policy_totals,
        "n_total": data["meta"]["n"],
        "record": {"better": rec["better"], "worse": rec["worse"], "p": rec["p"],
                   "gain": rec["gain"], "where": f"{entry['source_file']} pairs[{key!r}]",
                   "orientation": "reverse" if key in data["pairs"] else "declared"},
        "extra_meta": {},
    }


def _source_run(entry: dict) -> dict:
    probe = entry["source_probe"]
    path, doc, cand = _locate_run_source(probe["baseline_policy"], probe["candidate_policy"])
    rel = path.relative_to(ROOT).as_posix()
    if rel != entry["declared_source_file"]:
        raise ValueError(
            f"{entry['source_pool']}: located {rel} by policy {probe!r} but the frozen roster "
            f"declares {entry['declared_source_file']!r}; the roster declaration is stale")
    chal, inc = entry["chal_policy"], entry["inc_policy"]
    cand_policy = (cand.get("candidate") or {}).get("answer_policy")
    if cand_policy != chal:
        raise ValueError(f"{entry['source_pool']}: located candidate policy {cand_policy!r} != {chal!r}")

    base_out = doc["baseline"]["outcomes"]
    chal_out = cand["evaluation"]["outcomes"]
    base = {o["task_id"]: bool(o["passed"]) for o in base_out}
    chal_map = {o["task_id"]: bool(o["passed"]) for o in chal_out}
    if set(base) != set(chal_map):
        raise ValueError(f"{entry['source_pool']}: baseline and candidate scored different task ids")
    qids = _ordered_qids(list(base), entry["source_pool"])
    items = [{"qid": q, "chal": chal_map[q], "inc": base[q]} for q in qids]

    # The run artefact records its own aggregates; recompute them and require agreement, so a
    # truncated or hand-edited run file is caught rather than inherited.
    for label, outcomes, totals in (("baseline", base_out, doc["baseline"]),
                                    ("candidate", chal_out, cand["evaluation"])):
        passed = sum(1 for o in outcomes if o["passed"])
        if totals["total"] != len(outcomes) or totals["passed"] != passed:
            raise ValueError(f"{entry['source_pool']}: run {doc['run_id']!r} {label} aggregate "
                             f"({totals['passed']}/{totals['total']}) != recomputed "
                             f"({passed}/{len(outcomes)})")
    decision = doc.get("statistical_decision") if cand["id"] == doc.get("active_id") else None
    record = {"better": None, "worse": None, "p": None, "gain": None,
              "where": f"{rel} (run {doc['run_id']}, candidate {cand['id']})",
              "orientation": "declared"}
    if decision:
        record.update({"better": decision["mcnemar"]["better"], "worse": decision["mcnemar"]["worse"],
                       "p": decision["mcnemar"]["p_value"], "gain": decision["mean_gain"],
                       "where": f"{rel} statistical_decision (run {doc['run_id']}, "
                                f"active candidate {cand['id']})"})
    return {
        "items": items,
        "n": len(items),
        "model": doc.get("model"),
        "source_file": rel,
        "source_class": NONBLIND_SOURCE_CLASS,
        "aggregates": {"chal": sum(1 for v in chal_map.values() if v),
                       "inc": sum(1 for v in base.values() if v)},
        "n_total": len(items),
        "record": record,
        "extra_meta": {"run_id": doc["run_id"], "candidate_id": cand["id"],
                       "candidate_record": cand.get("candidate"),
                       "baseline_policy": probe["baseline_policy"]},
    }


def _source_pilot(entry: dict) -> dict:
    oracle = entry["source_probe"]["oracle"]
    path, doc = _locate_pilot_source(oracle)
    rel = path.relative_to(ROOT).as_posix()
    if rel != entry["declared_source_file"]:
        raise ValueError(
            f"{entry['source_pool']}: located {rel} by oracle {oracle!r} but the frozen roster "
            f"declares {entry['declared_source_file']!r}; the roster declaration is stale")
    chal, inc = entry["chal_policy"], entry["inc_policy"]
    chal_key, inc_key = _pilot_policy_key(chal), _pilot_policy_key(inc)
    policy_map = dict(_pilot_policies(doc))
    for key in (chal_key, inc_key):
        if key not in policy_map:
            raise ValueError(f"{entry['source_pool']}: {key!r} not among the pilot's policies "
                             f"{sorted(policy_map)}")
    chal_rows = {r["id"]: bool(r["passed"]) for r in policy_map[chal_key]["details"]}
    inc_rows = {r["id"]: bool(r["passed"]) for r in policy_map[inc_key]["details"]}
    if set(chal_rows) != set(inc_rows):
        raise ValueError(f"{entry['source_pool']}: the two pilot policies scored different ids")
    qids = _ordered_qids(list(chal_rows), entry["source_pool"])
    items = [{"qid": q, "chal": chal_rows[q], "inc": inc_rows[q]} for q in qids]
    for key, rows in ((chal_key, chal_rows), (inc_key, inc_rows)):
        rec = policy_map[key]
        if rec["total"] != len(rows) or rec["passed"] != sum(1 for v in rows.values() if v):
            raise ValueError(f"{entry['source_pool']}: pilot {key!r} aggregate "
                             f"({rec['passed']}/{rec['total']}) != recomputed")
    paired = doc["paired"]
    rec_where = f"{entry['source_pool']}: {rel} paired"
    chal_paired_key = _pilot_paired_key(chal_key, rec_where)
    inc_paired_key = _pilot_paired_key(inc_key, rec_where)
    return {
        "items": items,
        "n": len(items),
        "model": doc.get("model"),
        "source_file": rel,
        "source_class": NONBLIND_SOURCE_CLASS,
        "aggregates": {"chal": sum(1 for v in chal_rows.values() if v),
                       "inc": sum(1 for v in inc_rows.values() if v)},
        "n_total": len(items),
        "record": {"better": _pilot_paired_better(paired, chal_key, rec_where),
                   "worse": _pilot_paired_better(paired, inc_key, rec_where),
                   "p": paired.get("mcnemar_p_value"),
                   "gain": None,
                   "where": f"{rel} paired ({chal_paired_key} / {inc_paired_key})",
                   "orientation": "declared"},
        "extra_meta": {"oracle": doc["oracle"], "paired_record": paired,
                       "pilot_note": paired.get("note")},
    }


_SOURCE_LOADERS = {"round4": _source_round4, "run": _source_run, "pilot": _source_pilot}


def build_observed_pools() -> list[dict]:
    """Every observed pool of the frozen roster, in roster order (Task 3).

    Indices 0-3 are the blind held-out pools; indices 4-9 are the non-blind selection-set pools
    of the correction round.  Every figure is recomputed from the committed source artefact's
    per-question records; the artefact's own aggregate/pair records are used only as cross-checks,
    so a hand-edited or truncated source file is caught rather than inherited.
    """
    return [_build_observed_pool(entry) for entry in ROSTER]


def build_null_source_pools() -> list[dict]:
    """Only the observed pools that the roster *declares* to be null sources (indices 0-3).

    Rule 4's "not a null source" escape hatch is honoured here and in ``build_pools()``: indices
    4-9 are real observed pools but are never sent to ``permutation_nulls``, so the NULL set of
    this study remains exactly ``K`` nulls per declared source.
    """
    return [_build_observed_pool(ROSTER_BY_INDEX[i]) for i in DECLARED_NULL_SOURCES]


def _build_observed_pool(entry: dict) -> dict:
    src = _SOURCE_LOADERS[entry["source_kind"]](entry)
    items = src["items"]
    n = src["n"]
    if len(items) != n:
        raise ValueError(f"{entry['source_pool']}: {len(items)} items but n = {n}")

    expected_blind = blind_for_source_path(src["source_file"])
    if entry["blind"] is not expected_blind:
        raise ValueError(
            f"{entry['source_pool']}: roster says blind={entry['blind']} but the declared source "
            f"{src['source_file']!r} is a {src['source_class']}; a pool's blind flag must match "
            "its declared source")

    b, c = _items_bc({"items": items})
    d = b + c
    gain = _gain({"items": items})
    total_chal = src["aggregates"]["chal"]
    total_inc = src["aggregates"]["inc"]
    if d == 0 and entry["declared_null_source"]:
        # PREREG §1 rule 4: a pool with no discordant item can never be a NULL source -- there is
        # nothing to relabel, and a silent skip would shrink the FPR denominator.  The *escape
        # hatch* of the same rule is the other half of this condition: a d == 0 pool that the
        # roster explicitly declares NOT a null source is permitted as an observed row (it
        # contributes no nulls, so it cannot move any FPR).  Rejecting it unconditionally would
        # contradict the rule's own wording and would leave the declared escape hatch unusable on
        # the one path that actually builds observed rows.
        raise ValueError(
            f"{entry['source_pool']}: discordant_total == 0 but the roster declares it a null "
            "source; a pool with d == 0 may appear only as an observed pool explicitly declared "
            "'not a null source' (PREREG §1 rule 4)")
    if (b - c) != (total_chal - total_inc):
        raise ValueError(f"{entry['source_pool']}: (b - c) != totals[chal] - totals[inc]")
    if abs(gain - (total_chal - total_inc) / n) > 1e-12:
        raise ValueError(f"{entry['source_pool']}: gain != (total_chal - total_inc)/n")
    if src["n_total"] != n:
        raise ValueError(f"{entry['source_pool']}: source declares n = {src['n_total']} but "
                         f"{n} items were read")

    p_exact = mcnemar_two_sided(b, c)
    rec = src["record"]
    if rec["orientation"] == "declared":
        want_better, want_worse, want_gain = b, c, gain
    else:                                   # the source stores the reverse orientation
        want_better, want_worse, want_gain = c, b, -gain
    for field, want in (("better", want_better), ("worse", want_worse), ("gain", want_gain)):
        got = rec[field]
        if got is None:
            continue
        if abs(got - want) > 1e-12:
            raise ValueError(f"{entry['source_pool']}: source record {field}={got!r} but the "
                             f"orientation arithmetic gives {want!r} ({rec['where']})")
    if rec["p"] is not None and abs(rec["p"] - p_exact) > 1e-12:
        raise ValueError(f"{entry['source_pool']}: source record p={rec['p']!r} != {p_exact} "
                         f"({rec['where']})")

    meta = {
        "source_pool": entry["source_pool"],
        "source_pool_index": entry["index"],
        "discordant_total": d,
        "chal_policy": entry["chal_policy"],
        "inc_policy": entry["inc_policy"],
        "seed": child_seed(entry["index"]),
        "seed_basis": "child_seed = SEED + source_pool_index (PREREG §1 rule 2)",
        "family": entry["family"],
        "provenance": entry["provenance"],
        "source_file": src["source_file"],
        "dataset": entry["dataset"],
        "model": src["model"],
        "blind": entry["blind"],
        # The blind wording is kept byte-identical to the pre-correction artefact (indices 0-3 are
        # anchored byte-wise); it is only used when the source really is the round-4 blind class.
        "blind_basis": (
            f"source artefact is a round-4 blind held-out set: {entry['dataset']}"
            if src["source_class"] == BLIND_SOURCE_CLASS else
            f"declared source {src['source_file']!r} is a {src['source_class']}, not a held-out "
            f"set: {entry['dataset']}"),
        "blind_policy": BLIND_POLICY,
        "item_order": ITEM_ORDER_POLICY,
        "discordant_checks": {"b": b, "c": c, "d": d, "gain": gain, "mcnemar_p": p_exact},
        "declared_null_source": entry["declared_null_source"],
    }
    meta.update(src["extra_meta"])
    return {
        "name": entry["source_pool"],
        "n": n,
        "blind": entry["blind"],
        "truth": "observed",
        "chal_policy": entry["chal_policy"],
        "inc_policy": entry["inc_policy"],
        "items": items,
        "meta": meta,
        **_structural_keys(),
    }


# ------------------------------------------------------------------------- blind-label guard

def check_blind_labels(pools: list[dict]) -> None:
    """Fail unless every pool's ``blind`` flag matches the source it declares.

    * an observed pool must be ``blind == (its declared source is a blind held-out set)``;
    * a null pool must inherit its source observed pool's label (``blind_policy``), because a null
      pool is built from that source pool's own questions.

    This is the correction round's replacement for the earlier guard, which asserted a corpus-wide
    "no non-blind pool" fact that was false.  A mislabelled pool -- in either direction -- fails
    here instead of silently making R4 look evaluable or unevaluable.
    """
    by_index = {}
    for pool in pools:
        if pool["truth"] == "observed":
            index = pool["meta"]["source_pool_index"]
            if index in by_index:
                raise ValueError(f"duplicate observed pool for roster index {index}")
            by_index[index] = pool
            want = blind_for_source_path(pool["meta"]["source_file"])
            if pool["blind"] is not want or pool["meta"]["blind"] is not want:
                raise ValueError(
                    f"pool {pool['name']!r}: blind={pool['blind']!r} (meta {pool['meta']['blind']!r}) "
                    f"but its declared source {pool['meta']['source_file']!r} is a "
                    f"{classify_source_path(pool['meta']['source_file'])} -> blind must be {want!r}")
    for entry in ROSTER:
        if entry["index"] not in by_index:
            raise ValueError(f"the artefact is missing the observed pool for roster index "
                             f"{entry['index']} ({entry['source_pool']!r})")
    for pool in pools:
        if pool["truth"] != "null":
            continue
        index = pool["meta"]["source_pool_index"]
        source = by_index.get(index)
        if source is None:
            raise ValueError(f"null pool {pool['name']!r} has no source observed pool (index {index})")
        if pool["blind"] is not source["blind"] or pool["meta"]["blind"] is not source["blind"]:
            raise ValueError(f"null pool {pool['name']!r}: blind={pool['blind']!r} does not inherit "
                             f"its source pool's blind={source['blind']!r}")
        if pool["meta"].get("blind_policy") != BLIND_POLICY:
            raise ValueError(f"null pool {pool['name']!r}: blind_policy must be {BLIND_POLICY!r}")


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

def _resolve_stream_seed(pool: dict, k_units: int, seed: int | None) -> int:
    """Resolve the pinned child seed of a candidate stream, or refuse.

    The pinned path is ``seed is None``: the seed is derived from the pool's roster index and the
    stream is then the *frozen* stream of PREREG §1 rule 5, which has exactly ``K`` null blocks.
    A different ``k_units`` on that path would silently re-shape every candidate draw, so it is
    refused rather than accepted (fail closed).  An explicit ``seed`` is a deliberate off-protocol
    study; the caller then owns the budget.  A pool without a roster index can never be resolved
    implicitly -- the earlier silent fallback to index 0 is exactly the fail-open bug this closes.
    """
    if seed is not None:
        return seed
    index = pool.get("meta", {}).get("source_pool_index")
    if index is None:
        raise ValueError(
            f"pool {pool.get('name')!r} carries no meta.source_pool_index, so the pinned child seed "
            "cannot be derived; pass an explicit seed instead of relying on a fallback")
    if k_units != K:
        raise ValueError(
            f"the pinned candidate stream of a roster pool has exactly K={K} null blocks "
            f"(PREREG §1 rule 5); k_units={k_units!r} would silently change every candidate draw. "
            "Pass an explicit seed to study another budget off-protocol.")
    return child_seed(index)


def _stream_shape_ok(k_units: int, k_prefix: int) -> None:
    if not 0 < k_prefix <= K_CANDIDATES or k_units < 0:
        raise ValueError(f"bad stream shape: k_prefix={k_prefix!r} k_units={k_units!r}")


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

    A ``d == 0`` pool is refused here too (§1 rule 4): this is a relabelling stream, so a pool
    with no discordant item has nothing to relabel and must not be quietly streamed.
    """
    _stream_shape_ok(k_units, k_prefix)
    d = discordant_total_from_items(pool["items"])
    if d == 0:
        raise ValueError(
            f"source pool {pool.get('name')!r} has discordant_total == 0: the NULL-family "
            "candidate stream is a relabelling stream and cannot be drawn from a pool with no "
            "discordant item (PREREG §1 rule 4); such a pool may appear only as an observed pool "
            "explicitly declared 'not a null source'")
    seed = _resolve_stream_seed(pool, k_units, seed)
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
    _stream_shape_ok(k_units, k_prefix)
    d = discordant_total_from_items(pool["items"])
    if d == 0:
        raise ValueError("a POSITIVE-family bootstrap candidate needs a pool with a real effect")
    seed = _resolve_stream_seed(pool, k_units, seed)
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

    Observed pools come first in roster order (indices 0-8), then, grouped by source pool, the
    ``K`` nulls of **each declared null source** -- rule 4's escape hatch is honoured here, so an
    observed pool that the roster declares *not a null source* (indices 4-9, the non-blind
    selection-set pools) contributes no nulls and cannot move the FPR denominator.  A source pool
    with ``d == 0`` raises ``ValueError`` through ``permutation_nulls``.  R7's candidate pools are
    deliberately NOT part of this list: they are candidates, not null pools, and must never be
    counted in the NULL set (PREREG §1 / §5.2).  Generate them with ``iter_null_candidate_blocks``
    / ``positive_candidate_blocks``.
    """
    observed = build_observed_pools()
    pools = list(observed)
    for pool in observed:
        if not pool["meta"]["declared_null_source"]:
            continue                         # rule 4: declared "not a null source"
        index = pool["meta"]["source_pool_index"]
        pools.extend(permutation_nulls(pool, K, child_seed(index)))
    return pools


# ------------------------------------------------------------- artefact description + I/O

def _serialize_pool(pool: dict) -> str:
    """The exact per-pool serialization used by ``write_pools_json()`` (byte-level claims)."""
    return json.dumps(pool, ensure_ascii=False, separators=(",", ":"))


def _block_sha256(pools) -> str:
    body = "\n".join(_serialize_pool(p) for p in pools)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def byte_stability_0_3(pools: list[dict]) -> dict:
    """Recompute the pre-correction blocks of the blind roster (indices 0-3) from the pools.

    Deliberately *computed*, never hardcoded: if any pool of indices 0-3 changes by a single byte
    -- or disappears -- the recomputation stops matching ``PRE_CORRECTION_0_3`` and the artefact
    is refused instead of quietly carrying the claim.
    """
    obs = [p for p in pools if p["truth"] == "observed"
           and p["meta"]["source_pool_index"] in BLIND_SOURCE_INDICES]
    nulls = [p for p in pools if p["truth"] == "null"
             and p["meta"]["source_pool_index"] in BLIND_SOURCE_INDICES]
    computed = {
        "n_observed": len(obs),
        "n_null": len(nulls),
        "observed_block_sha256": _block_sha256(obs),
        "null_block_sha256": _block_sha256(nulls),
    }
    expected = {k: PRE_CORRECTION_0_3[k] for k in
                ("n_observed", "n_null", "observed_block_sha256", "null_block_sha256")}
    return {
        "expected": expected,
        "expected_basis": PRE_CORRECTION_0_3,
        "observed": computed,
        "identical": computed == expected,
    }


def _r4_status(n_nonblind: int) -> str:
    """The R4 descriptor, derived from the pools -- it describes only what it computes."""
    if n_nonblind == 0:
        return "not evaluated (no non-blind pool in this artefact)"
    return f"evaluated ({n_nonblind} non-blind selection-set pool(s) in this artefact)"


def _r4_note(pools: list[dict]) -> str:
    """A sentence about R4 that is recomputed from the pools and therefore cannot go stale."""
    obs_nonblind = [p for p in pools if p["truth"] == "observed" and p["blind"] is not True]
    n_blind = sum(1 for p in pools if p["blind"] is True)
    if not obs_nonblind:
        return ("This artefact carries no non-blind (selection-set) observed pool, so R4 cannot be "
                "evaluated from it and the blindness contrast (R1 vs R4) is unmeasured here. No "
                "non-blind pool was invented.")
    names = ", ".join(f"{p['name']} (roster index {p['meta']['source_pool_index']})"
                      for p in obs_nonblind)
    return (f"R4 (non-blind) IS evaluated: this artefact carries {len(obs_nonblind)} non-blind "
            f"selection-set observed pool(s) with per-question detail -- {names}. They come from "
            "the loop's own selection-set runs, which is exactly what 'non-blind' means; no "
            f"synthetic pool was needed and none was used. The other {n_blind} pools are blind "
            "held-out pools (their permutation nulls included), so the NULL set used for FPR is "
            "unchanged.")


DESCRIPTION_KEYS = (
    "schema_version", "SEED", "K", "K_CANDIDATES", "blind_policy", "item_order",
    "declared_null_sources", "not_null_sources",
    "n_pools", "n_observed", "n_null", "n_blind_pools", "n_nonblind_pools",
    "all_artefact_pools_blind", "no_nonblind_pool_in_artefact", "r4_evaluable", "r4_status",
    "r4_note", "byte_stability_0_3",
)


def pools_meta(pools: list[dict]) -> dict:
    """The artefact-level description of ``pools.json``, computed from the pools themselves.

    Every field here describes **only what was actually counted in this artefact** (the earlier
    ``all_pools_blind`` / ``no_nonblind_pool_exists`` names asserted a corpus-wide fact and were
    renamed accordingly), and ``r4_status`` / ``r4_note`` are derived from the pools rather than
    written as prose, so the description cannot drift away from the rows it describes.
    ``load_pools_json()`` recomputes this dict and refuses any artefact whose stored description
    disagrees.
    """
    n_nonblind = sum(1 for p in pools if p["blind"] is not True)
    n_blind = len(pools) - n_nonblind
    return {
        "schema_version": 2,
        "SEED": SEED,
        "K": K,
        "K_CANDIDATES": K_CANDIDATES,
        "blind_policy": BLIND_POLICY,
        "item_order": ITEM_ORDER_POLICY,
        "declared_null_sources": [ROSTER_BY_INDEX[i]["source_pool"] for i in DECLARED_NULL_SOURCES],
        "not_null_sources": [ROSTER_BY_INDEX[i]["source_pool"] for i in NOT_NULL_SOURCES],
        "n_pools": len(pools),
        "n_observed": sum(1 for p in pools if p["truth"] == "observed"),
        "n_null": sum(1 for p in pools if p["truth"] == "null"),
        "n_blind_pools": n_blind,
        "n_nonblind_pools": n_nonblind,
        "all_artefact_pools_blind": n_nonblind == 0,
        "no_nonblind_pool_in_artefact": n_nonblind == 0,
        "r4_evaluable": n_nonblind > 0,
        "r4_status": _r4_status(n_nonblind),
        "r4_note": _r4_note(pools),
        "byte_stability_0_3": byte_stability_0_3(pools),
    }


def write_pools_json(path: Path | None = None) -> Path:
    """Write ``pools.json`` as ``{"meta": ..., "pools": [...]}``, one pool per line.

    The artefact is an object rather than a bare array so that the artefact-level description
    travels **inside the evidence artefact** and cannot be lost by copying the pools.  Keep the
    pool lines one-per-line: the file stays diffable and greppable.
    """
    pools = build_pools()
    out = Path(path) if path is not None else ROUND5 / "pools.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    body = ",\n".join(_serialize_pool(p) for p in pools)
    meta = json.dumps(pools_meta(pools), ensure_ascii=False, indent=1, sort_keys=True)
    meta = " " + meta.replace("\n", "\n ")       # keep it inside the object's 1-space indent
    out.write_text("{\n \"meta\": " + meta.lstrip() + ",\n \"pools\": [\n" + body + "\n ]\n}\n",
                   encoding="utf-8")
    return out


def load_pools_json(path: Path | None = None) -> list[dict]:
    """Load the pool list from the committed ``pools.json`` artefact, verifying its description.

    The artefact must be the ``{"meta": ..., "pools": [...]}`` object written by
    ``write_pools_json()`` (a bare JSON array is **rejected**: it would drop the description), and
    every description key must be exactly what the pools imply -- recomputed here via
    ``pools_meta()``.  In addition each pool's ``blind`` flag must match its declared source
    (``check_blind_labels``), and the pre-correction blocks of roster indices 0-3 must still be
    byte-identical to the anchored hashes.  The loader therefore fails both when the artefact
    misdescribes reality and when a pool is mislabelled -- it never refuses a *true* description.
    """
    src = Path(path) if path is not None else ROUND5 / "pools.json"
    doc = json.loads(src.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or "meta" not in doc or "pools" not in doc:
        raise ValueError(
            f"{src}: pools.json must be an object with 'meta' and 'pools' keys (the description "
            "travels with the pools); a bare JSON array is rejected")
    meta, pools = doc["meta"], doc["pools"]
    if not isinstance(pools, list) or not pools:
        raise ValueError(f"{src}: 'pools' must be a non-empty list")
    computed = pools_meta(pools)
    for key in DESCRIPTION_KEYS:
        got, want = meta.get(key), computed[key]
        if got != want:
            raise ValueError(
                f"{src}: meta[{key!r}] = {got!r} but the pools imply {want!r}: the artefact's "
                "description must not misdescribe the pools it carries")
    if not computed["byte_stability_0_3"]["identical"]:
        raise ValueError(
            f"{src}: the pools of roster indices 0-3 are no longer byte-identical to the "
            f"pre-correction artefact {PRE_CORRECTION_0_3['artefact']!r} at "
            f"{PRE_CORRECTION_0_3['commit']} (rerun the correction-round stability check before "
            "re-anchoring deliberately)")
    check_blind_labels(pools)
    return pools


def main() -> int:
    pools = build_pools()
    path = write_pools_json()
    observed = [p for p in pools if p["truth"] == "observed"]
    nulls = [p for p in pools if p["truth"] == "null"]
    print(f"SEED={SEED} K={K} K_CANDIDATES={K_CANDIDATES} "
          f"declared_null_sources={list(DECLARED_NULL_SOURCES)} "
          f"not_null_sources={list(NOT_NULL_SOURCES)}")
    print(f"observed={len(observed)} nulls={len(nulls)} total={len(pools)} "
          f"-> {path.relative_to(ROOT)} ({path.stat().st_size} bytes)")
    print("observed roster (index, source_pool, n, d, b, c, gain, blind, chal->inc):")
    for p in observed:
        b, c = _items_bc(p)
        print(f"  {p['meta']['source_pool_index']} {p['name']:32s} n={p['n']:4d} "
              f"d={p['meta']['discordant_total']:4d} b={b:4d} c={c:4d} "
              f"gain={_gain(p):+.4f} blind={p['blind']} "
              f"({p['chal_policy']} vs {p['inc_policy']})")
    print("nulls per source pool: " + (", ".join(
        f"{ROSTER_BY_INDEX[i]['source_pool']}="
        f"{sum(1 for p in nulls if p['meta']['source_pool_index'] == i)}"
        for i in DECLARED_NULL_SOURCES) or "(none)"))
    assert all(p[key] is True for p in pools for key in GATE_KEYS)
    # Correction round: the guard now checks that every pool's blind flag matches the source it
    # declares (blind held-out -> True, selection set -> False).  It no longer asserts a
    # corpus-wide "no non-blind pool" fact: that fact was false, and R4 IS evaluable.
    check_blind_labels(pools)
    meta = pools_meta(pools)
    assert meta["byte_stability_0_3"]["identical"], (
        "roster indices 0-3 moved: the correction round must not change the blind pools")
    assert meta["n_nonblind_pools"] == 6, (
        "the six non-blind selection-set pools of roster indices 4-9 must be present")
    # Fix round 3: the added index-9 arm is pinned to the figures re-derived from its run report,
    # so the artefact cannot be rebuilt around a different arm under the same roster index.
    added = next(p for p in observed if p["meta"]["source_pool_index"] == 9)
    added_b, added_c = _items_bc(added)
    added_p = added["meta"]["discordant_checks"]["mcnemar_p"]
    assert (added["n"], added_b, added_c, added["meta"]["discordant_total"]) == (
        ROUNDINGAWARE_PINNED["n"], ROUNDINGAWARE_PINNED["b"], ROUNDINGAWARE_PINNED["c"],
        ROUNDINGAWARE_PINNED["d"]), f"roster index 9 counts != {ROUNDINGAWARE_PINNED}: {added['name']}"
    assert abs(_gain(added) - ROUNDINGAWARE_PINNED["gain"]) < 1e-12 and \
        abs(added_p - ROUNDINGAWARE_PINNED["mcnemar_p"]) < 1e-12, (
        f"roster index 9 gain/p != {ROUNDINGAWARE_PINNED}: got gain={_gain(added)!r} p={added_p!r}")
    print(f"roster index 9 pinned: n={added['n']} b={added_b} c={added_c} "
          f"d={added['meta']['discordant_total']} gain={_gain(added):+.4f} p={added_p:.6f}")
    print(f"blind=[{meta['n_blind_pools']}] nonblind=[{meta['n_nonblind_pools']}] "
          f"r4_status={meta['r4_status']!r}")
    print(f"indices 0-3 byte-stability: {meta['byte_stability_0_3']['identical']} "
          f"(observed_block={meta['byte_stability_0_3']['observed']['observed_block_sha256'][:16]}… "
          f"null_block={meta['byte_stability_0_3']['observed']['null_block_sha256'][:16]}…)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
