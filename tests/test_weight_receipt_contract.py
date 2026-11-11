# P2 权重杠杆回执契约测试。
#
# 动机（SIA, arXiv:2605.27276 §Limitations 的 Coupled co-evolutionary Goodhart）：
# 双杠杆共用固定 verifier 时，权重侧的每次落地都必须可被独立复核——"我训了"
# 不能只是一句话。故 apply() 的返回值不是可忽略的副作用，而是证据回执：
#   {"adapter_sha256": <64 hex>, "verifier_id": <与循环一致>, "steps": <非负整数>}
# 拿不到合契约的回执 = 这次权重改动无法进证据链 → fail-closed 停机，绝不接受。
#
# 全部用合成夹具，零训练、零 GPU（AGENTS.md 第 17 条）。
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evokit.lever_selector import FailureProfile, run_interleaved_loop  # noqa: E402

SHA = "a" * 64


class _ReceiptUpdater:
    """返回调用方指定回执的替身；不训练、不落盘。"""

    def __init__(self, receipt):
        self.receipt = receipt
        self.calls = 0

    def apply(self, payload):
        self.calls += 1
        return self.receipt


def _profile(_i):
    # reasoning_errors 占多 → 选择器走 weight 杠杆（R2_capability_bottleneck）
    return FailureProfile(harness_errors=1, reasoning_errors=5)


def _run(updater, rounds=2):
    return run_interleaved_loop(
        rounds=rounds, diagnose=_profile,
        propose_harness=lambda i: {"answer_policy": "h"},
        propose_weight=lambda i: {"lora_rank": 32},
        evaluate=lambda cand, i: {"score": 0.95, "verifier_id": "v-fixed"},
        verifier_id="v-fixed", weight_updater=updater,
        min_gain=0.02, baseline_score=0.90,
    )


def test_valid_receipt_is_recorded_in_round():
    # GREEN：回执合契约 → 逐字进 records，可被下游按 sha256 复核
    updater = _ReceiptUpdater({"adapter_sha256": SHA, "verifier_id": "v-fixed", "steps": 7})
    report = _run(updater)
    weight_rounds = [r for r in report["rounds"] if r["lever"] == "weight"]
    assert weight_rounds, "第一轮应为 weight 杠杆"
    assert weight_rounds[0]["weight_receipt"]["adapter_sha256"] == SHA
    assert weight_rounds[0]["weight_receipt"]["steps"] == 7
    assert report["stopped_reason"] is None


def test_missing_receipt_fails_closed():
    # RED 反证：apply 返回 None = 无法证明权重被改过 → 一句都不许接受
    report = _run(_ReceiptUpdater(None), rounds=3)
    assert report["stopped_reason"] == "weight_receipt_invalid"
    assert len(report["rounds"]) == 1
    assert report["rounds"][0]["accepted"] is False
    assert report["rounds"][0]["rollback"] is True


def test_receipt_verifier_drift_fails_closed():
    # RED 反证：权重是在另一个 verifier 下训的 → 身份漂移，停机
    report = _run(_ReceiptUpdater(
        {"adapter_sha256": SHA, "verifier_id": "v-other", "steps": 3}), rounds=3)
    assert report["stopped_reason"] == "weight_verifier_drift"
    assert len(report["rounds"]) == 1
    assert report["rounds"][0]["accepted"] is False


def test_malformed_sha_fails_closed():
    # RED 反证：sha 形状不对（长度/字符集）与缺失等价，不许蒙混
    for bad in ("", "a" * 63, "z" * 64, SHA.upper()):
        report = _run(_ReceiptUpdater(
            {"adapter_sha256": bad, "verifier_id": "v-fixed", "steps": 1}), rounds=2)
        assert report["stopped_reason"] == "weight_receipt_invalid", bad
        assert report["rounds"][0]["accepted"] is False


def test_negative_steps_fails_closed():
    # RED 反证：步数为负说明回执是编的
    report = _run(_ReceiptUpdater(
        {"adapter_sha256": SHA, "verifier_id": "v-fixed", "steps": -1}), rounds=2)
    assert report["stopped_reason"] == "weight_receipt_invalid"


def test_non_mapping_receipt_fails_closed():
    # RED 反证：回执必须是 mapping，字符串/列表都不算证据
    for bad in ("trained", ["a" * 64], 42):
        report = _run(_ReceiptUpdater(bad), rounds=2)
        assert report["stopped_reason"] == "weight_receipt_invalid", bad
