"""token_budget_probe 判定测试：把 96→256 的 L3 变化机械映射成三态判决。

为什么要单独一台尺子（不是装饰）：
  PREREG-256 跑前锁死了两条可证伪假设与三态判决（TOKEN_LIMIT_DOMINANT /
  MIXED / NEITHER）。本尺子把「读两个 error_taxonomy 产物」变成确定性判定，
  避免看完数据再口头解释阈值——那是拿结果调判据。

两条方向都要测：
  - 正向：截断塌缩+退化不塌缩 → TOKEN_LIMIT_DOMINANT
  - 变异反证：把判据反过来（退化塌缩）会翻成别的态，证明阈值真的在判东西，不是恒定输出。
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import token_budget_probe as tb  # noqa: E402


def _tax(l1, l2, trunc, degen, computed=0, other=0, wrong=0, correct=0):
    """构造一个 error_taxonomy.effective_measurement 形状的最小 dict。"""
    return {
        "L1_manifest": l1, "L2_scorable": l2,
        "L3_heuristic_excluded": l1 - l2,
        "categories": {
            tb.ANSWER_CORRECT: correct,
            tb.ANSWER_WRONG_TRUEARITH: wrong,
            tb.NOANS_TRUNCATED_MIDSTEP: trunc,
            tb.NOANS_DEGENERATE: degen,
            tb.NOANS_COMPUTED_BUT_UNFORMATTED: computed,
            tb.NOANS_OTHER: other,
        },
    }


def test_token_limit_dominant_when_truncation_and_degeneration_both_relax():
    """PREREG-256.md:37 形式定义：H_token 成立 且 H_greedy 不成立 → DOMINANT。

    语义：截断塌缩（加 token 救回）+ 退化也塌缩（H_greedy 假=退化也被救回）
    → token 上限是两者唯一主因。注意 :37 括号里的自然语言"退化不塌缩"是笔误，
    与同句形式条件相反；判据以形式定义为准（:35「由真假组合机械决定」）。
    """
    b96 = {"sft": _tax(60, 48, 11, 0, computed=1), "dpo": _tax(60, 51, 1, 3, computed=5)}
    # 256：SFT 截断 11→2、L3 12→3（H_token 成立）；DPO 退化 3→1（H_greedy 不成立）
    b256 = {"sft": _tax(60, 57, 2, 0, computed=1), "dpo": _tax(60, 56, 1, 1, computed=2)}
    r = tb.judge(b96, b256)
    assert r["verdict"] == "TOKEN_LIMIT_DOMINANT"
    assert r["h_token"] is True and r["h_greedy"] is False
    assert r["sft_trunc"] == {"from": 11, "to": 2, "threshold": 3}
    assert r["sft_l3"] == {"from": 12, "to": 3, "threshold": 4}


def test_neither_when_truncation_does_not_collapse():
    b96 = {"sft": _tax(60, 48, 11, 0, computed=1), "dpo": _tax(60, 51, 1, 3, computed=5)}
    # 256：SFT 截断 11→10（没塌缩），H_token 不成立 → NEITHER
    b256 = {"sft": _tax(60, 49, 10, 0, computed=1), "dpo": _tax(60, 51, 1, 3, computed=5)}
    r = tb.judge(b96, b256)
    assert r["verdict"] == "NEITHER"
    assert r["h_token"] is False


def test_mixed_when_truncation_relaxes_but_degeneration_persists():
    """PREREG-256.md:38：两条都成立 → MIXED（截断救回、退化没救回=两机制并存）。"""
    b96 = {"sft": _tax(60, 48, 11, 0, computed=1), "dpo": _tax(60, 51, 1, 3, computed=5)}
    # SFT 截断塌缩（H_token 真），DPO 退化 3→3 仍≥2（H_greedy 真）→ MIXED
    b256 = {"sft": _tax(60, 57, 2, 0, computed=1), "dpo": _tax(60, 51, 1, 3, computed=5)}
    r = tb.judge(b96, b256)
    assert r["verdict"] == "MIXED"
    assert r["h_token"] is True and r["h_greedy"] is True


def test_thresholds_are_the_prereg_frozen_values():
    assert tb.SFT_TRUNC_96 == 11
    assert tb.SFT_TRUNC_256_MAX == 3
    assert tb.SFT_L3_96 == 12
    assert tb.SFT_L3_256_MAX == 4
    assert tb.DPO_DEGEN_96 == 3
    assert tb.DPO_DEGEN_256_MIN == 2


def test_mutation_would_turn_red():
    """变异反证：把 SFT 256  L3 门槛从 4 改成 13（同数据成立），判决必须翻转。"""
    b96 = {"sft": _tax(60, 48, 11, 0, computed=1), "dpo": _tax(60, 51, 1, 3, computed=5)}
    # 截断塌缩(trunc 2<=3)但 L3 不塌缩(11>4) → real=NEITHER；放宽 l3 门槛到 13 → MIXED
    b256 = {"sft": _tax(60, 49, 2, 0, computed=1), "dpo": _tax(60, 51, 1, 3, computed=5)}
    real = tb.judge(b96, b256)
    mutated = tb.judge(b96, b256, sft_l3_256_max=13)  # 放宽到不可能失败
    assert real["verdict"] == "NEITHER"
    assert mutated["verdict"] != real["verdict"]


def test_symbol_consistency_recomputed_from_parser_report():
    rep = {"per_parser": {
        "last_int": {"label": "GAIN"},
        "first_answer": {"label": "REGRESSION"},
        "strict_last_line": {"label": "NO_GAIN"},
    }}
    assert tb.symbol_verdict(rep) == "UNSTABLE"
    rep2 = {"per_parser": {k: {"label": "GAIN"} for k in ("last_int", "first_answer")}}
    assert tb.symbol_verdict(rep2) == "STABLE"


def test_missing_round_is_incomplete_not_extrapolated():
    b96 = {"sft": _tax(60, 48, 11, 0, computed=1), "dpo": _tax(60, 51, 1, 3, computed=5)}
    r = tb.judge(b96, None)  # 256 没跑出来
    assert r["verdict"] == "INCOMPLETE"
    assert r["reason"] == "no_256_artifacts"


def test_render_md_carries_honest_boundaries():
    b96 = {"sft": _tax(60, 48, 11, 0, computed=1), "dpo": _tax(60, 51, 1, 3, computed=5)}
    # SFT 截断塌缩 + DPO 退化也被救回(degen 1<2) → DOMINANT
    b256 = {"sft": _tax(60, 57, 2, 0, computed=1), "dpo": _tax(60, 56, 1, 1, computed=2)}
    rep = tb.build_report(b96, b256, symbol_256="UNSTABLE", symbol_96="UNSTABLE")
    md = tb.render_md(rep)
    assert "finish_reason" in md
    assert "启发式" in md
    assert "非能力结论" in md or "存在性" in md
    assert "TOKEN_LIMIT_DOMINANT" in md
