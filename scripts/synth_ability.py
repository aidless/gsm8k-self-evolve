"""合成能力任务：受控取模算术 (A*B+C) mod M，带精确 ground truth。

选项 B（用户 2026-11-22 选定）：合成有明确 ground truth 的能力任务重训 + 评测，
回答"权重线改完有没有用"。这是一个**全新的能力任务**，与原写作偏好 DPO 数据
(dpo_p0v2) 完全不同；任何结论只在本任务 + 本 verifier + 本步数条件下解释，
不构成原 p2 adapter 的能力提升，也不宣称 GSM8K/TMLR 指标提升。

纯 Python，无外部依赖，可本地 TDD。ground truth 由 Python 精确计算，不靠模型自评。
train 用 seed [0, TRAIN_N)，heldout 用 seed [HELD_BASE, HELD_BASE+HELD_N)，两者不重叠。
"""
import random
import re

TRAIN_N = 400
HELD_BASE = 100000
HELD_N = 60

M_RANGE = (7, 13)      # 模数范围
A_RANGE = (10, 99)     # A 两位数（LLM 无 scratchpad 常出错 → 有提升空间）
B_RANGE = (10, 99)     # B 两位数
C_RANGE = (1, 50)
NUM = re.compile(r"-?\d+")


def gen_case(seed: int) -> dict:
    """确定性生成一个案例。相同 seed 必得相同案例（可复现）。"""
    r = random.Random(seed)
    a = r.randint(*A_RANGE)
    b = r.randint(*B_RANGE)
    c = r.randint(*C_RANGE)
    m = r.randint(*M_RANGE)
    prod = a * b
    summ = prod + c
    answer = summ % m
    return {
        "id": f"s{seed:06d}",
        "seed": seed,
        "a": a, "b": b, "c": c, "m": m,
        "prod": prod, "sum": summ, "answer": answer,
        "prompt": (
            "Compute (A * B + C) mod M step by step, then write the final "
            "integer alone on the last line prefixed with 'Answer:'.\n"
            f"A={a}, B={b}, C={c}, M={m}."
        ),
    }


def make_pair(case: dict) -> dict:
    """构造 DPO 偏好对：chosen 是完整正确的分步链，rejected 只在最后取模步出错。

    差分只落在最后一步（正确余数 vs 错误余数），中间和产品/加法步骤完全一致，
    给 DPO 一个干净的"最后取模要算对"信号，可被 heldout 上的同类题复用。
    """
    r = random.Random(str(case["seed"]) + "|wrong")
    a, b, c, m = case["a"], case["b"], case["c"], case["m"]
    prod, summ, ans = case["prod"], case["sum"], case["answer"]
    delta = r.choice([d for d in (-3, -2, -1, 1, 2, 3)])
    wrong = (ans + delta) % m
    if wrong == ans:                      # 模较小时偏移可能绕回，换个非零偏移
        wrong = (ans + 1) % m
    prefix = f"{a} * {b} = {prod}. {prod} + {c} = {summ}. {summ} mod {m} = "
    return {
        "prompt": case["prompt"],
        "chosen": f"{prefix}{ans}. Answer: {ans}",
        "rejected": f"{prefix}{wrong}. Answer: {wrong}",
        "meta": {"answer": ans, "wrong": wrong, "case_id": case["id"]},
    }


def score_response(response: str, answer: int) -> bool:
    """从模型输出抽最后一个整数，与 ground truth 精确比对。

    分步链末尾是 'Answer: X'，取最后一个整数即最终答案；如果模型复读 prompt
    里的数字，最后一个整数仍是它自己给出的答案行。无整数则判错。
    """
    nums = NUM.findall((response or "").strip().replace(",", ""))
    if not nums:
        return False
    try:
        return int(nums[-1]) == answer
    except ValueError:
        return False


def gen_train_pairs(n: int = TRAIN_N) -> list[dict]:
    return [make_pair(gen_case(s)) for s in range(n)]


def gen_heldout(n: int = HELD_N) -> list[dict]:
    return [gen_case(HELD_BASE + i) for i in range(n)]
