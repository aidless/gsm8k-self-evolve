"""合成能力任务的数据/判据测试：真输入→真输出，不 mock。

fail-closed 反证：篡改 ground truth / 让 rejected==chosen / train 与 heldout seed 重叠
都必须被断言抓住。
"""
import pytest

from scripts.synth_ability import (
    A_RANGE, B_RANGE, C_RANGE, M_RANGE, HELD_BASE, HELD_N, TRAIN_N,
    gen_case, make_pair, score_response, gen_train_pairs, gen_heldout,
)


def test_gen_case_ground_truth_exact():
    for s in range(50):
        c = gen_case(s)
        assert c["prod"] == c["a"] * c["b"]
        assert c["sum"] == c["prod"] + c["c"]
        assert c["answer"] == c["sum"] % c["m"]
        assert 0 <= c["answer"] < c["m"]


def test_gen_case_deterministic():
    assert gen_case(123) == gen_case(123)
    assert gen_case(123) != gen_case(124)


def test_pair_chosen_correct_rejected_wrong():
    for s in range(50):
        case = gen_case(s)
        pair = make_pair(case)
        assert score_response(pair["chosen"], case["answer"]) is True
        assert score_response(pair["rejected"], case["answer"]) is False
        assert pair["meta"]["answer"] == case["answer"]
        assert pair["meta"]["wrong"] != case["answer"]
        assert case["prompt"] == pair["prompt"]


def test_pair_diff_only_last_step():
    """chosen/rejected 前缀（中间步骤）必须完全一致，只有最后余数不同。"""
    for s in range(30):
        pair = make_pair(gen_case(s))
        c, r = pair["chosen"], pair["rejected"]
        # 拆到最后一次 " = " 之前应完全相同
        assert c.rsplit(" = ", 1)[0] == r.rsplit(" = ", 1)[0]


def test_fail_closed_wrong_ground_truth_is_detected():
    """若有人篡改 case 的 answer，score_response 对 chosen 应判 False——证明判据真的连着 gt。"""
    case = gen_case(7)
    pair = make_pair(case)
    assert score_response(pair["chosen"], case["answer"]) is True
    assert score_response(pair["chosen"], (case["answer"] + 1) % case["m"]) is False


def test_fail_closed_no_number_is_wrong():
    assert score_response("no integer here", gen_case(1)["answer"]) is False
    assert score_response("", gen_case(1)["answer"]) is False


def test_train_heldout_seeds_disjoint():
    train = {c["seed"] for c in [gen_case(s) for s in range(TRAIN_N)]}
    held = {c["seed"] for c in gen_heldout(HELD_N)}
    assert train.isdisjoint(held)
    assert HELD_BASE >= TRAIN_N


def test_gen_sizes_and_ranges():
    assert len(gen_train_pairs()) == TRAIN_N
    assert len(gen_heldout()) == HELD_N
    for c in gen_heldout():
        assert A_RANGE[0] <= c["a"] <= A_RANGE[1]
        assert M_RANGE[0] <= c["m"] <= M_RANGE[1]


def test_all_pairs_chosen_beats_rejected():
    """全量 400 条：chosen 全对、rejected 全错（真值来自 Python，非模型）。"""
    pairs = gen_train_pairs()
    assert all(score_response(p["chosen"], p["meta"]["answer"]) for p in pairs)
    assert all(not score_response(p["rejected"], p["meta"]["answer"]) for p in pairs)
