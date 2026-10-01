"""Tests for scripts/frontier.py.

The load-bearing test is the last one: recomputing the pairwise statistics from
committed evidence must reproduce the p-values the manuscript already reports. If
the new tool and the paper disagree about the same data, one of them is wrong and
this is where it shows.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from frontier import (  # noqa: E402
    ROOT, analyse, frontier, mcnemar_exact, paired_boot_diff, wilson,
)

EVIDENCE = os.path.join(ROOT, "results/rounds/round4/trackA-merged.json")


# ---- statistics ---------------------------------------------------------------
def test_wilson_interval_brackets_the_point_estimate():
    p, lo, hi = wilson(186, 200)
    assert lo < p < hi
    assert 0.0 <= lo and hi <= 1.0


def test_wilson_degenerate_cases():
    assert wilson(0, 0)[0] == 0.0
    p, lo, hi = wilson(40, 40)
    assert p == 1.0 and hi == 1.0 and lo > 0.8


def test_mcnemar_exact_known_values():
    assert mcnemar_exact(0, 0) == 1.0
    assert round(mcnemar_exact(9, 7), 4) == 0.8036    # committed step-calc/cot-zero
    assert round(mcnemar_exact(9, 14), 4) == 0.4049   # committed step-calc/few-shot
    assert mcnemar_exact(5, 0) < 0.2
    assert mcnemar_exact(3, 3) == 1.0


def test_mcnemar_is_symmetric():
    assert mcnemar_exact(9, 7) == mcnemar_exact(7, 9)
    assert mcnemar_exact(2, 11) == mcnemar_exact(11, 2)


def test_paired_boot_diff_is_deterministic_under_a_fixed_seed():
    import random
    rng = random.Random(11)
    a = [rng.gauss(5, 1) for _ in range(60)]
    b = [x - 1.5 for x in a]                     # paired, so a is uniformly larger
    d1, lo1, hi1 = paired_boot_diff(a, b, n_boot=600)
    d2, lo2, hi2 = paired_boot_diff(a, b, n_boot=600)
    assert (d1, lo1, hi1) == (d2, lo2, hi2)
    assert lo1 <= d1 <= hi1
    assert lo1 > 0, "a constant per-item offset must give a decisive positive interval"


def test_paired_boot_detects_a_real_difference_and_not_noise():
    import random
    rng = random.Random(7)
    base = [rng.gauss(5, 1) for _ in range(80)]
    _, lo, hi = paired_boot_diff(base, [rng.gauss(5, 1) for _ in range(80)], n_boot=800)
    assert lo < 0 < hi, "independent noise must not give a decisive interval"
    # paired offset, not a shift of means: this is the shape real per-item data has
    d, lo, hi = paired_boot_diff([x + 3.0 for x in base], base, n_boot=800)
    assert lo > 0, "a real paired difference must produce a decisive interval"


# ---- the real evidence --------------------------------------------------------
def test_frontier_drops_a_dominated_policy():
    per = {
        "cheap_bad": {"accuracy": 0.10, "lat_mean": 1.0},
        "mid": {"accuracy": 0.90, "lat_mean": 5.0},
        "costly_good": {"accuracy": 0.93, "lat_mean": 10.0},
        "dominated": {"accuracy": 0.80, "lat_mean": 12.0},
    }
    keep = frontier(per)
    assert "dominated" not in keep
    assert set(keep) == {"cheap_bad", "mid", "costly_good"}


def test_recomputed_pairwise_stats_match_the_committed_manuscript():
    """Cross-check against values already written in paper/RESULTS.md.

    Committed: step-calc vs cot-zero 9:7 p=0.804; step-calc vs few-shot 9:14
    p=0.4049; direct vs cot-zero 159:0.
    """
    data = json.load(open(EVIDENCE, encoding="utf-8"))
    items, pols, per = analyse(data)
    assert len(items) == 200

    # Cross-check against the file's own committed `pairs` block rather than
    # against a remembered ordering.
    #
    # CONVENTION, pinned here because it is not inferable and I got it backwards
    # once while writing this file: in a key "a_vs_b", `better` counts the wins
    # of the SECOND policy (b-only), and `worse` the first (a-only). So
    # "step-calc_vs_cot-zero: better=9" means cot-zero won 9 items outright.
    # Under the opposite reading every pair below transposes.
    assert data["pairs"]["step-calc_vs_cot-zero"]["better"] == 9
    assert data["pairs"]["step-calc_vs_cot-zero"]["worse"] == 7

    for key, rec in data["pairs"].items():
        x, y = key.split("_vs_")
        x_only = sum(1 for i in items
                     if data["details"][i][x]["passed"] and not data["details"][i][y]["passed"])
        y_only = sum(1 for i in items
                     if data["details"][i][y]["passed"] and not data["details"][i][x]["passed"])
        assert (y_only, x_only) == (rec["better"], rec["worse"]), (
            f"{key}: recomputed (b={y_only},a={x_only}) vs committed "
            f"(better={rec['better']},worse={rec['worse']})")
        assert round(mcnemar_exact(x_only, y_only), 4) == round(rec["p"], 4), key

    p = data["pairs"]["step-calc_vs_cot-zero"]
    assert round(mcnemar_exact(p["worse"], p["better"]), 4) == 0.8036


def test_step_calc_is_significantly_cheaper_than_cot_zero():
    """The finding: an accuracy null that is a real cost difference."""
    data = json.load(open(EVIDENCE, encoding="utf-8"))
    items, pols, per = analyse(data)
    d, lo, hi = paired_boot_diff(per["step-calc"]["_lat"], per["cot-zero"]["_lat"], n_boot=2000)
    assert hi < 0, f"CI should sit entirely below zero, got [{lo:.3f},{hi:.3f}]"
    assert round(mcnemar_exact(9, 7), 2) >= 0.05, "accuracy really is indistinguishable"
    saving = -d / per["cot-zero"]["lat_mean"]
    assert 0.10 < saving < 0.25, f"saving is {saving:.1%}, expected 10-25%"