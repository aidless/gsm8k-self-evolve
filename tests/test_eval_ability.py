"""eval_ability 纯逻辑测试：真数据→真判定，不 mock 模型。

fail-closed 反证：generation 与 heldout 错位、无整数输出、篡改 gt，都必须被判错。
"""
import json

import pytest

from scripts.eval_ability import (
    load_heldout, score_generations, verdict, _last_int,
)


def _write(tmp_path, rows):
    p = tmp_path / "h.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                 encoding="utf-8")
    return str(p)


def test_load_heldout_roundtrip(tmp_path):
    rows = [{"id": "s100000", "prompt": "q1", "answer": 3},
            {"id": "s100001", "prompt": "q2", "answer": 7}]
    got = load_heldout(_write(tmp_path, rows))
    assert len(got) == 2
    assert got[0]["id"] == "s100000" and got[1]["answer"] == 7


def test_load_heldout_missing_field_fails(tmp_path):
    p = tmp_path / "bad.jsonl"
    p.write_text(json.dumps({"id": "x", "prompt": "q"}) + "\n", encoding="utf-8")
    with pytest.raises(AssertionError):
        load_heldout(str(p))


def test_score_generations_counts_correct():
    held = [{"id": "a", "answer": 3}, {"id": "b", "answer": 7}]
    gens = ["step... Answer: 3", "step... Answer: 5"]
    rep = score_generations(held, gens)
    assert rep["passed"] == 1 and rep["total"] == 2 and rep["accuracy"] == 0.5
    assert rep["details"][0]["correct"] is True
    assert rep["details"][1]["correct"] is False
    assert rep["details"][1]["parsed"] == 5


def test_score_generations_length_mismatch_fails_closed():
    with pytest.raises(ValueError):
        score_generations([{"id": "a", "answer": 1}], [])


def test_no_integer_output_is_wrong():
    rep = score_generations([{"id": "a", "answer": 1}], ["I cannot compute that"])
    assert rep["passed"] == 0
    assert rep["details"][0]["parsed"] is None


def test_last_int_handles_commas_and_negatives():
    assert _last_int("Answer: 1,234") == 1234
    assert _last_int("answer -5") == -5
    assert _last_int("nothing") is None


def test_verdict_labels():
    base = {"accuracy": 0.5}
    assert verdict(base, {"accuracy": 0.6}, min_delta=0.05)["label"] == "GAIN"
    assert verdict(base, {"accuracy": 0.5}, min_delta=0.05)["label"] == "NO_GAIN"
    assert verdict(base, {"accuracy": 0.3}, min_delta=0.05)["label"] == "REGRESSION"
    assert verdict(base, {"accuracy": 0.6}, min_delta=0.05)["delta"] == 0.1


def test_verdict_threshold_is_not_post_hoc():
    """门槛是跑前固定的：0.06 提升在 min_delta=0.05 下 GAIN，在 0.10 下 NO_GAIN。"""
    base = {"accuracy": 0.50}
    adj = {"accuracy": 0.56}
    assert verdict(base, adj, min_delta=0.05)["label"] == "GAIN"
    assert verdict(base, adj, min_delta=0.10)["label"] == "NO_GAIN"
