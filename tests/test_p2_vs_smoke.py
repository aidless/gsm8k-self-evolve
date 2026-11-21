"""p2 vs smoke 提取器的反硬编码测试。

verifier: 提取函数对落盘源断言；篡改源里任一数字必须抛 AssertionError。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from scripts.p2_vs_smoke import (  # noqa: E402
    SMOKE_SHA, P2_SHA, build_comparison, load_run, parse_p2_rows,
)


def test_comparison_reads_real_persisted_numbers():
    c = build_comparison()
    assert c["smoke"]["steps"] == 10 and c["p2"]["steps"] == 50
    assert c["smoke"]["adapter_sha256"] == SMOKE_SHA
    assert c["p2"]["adapter_sha256"] == P2_SHA
    assert c["smoke"]["adapter_sha256"] != c["p2"]["adapter_sha256"]
    assert c["p2"]["accuracy_all_steps"] == [1.0]
    assert c["p2"]["reward_margin_last"] > c["p2"]["reward_margin_first"]
    assert c["provenance"]["no_paper_number_changed"] is True


def test_parse_p2_rows_extracts_real_rewards_not_hardcoded():
    sample = (
        "{'loss': 0.0007, 'rewards/chosen': 14.16, 'rewards/rejected': -5.50, "
        "'rewards/accuracies': 1.0, 'epoch': 0.1}\n"
        "{'loss': 0.0, 'rewards/chosen': 21.65, 'rewards/rejected': -5.56, "
        "'rewards/accuracies': 1.0, 'epoch': 1.0}\n"
    )
    rows = parse_p2_rows(sample)
    assert len(rows) == 2
    assert rows[0]["chosen"] == 14.16 and rows[1]["rejected"] == -5.56
    assert rows[1]["epoch"] == 1.0


def test_tampered_source_fails_closed(monkeypatch):
    run = load_run()
    run["p2"]["adapter"]["sha256"] = "0" * 64
    monkeypatch.setattr("scripts.p2_vs_smoke.load_run", lambda: run)
    with pytest.raises(AssertionError):
        build_comparison()
