# P2 杠杆选择器测试：SIA 式反馈驱动的 harness / weight 双杠杆交错循环。
# 源自 arXiv:2605.27276：Feedback-Agent 看完整轨迹选动作；两杠杆共用一个
# 固定 verifier 会带来 Coupled co-evolutionary Goodhart，故 verifier 身份必须冻结。
# 本测试只用合成夹具，不跑任何训练、不产出任何实验结论（AGENTS.md 第 17 条）。
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evokit.lever_selector import (  # noqa: E402
    FailureProfile, LeverSignal, interleaved_plan, run_interleaved_loop, select_lever,
)


def test_cold_start_selects_harness():
    # GREEN：无历史 → 冷启动先改 harness（SIA: Best-of-N BC 冷启动）
    d = select_lever((), FailureProfile(0, 0), weight_available=True)
    assert d.lever == "harness"
    assert d.rule_id == "R0_cold_start"


def test_bottleneck_routing():
    # GREEN：scaffold 类错误多 → harness；推理/能力类错误多 → weight
    profile = FailureProfile(harness_errors=5, reasoning_errors=1)
    assert select_lever((), profile, weight_available=True).lever == "harness"
    assert select_lever((), profile, weight_available=True).rule_id == "R1_scaffold_bottleneck"
    profile2 = FailureProfile(harness_errors=1, reasoning_errors=5)
    d = select_lever((), profile2, weight_available=True)
    assert d.lever == "weight"
    assert d.rule_id == "R2_capability_bottleneck"


def test_weight_unprovisioned_fails_closed_to_harness():
    # GREEN：权重侧没接训练通道时绝不假装在改权重（本机禁长跑，AGENTS.md 17）
    d = select_lever((), FailureProfile(1, 5), weight_available=False)
    assert d.lever == "harness"
    assert d.rule_id == "R3_weight_unprovisioned"


def test_tie_alternates():
    # GREEN：两杠杆平分秋色时严格交错
    signals = (LeverSignal(lever="harness", delta=0.03, verifier_id="v1"),)
    d = select_lever(signals, FailureProfile(2, 2), weight_available=True)
    assert d.lever == "weight"
    assert d.rule_id == "R4_interleave_tie"


def test_plan_is_strictly_interleaved():
    plan = interleaved_plan(6, weight_available=True)
    assert [d.lever for d in plan] == ["harness", "weight"] * 3
    assert plan[0].rule_id == "R0_cold_start"


def test_invalid_profile_rejected():
    with pytest.raises(ValueError):
        select_lever((), FailureProfile(-1, 0), weight_available=True)


class _FakeWeightUpdater:
    """纯记录用的权重杠杆替身：绝不训练，只记被调用过。

    回执按 lever_selector.validate_weight_receipt() 的契约构造（sha/steps/verifier），
    否则循环会按 fail-closed 停机——见 tests/test_weight_receipt_contract.py。
    """

    SHA = "b" * 64
    VERIFIER = "v-fixed"

    def __init__(self):
        self.calls = 0

    def apply(self, payload):
        self.calls += 1
        return {"adapter_sha256": self.SHA, "verifier_id": self.VERIFIER,
                "steps": self.calls}


def test_loop_interleaves_and_rolls_back_on_no_gain():
    # GREEN：交错执行 + 无增益回滚；每个决定都带 rule_id 便于审计
    updater = _FakeWeightUpdater()
    applied = []

    def propose_harness(round_i):
        applied.append("harness")
        return {"answer_policy": f"step-calc-{round_i}"}

    def propose_weight(round_i):
        applied.append("weight")
        return {"lora_rank": 32}

    def evaluate(candidate, round_i):
        # 第 0 轮有增益，第 1 轮无增益（应回滚），后面保持有增益
        score = 0.90 if round_i == 1 else 0.95
        return {"score": score, "verifier_id": "v-fixed"}

    report = run_interleaved_loop(
        rounds=4, diagnose=lambda i: FailureProfile(2, 2),
        propose_harness=propose_harness, propose_weight=propose_weight,
        evaluate=evaluate, verifier_id="v-fixed", weight_updater=updater,
        min_gain=0.02, baseline_score=0.90)
    levers = [r["lever"] for r in report["rounds"]]
    assert levers == ["harness", "weight", "harness", "weight"]
    assert updater.calls == 2
    assert report["rounds"][1]["rollback"] is True
    assert report["rounds"][0]["accepted"] is True
    assert all(r["rule_id"] for r in report["rounds"])


def test_verifier_drift_fails_closed():
    # GREEN：两杠杆共用 verifier，身份变了立刻停（Goodhart 防线）
    report = run_interleaved_loop(
        rounds=3, diagnose=lambda i: FailureProfile(2, 2),
        propose_harness=lambda i: {}, propose_weight=lambda i: {},
        evaluate=lambda cand, i: {"score": 0.95,
                                  "verifier_id": "v-fixed" if i == 0 else "v-other"},
        verifier_id="v-fixed", weight_updater=_FakeWeightUpdater(),
        min_gain=0.02, baseline_score=0.90)
    assert report["stopped_reason"] == "verifier_drift"
    assert len(report["rounds"]) == 2
    assert report["rounds"][1]["accepted"] is False
