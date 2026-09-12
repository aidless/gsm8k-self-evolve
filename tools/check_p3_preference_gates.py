#!/usr/bin/env python3
"""A 线 P3 偏好门：KTO 偏好信号 + 锚定集回归（fail-closed，含非空性反证）。

门清单：
  P1 前景理论形状：收益凹 / 损失凸 / 损失厌恶（同一幅度下损失权重更大）
  P2 锚定回归判定：容差内通过；超容差拒绝；缺锚点视为回归（fail-closed）
  P3 择优语义：**使锚定集回退的候选必须出局**，无论其可欲效用多高
  P4 非空性反证：放宽容差后回退候选会入选 → 证明 P3 确有鉴别力（非恒真）

基础设施，标准库 only，不含 bench 语义、不产生也不声称任何基准分数。
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from evokit.preference import (  # noqa: E402
    anchor_regression, kto_weight, prospect_value, select_by_desirability,
)


def p1_prospect_shape():
    bad = []
    # 收益凹：v(2x) < 2 v(x)
    if not (prospect_value(2.0) < 2 * prospect_value(1.0)):
        bad.append("收益侧非凹")
    # 损失凸：|v(-2x)| < 2|v(-x)|
    if not (abs(prospect_value(-2.0)) < 2 * abs(prospect_value(-1.0))):
        bad.append("损失侧非凸")
    # 损失厌恶：|v(-1)| > v(1)
    if not (abs(prospect_value(-1.0)) > prospect_value(1.0)):
        bad.append("无损失厌恶")
    # 零点连续
    if prospect_value(0.0) != 0.0:
        bad.append("v(0) != 0")
    # 二元信号：可欲为正、不可欲为负
    if not (kto_weight(True) > 0 > kto_weight(False)):
        bad.append("KTO 符号方向错")
    # 类型守卫（fail-closed）
    for fn, arg in ((prospect_value, "x"), (kto_weight, 1)):
        try:
            fn(arg) if fn is prospect_value else fn(arg)
            bad.append(f"{fn.__name__} 未拒绝非法输入")
        except (TypeError, ValueError):
            pass
    ok = not bad
    print(f"  [P1] 前景理论形状（凹/凸/损失厌恶/符号）  {'PASS' if ok else 'FAIL'}")
    for b in bad:
        print(f"       {b}")
    return ok


def p2_anchor_regression():
    bad = []
    base = {"a": 1.0, "b": 0.8}

    r = anchor_regression(base, {"a": 1.0, "b": 0.8})
    if not r["ok"] or r["worst_delta"] != 0.0:
        bad.append(f"同分应通过: {r}")

    r = anchor_regression(base, {"a": 1.0, "b": 0.7})
    if r["ok"] or r["regressed"] != ["b"]:
        bad.append(f"回退 0.1 应拒绝且指认 b: {r}")

    r = anchor_regression(base, {"a": 1.05, "b": 0.75}, tol=0.06)
    if not r["ok"]:
        bad.append(f"容差内应通过: {r}")

    r = anchor_regression(base, {"a": 1.0})
    if r["ok"] or "b" not in r["regressed"]:
        bad.append(f"缺锚点应视为回归(fail-closed): {r}")

    ok = not bad
    print(f"  [P2] 锚定回归判定（容差/指认/缺锚点）  {'PASS' if ok else 'FAIL'}")
    for b in bad:
        print(f"       {b}")
    return ok


def p3_selection():
    bad = []
    base = {"a": 1.0, "b": 1.0}

    cands = [
        # 可欲效用很高，但让锚点 b 回退 → 必须出局
        {"name": "greedy", "desirable": True, "magnitude": 9.0,
         "anchor_scores": {"a": 1.0, "b": 0.2}},
        # 可欲效用较低，但锚定集无回退 → 应入选
        {"name": "safe", "desirable": True, "magnitude": 1.0,
         "anchor_scores": {"a": 1.0, "b": 1.0}},
        # 不可欲 → 效用为负，不应被选（无更优时也不选它）
        {"name": "bad", "desirable": False, "magnitude": 1.0,
         "anchor_scores": {"a": 1.0, "b": 1.0}},
    ]
    res = select_by_desirability(cands, base)
    if res["chosen"] != "safe":
        bad.append(f"应选 safe（greedy 回退锚点）: {res}")
    if "greedy" not in [r["name"] for r in res["rejected"]]:
        bad.append(f"greedy 应在 rejected: {res}")

    # 全部回退 → 不选任何候选（而不是退而求其次选个坏的）
    res2 = select_by_desirability(
        [{"name": "x", "desirable": True, "magnitude": 5.0,
          "anchor_scores": {"a": 0.1, "b": 1.0}}], base)
    if res2["chosen"] is not None:
        bad.append(f"全回退时应 chosen=None: {res2}")

    ok = not bad
    print(f"  [P3] 择优语义（回退者出局，不论效用）  {'PASS' if ok else 'FAIL'}")
    for b in bad:
        print(f"       {b}")
    return ok


def p4_nonvacuity():
    """反证：把容差放到极大，greedy 就会入选 → 证明 P3 的拒绝来自锚定门，
    而不是恒真地拒绝一切。"""
    base = {"a": 1.0, "b": 1.0}
    cands = [{"name": "greedy", "desirable": True, "magnitude": 9.0,
              "anchor_scores": {"a": 1.0, "b": 0.2}}]
    strict = select_by_desirability(cands, base, tol=0.0)
    loose = select_by_desirability(cands, base, tol=10.0)

    pts = [
        ("严格容差(0.0) 拒绝 greedy", strict["chosen"] is None, True),
        ("放宽容差(10.0) 选中 greedy", loose["chosen"] == "greedy", True),
        ("两种容差给出不同结论（门有鉴别力）",
         strict["chosen"] != loose["chosen"], True),
    ]
    ok = all(g for _, _, g in pts)
    print(f"  [P4] 非空性反证（容差影响结论）  {'PASS' if ok else 'FAIL'}")
    for label, val, good in pts:
        print(f"       {'ok ' if good else 'BAD'} {label} = {val}")
    return ok


def main():
    print("A 线 P3 偏好门（KTO 信号 + 锚定回归）")
    results = [
        ("P1 前景形状", p1_prospect_shape()),
        ("P2 锚定回归", p2_anchor_regression()),
        ("P3 择优语义", p3_selection()),
        ("P4 非空性", p4_nonvacuity()),
    ]
    print()
    failed = [n for n, ok in results if not ok]
    if failed:
        print(f"PREFERENCE GATES FAIL: {failed}")
        return 1
    print(f"PREFERENCE GATES PASS: {len(results)} 门全过（含非空性反证）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
