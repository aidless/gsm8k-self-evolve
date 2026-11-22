"""parser_sensitivity 的判定测试。

关键断言不是"某口径得几分"，而是"同一批生成换解析器会翻转判决符号"——
这台的职责就是把判决对解析器的依赖变成可复算读数。两条方向都要测：
  - 真数据（generation 文件）→ 必须 UNSTABLE（GAIN↔REGRESSION）
  - 构造的 STABLE 数据（两组文本相同）→ 必须 STABLE
不会红的符号断言 = 装饰，故另有一条变异反证。
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import parser_sensitivity as ps  # noqa: E402

HELD = ROOT / "results/qlora-ability-b/synth_heldout.jsonl"
GSFT = ROOT / "results/qlora-ability-b/generations/generations_sft.json"
GDPO = ROOT / "results/qlora-ability-b/generations/generations_dpo.json"


def test_parsers_unit_level():
    t = "Step 1: 21 * 72 = 1512. Answer: 3\nStep 1: redo 5."
    assert ps.last_int(t) == 5            # 抓到 Answer 之后续写的数字
    assert ps.first_answer(t) == 3        # 尊重显式 Answer
    assert ps.last_answer(t) == 3
    assert ps.upto_answer(t) == 3         # 截到 Answer 数字为止
    assert ps.strict_last_line(t) is None  # 末行不是 Answer 行
    assert ps.format_compliant(t) is False
    clean = "21 * 72 = 1512. 1512 mod 12 = 3.\nAnswer: 3"
    assert ps.last_int(clean) == 3
    assert ps.strict_last_line(clean) == 3
    assert ps.format_compliant(clean) is True


def test_align_missing_id_fail_closed():
    held = [{"id": "x", "answer": 1}]
    with pytest.raises(ValueError, match="缺 heldout id"):
        ps._align(held, {}, "sft")


def test_real_ledger_symbol_unstable():
    """真数据：PREREG 的 last_int 判 GAIN，explicit 口径判 REGRESSION。"""
    rep = ps.run(str(HELD), str(GSFT), str(GDPO), min_delta=0.05)
    assert rep["symbol_consistency"] == "UNSTABLE"
    assert rep["per_parser"]["last_int"]["label"] == "GAIN"
    assert rep["per_parser"]["first_answer"]["label"] == "REGRESSION"
    assert rep["per_parser"]["last_answer"]["label"] == "REGRESSION"
    assert rep["per_parser"]["last_int"]["delta"] > 0
    assert rep["per_parser"]["first_answer"]["delta"] < 0
    # 格式遵从读数：SFT 0/60、DPO 5/60（不管答案对错）
    assert rep["format_compliance"] == {"sft": 0, "dpo": 5, "total": 60}


def test_stable_when_both_arms_identical():
    """构造：两组文本相同 → 所有口径 delta=0 → NO_GAIN → STABLE。"""
    rep = ps.run(str(HELD), str(GSFT), str(GSFT), min_delta=0.05)
    assert rep["symbol_consistency"] == "STABLE"
    assert set(rep["labels"]) == {"NO_GAIN"}
    for v in rep["per_parser"].values():
        assert v["delta"] == 0.0


def test_mutation_would_turn_red(monkeypatch):
    """变异反证：若 last_int 被改成恒返回 0，UNSTABLE 断言必须失败。"""
    assert ps.PARSERS["last_int"] is ps.last_int
    monkeypatch.setitem(ps.PARSERS, "last_int", lambda t: 0)
    rep = ps.run(str(HELD), str(GSFT), str(GDPO), min_delta=0.05)
    # 恒 0 解析下 last_int 不再 GAIN —— 证明上面的符号断言不是装饰
    assert rep["per_parser"]["last_int"]["label"] != "GAIN"
