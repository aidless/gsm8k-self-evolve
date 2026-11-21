"""真 DPO p2 adapter 驱动双杠杆闭环的可复算测试。

verifier: 脚本产出 JSON 的字段断言 + 本地回执与云端回执逐字段对表 +
RED→GREEN（build_report 未实现时 import 失败）。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.run_dpo_lever_loop import (  # noqa: E402
    EXPECTED_SHA,
    build_report,
)


def test_p2_adapter_drives_weight_lever_with_real_receipt():
    payload = build_report()
    loop = payload["loop"]
    assert loop["stopped_reason"] is None
    assert loop["accepted"] == [0, 1]
    assert [r["lever"] for r in loop["rounds"]] == ["harness", "weight"]
    weight_receipt = loop["rounds"][1]["weight_receipt"]
    assert weight_receipt is not None
    assert weight_receipt["adapter_sha256"] == EXPECTED_SHA
    assert weight_receipt["steps"] == 50
    assert payload["receipt_validation"]["reason"] is None


def test_local_receipt_matches_cloud_receipt_field_by_field():
    crosscheck = build_report()["receipt_crosscheck_local_vs_cloud"]
    assert crosscheck, "crosscheck must not be empty"
    for field, pair in crosscheck.items():
        assert pair["match"] is True, f"{field}: local={pair['local']} cloud={pair['cloud']}"


def test_evidence_explicitly_disclaims_capability_and_synthetic_scores():
    evidence = build_report()["evidence"]
    joined = " ".join(evidence["not_claimed"]).lower()
    assert "gsm8k" in joined and "synthetic" in joined
    assert evidence["optimizer_steps"] == 50
    assert evidence["training_hardware"].startswith("AMD")
