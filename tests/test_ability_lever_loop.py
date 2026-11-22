"""真实 ground-truth objective 双杠杆闭环：分数必须是 ability-B 实测读数。

RED→GREEN + 两向变异反证：
- 分数来自盘上 parser_sensitivity.json 的 last_int，不是旧脚本的注入序列 0.86/0.93；
- 权重回执是 ability-B 的 b5e8ff…，steps=50，validate 过契约；
- adapter_sha 与盘上字节不符时 fail-closed（变异反证：这道闸会红）；
- UNSTABLE 边界必须写进 not_claimed（禁止单口径宣称能力）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import run_ability_lever_loop as ab  # noqa: E402
from evokit.lever_selector import run_interleaved_loop, validate_weight_receipt  # noqa: E402

ABILITY_SHA = "b5e8ff39193247ce8e61f3b18724e13ff1dd8102506c8983959836086a089db9"


def _prereg():
    return json.loads(ab.PARSER_SENSITIVITY.read_text(encoding="utf-8"))["per_parser"]["last_int"]


def test_evaluate_uses_real_ability_b_accuracy_not_injected_scores():
    """核心断言：evaluate 返回真实 heldout 准确率，不是注入的 0.86/0.93。"""
    payload = ab.build_report()
    scores = [r["score"] for r in payload["loop"]["rounds"]]
    prereg = _prereg()
    assert scores[0] == prereg["sft_accuracy"]   # 0.4333
    assert scores[1] == prereg["dpo_accuracy"]   # 0.5667
    assert 0.86 not in scores and 0.93 not in scores, "必须从真实 ground-truth 读数，不可注入合成分数"
    assert payload["loop"]["final_score"] == prereg["dpo_accuracy"]


def test_delta_matches_ability_report_within_rounding():
    """闭环里 weight 轮的 delta 必须复算自盘上 ability_report.json。"""
    payload = ab.build_report()
    report = json.loads((ab.RESULTS / "ability_report.json").read_text(encoding="utf-8"))
    weight_round = payload["loop"]["rounds"][1]
    assert abs(weight_round["delta"] - report["verdict"]["delta"]) < 0.01
    assert weight_round["accepted"] is True
    assert payload["loop"]["accepted"] == [0, 1]


def test_weight_receipt_is_real_ability_b_adapter():
    payload = ab.build_report()
    receipt = payload["loop"]["rounds"][1]["weight_receipt"]
    assert receipt["adapter_sha256"] == ABILITY_SHA
    assert receipt["steps"] == 50
    assert payload["receipt_validation"]["reason"] is None
    assert all(p["match"] for p in payload["receipt_crosscheck_local_vs_disk"].values())


def test_unstable_parser_boundary_is_declared():
    """UNSTABLE 边界必须写进 not_claimed，禁止单口径 GAIN 冒充能力。"""
    payload = ab.build_report()
    evidence = payload["evidence"]
    assert evidence["prereg_accuracy"]["symbol_consistency"] == "UNSTABLE"
    joined = " ".join(evidence["not_claimed"]).lower()
    assert "capability" in joined and "parser" in joined


def test_sha_mismatch_on_disk_fails_closed(tmp_path):
    """变异反证：篡改盘上 adapter_sha 必须让回执契约失败（这道闸会红）。

    关键：不符时必须返回**非 mapping**，而不是格式合法的假 sha——
    后者会被 validate_weight_receipt 放行，闸就成了装饰（本测试抓过这个真 bug）。
    """
    bad_receipt = tmp_path / "bad_receipt.json"
    bad_receipt.write_text(json.dumps({
        "adapter_sha256": "f" * 64, "verifier_id": ab.VERIFIER, "steps": 50,
    }), encoding="utf-8")
    updater = ab._AbilityWeightUpdater(bad_receipt, ab.ADAPTER, ab.VERIFIER)
    raw = updater.apply({"lever": "weight"})
    assert raw is None, "产物身份不符时必须返回非 mapping，不能返回假 sha"
    assert updater.calls[0]["error"] == "adapter_sha_mismatch_on_disk"
    cleaned, reason = validate_weight_receipt(raw, ab.VERIFIER)
    assert cleaned is None and reason == "weight_receipt_invalid"


def test_verifier_drift_stops_loop():
    """第二向反证：evaluate 回报的 verifier 不一致必须停机。"""
    def diagnose(i):
        return ab.FailureProfile(10, 0)

    def propose(i):
        return {"lever": "harness", "round": i}

    def bad_evaluate(candidate, i):
        return {"verifier_id": "wrong-verifier", "score": 0.5}

    report = run_interleaved_loop(
        rounds=1, diagnose=diagnose, propose_harness=propose,
        propose_weight=propose, evaluate=bad_evaluate, verifier_id=ab.VERIFIER,
    )
    assert report["stopped_reason"] == "verifier_drift"
    assert report["accepted"] == []
