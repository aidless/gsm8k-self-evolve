"""error_taxonomy 判定测试：把 explicit 口径判出的"错"分成算术错 / 输出失败。

为什么需要这台尺子（不是装饰）：
  ability-B 的 explicit 口径给出 "DPO 真算术错 17 vs SFT 3"，但这个数字把
  "没生成规范 Answer 字段"的题（token 上限截断 / 贪心解码退化）一律算成算术错。
  generations 里没有 finish_reason，截断只能启发式判断——所以本尺子只做分型，
  不宣称客观归因，且所有 NOANS_* 类都带 heuristic=True 标记。

两条方向都要测：
  - 真数据：L2 可评分规模 < L1 清单规模，且 computed-but-unformatted > 0
    （证明"explicit 错"里确有算对但没写格式的题）
  - 变异反证：若把 NOANS 全算算术错（旧假设），会夸大；分型必须改变读数
不会红的断言 = 装饰，故第 6 条是变异反证。
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import error_taxonomy as et  # noqa: E402

GSFT = ROOT / "results/qlora-ability-b/generations/generations_sft.json"
GDPO = ROOT / "results/qlora-ability-b/generations/generations_dpo.json"


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_unit_categories_all_five():
    cases = [
        ("Compute 1+1=2. Answer: 2", 2, et.ANSWER_CORRECT),
        ("Compute 1+1=3. Answer: 3", 2, et.ANSWER_WRONG_TRUEARITH),
        ("Step 3: 6015 ÷ 13: 13*46", 9, et.NOANS_TRUNCATED_MIDSTEP),
        ("Step 3: remainder 10. Final", 10, et.NOANS_COMPUTED_BUT_UNFORMATTED),
    ]
    for text, expected, want in cases:
        got = et.classify(text, expected)
        assert got["category"] == want, (text, got)
        assert got["expected"] == expected

    deg = et.classify("₁₅*₇₉=₁₁₈₅; ₁₁₈₅+₄₉=₁₂₃₄; ₁₂₃₄ mod ₈=₂. ₂ is", 2)
    assert deg["category"] == et.NOANS_DEGENERATE


def test_real_fixture_degenerate_unicode_and_repeat():
    # 真 fixture 值，从 generations_dpo.json 逐字拷出
    s100012 = (" Intermediate steps are not allowed in the answer; only the final integer, "
               "prefixed as 'Answer:', may appear. ₁₅*₇₉=₁₁₈₅; ₁₁₈₅+₄₉=₁₂₃₄; "
               "₁₂₃₄ mod ₈=₂. ₂ is the result. ₁₂₃₄ mod ₈=₂. ₂ is")
    assert et.classify(s100012, 2)["category"] == et.NOANS_DEGENERATE
    s100030 = "0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0"
    assert et.classify(s100030, 9)["category"] == et.NOANS_DEGENERATE


def test_real_fixture_computed_but_unformatted():
    # 这四题 explicit 口径判错，但文本里已经算出正确值，只差写进 Answer 字段
    fixtures = [
        ("... Dividing 3390 by 13: 13*260 = 3380, remainder 10. Final", 10),
        ("... Modulo M: 1142 mod 13. Dividing 1142 by 13: 13*87=1131, remainder 11", 11),
        ("... 3201-3195=6. Final integer: 6. Answer:", 6),
        ("... 9*516=4644, remainder 8. So 4652 mod 9 is 8.  Answer:", 8),
    ]
    for text, expected in fixtures:
        assert et.classify(text, expected)["category"] == et.NOANS_COMPUTED_BUT_UNFORMATTED


def test_noans_carries_heuristic_flag():
    for text, expected in [
        ("Step 3: 6015 ÷ 13: 13*46", 9),
        ("... remainder 10. Final", 10),
        ("0.0.0.0.0.0.0.0.0.", 9),
    ]:
        r = et.classify(text, expected)
        assert r["heuristic"] is True, r
    ok = et.classify("Answer: 2", 2)
    assert ok["heuristic"] is False


def test_real_generations_denominator_shrinks():
    for path in (GSFT, GDPO):
        a = et.effective_measurement(_load(path))
        assert a["L1_manifest"] == 60
        assert a["L2_scorable"] < a["L1_manifest"], a  # 分母确实缩水
        assert a["L3_heuristic_excluded"] > 0, a
        present = {k for k, v in a["categories"].items() if v > 0}
        assert len(present) >= 4, (path, present)
        assert a["computed_but_unformatted"] > 0, a  # 确有"算对没写格式"被 explicit 判错


def test_mutation_would_turn_red():
    """变异反证：旧假设把 NOANS 全算算术错，会夸大真算术错数。"""
    a = et.effective_measurement(_load(GDPO))
    naive = a["naive_arith_wrong_all_noans"]
    taxonomy = a["categories"][et.ANSWER_WRONG_TRUEARITH]
    assert naive > taxonomy, (naive, taxonomy)
    # 若分型无信息（所有 NOANS 都=算术错），上面不等式不成立 → 测试红


def test_effective_measurement_is_deterministic():
    rows = _load(GSFT)
    assert et.effective_measurement(rows) == et.effective_measurement(rows)


def test_render_md_states_honest_boundary():
    a = et.effective_measurement(_load(GSFT))
    b = et.effective_measurement(_load(GDPO))
    md = et.render_md(a, b)
    assert "finish_reason" in md  # 必须声明无法客观归因
    assert "启发式" in md
    assert "L1" in md and "L2" in md
