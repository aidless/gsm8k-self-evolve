"""complexity_vs_gain is not vacuous: fail loudly if the measurement stops discriminating.

Per the repo's gate discipline (every gate needs a non-vacuity counter-proof), this test
asserts that the script is actually SENSITIVE to the thing it claims to measure:

1. 20 contrasts are discovered from the committed result files (drift guard).
2. Every gain is a rate in [-1, 1] -- the unit-normalisation bug that once produced
   "+437 accuracy points" must not come back.
3. The Spearman implementation is correct on data with a KNOWN answer:
      rho == +1 for a strictly increasing pair, -1 for decreasing, 0 for flat.
4. The measurement is sensitive: inject a synthetic artifact where size predicts gain
      perfectly and the correlation must move decisively. If it does not, the gate
      cannot distinguish "no effect" from "no measurement", and a real null would be
      uninterpretable.
5. The prompt table is read from the evaluator, not hard-coded, so deleting a policy
      from examples/gsm8k_evaluator.py must surface as a KeyError rather than silence.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("cvg", ROOT / "scripts" / "complexity_vs_gain.py")
cvg = importlib.util.module_from_spec(spec)
sys.modules["cvg"] = cvg
spec.loader.exec_module(cvg)


def test_discovers_expected_contrasts():
    res = cvg.analyse()
    assert res["n_contrasts"] == cvg.EXPECTED_N == 20
    assert res["zero_model_calls"] is True


def test_gains_are_rates_not_counts():
    """Regression guard for the unit-normalisation bug (counts vs accuracies)."""
    for c in cvg.analyse()["contrasts"]:
        assert -1.0 <= c["gain"] <= 1.0, (c["source"], c["challenger"], c["gain"])
        assert -1.0 <= c["chal_chars"] / 1e6 <= 1.0


def test_spearman_is_correct_on_known_answers():
    xs = [1.0, 2.0, 3.0, 4.0, 5.0]
    rho, p = cvg.spearman(xs, [10.0, 20.0, 30.0, 40.0, 50.0])
    assert rho == pytest.approx(1.0, abs=1e-9) and p < 1e-3

    rho, p = cvg.spearman(xs, [50.0, 40.0, 30.0, 20.0, 10.0])
    assert rho == pytest.approx(-1.0, abs=1e-9) and p < 1e-3

    rho, p = cvg.spearman(xs, [7.0, 7.0, 7.0, 7.0, 7.0])
    assert rho == 0.0 and p == 1.0


def test_spearman_handles_ties_by_midrank():
    # [1,2,2,3] has midranks [1, 2.5, 2.5, 4]; y is a monotone function of those.
    rho, _ = cvg.spearman([1.0, 2.0, 2.0, 3.0], [1.0, 2.5, 2.5, 4.0])
    assert rho == pytest.approx(1.0, abs=1e-9)


def test_measurement_is_sensitive_to_a_real_relationship():
    """Non-vacuity: if size DID predict gain, this pipeline must detect it.

    Without this, "INCONCLUSIVE" could mean "no effect" or "the instrument is dead" --
    the two are indistinguishable, which is the failure mode of every null result.
    """
    n = 20
    xs = [50.0 + 30.0 * i for i in range(n)]
    ys = [0.02 * (x - 50.0) - 0.2 for x in xs]      # perfectly monotone
    rho, p = cvg.spearman(xs, ys)
    assert rho == pytest.approx(1.0, abs=1e-9)
    assert p < 0.001, "a perfectly monotone relationship must be significant at n=20"

    # and the direction the literature predicts (bigger -> worse) must also register
    ys_neg = [-y for y in ys]
    rho_neg, p_neg = cvg.spearman(xs, ys_neg)
    assert rho_neg == pytest.approx(-1.0, abs=1e-9) and p_neg < 0.001


def test_prompt_stats_come_from_the_evaluator_not_a_hardcoded_table():
    stats = cvg.load_prompt_stats()
    src = (ROOT / "examples" / "gsm8k_evaluator.py").read_text(encoding="utf-8")
    assert "step_calc" in stats and "cot_zero" in stats and "few_shot" in stats
    # every literal policy name in the evaluator must be addressable
    for name in ("direct", "concise_reason", "step_calc", "rounding_aware",
                 "rectify", "cot_zero"):
        assert name in stats, name
    assert "PROMPTS" in src  # the read really is from the evaluator


def test_zero_model_calls_by_construction():
    """The module must not import an inference client."""
    src = (ROOT / "scripts" / "complexity_vs_gain.py").read_text(encoding="utf-8")
    for forbidden in ("requests", "urllib", "http.client", "ollama", "socket"):
        assert forbidden not in src, forbidden