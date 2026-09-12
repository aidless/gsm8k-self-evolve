#!/usr/bin/env python3
"""KTO 偏好信号 + 锚定集回归门（P3-HARDEN A 线 · 最小可验单元）。

迁移自 KTO（P2 台账 A-P35/P36）：用「可欲 / 不可欲」**二元信号**做偏好对齐，
其效用含前景理论（Kahneman–Tversky）的损失厌恶与收益凹/损失凸形状。

本模块只落地**可离线确定性验证的结构**，不声称任何训练效果：
  - `prospect_value`        前景理论价值函数（收益凹、损失凸、λ 倍损失厌恶）
  - `kto_weight`             二元信号 → 效用权重（可欲为正、不可欲为负且被放大）
  - `anchor_regression`      锚定集回归判定（候选不得使锚定分数回退超容差）
  - `select_by_desirability` 在候选中选「不回退锚定集且可欲效用最大」者

明确**不做**（诚实边界）：真实训练 / 模型前向 / 权重加载均未实现（本机无对应
权重与 GPU）；本模块不产生、也不声称任何基准分数。

零依赖：标准库 only。
"""

__all__ = [
    "prospect_value", "kto_weight",
    "anchor_regression", "select_by_desirability",
]

# 前景理论默认参数（Kahneman–Tversky 1992 常用取值；此处作为**默认超参**记录，
# 不声称其为最优，亦不据此宣称任何效果）
DEFAULT_ALPHA = 0.88   # 收益侧曲率
DEFAULT_BETA = 0.88    # 损失侧曲率
DEFAULT_LAMBDA = 2.25  # 损失厌恶系数


def prospect_value(x, alpha=DEFAULT_ALPHA, beta=DEFAULT_BETA,
                   lam=DEFAULT_LAMBDA):
    """前景理论价值函数。

    x >= 0 → x**alpha（收益凹）；x < 0 → -lam * (-x)**beta（损失凸且被放大）。
    参数据实为默认超参，非经调优结论。
    """
    if not isinstance(x, (int, float)) or isinstance(x, bool):
        raise TypeError("x 必须为数值")
    if x >= 0:
        return float(x) ** alpha
    return -lam * ((-float(x)) ** beta)


def kto_weight(desirable, magnitude=1.0, alpha=DEFAULT_ALPHA,
               beta=DEFAULT_BETA, lam=DEFAULT_LAMBDA):
    """二元可欲信号 → 效用权重。

    desirable=True 视为收益，False 视为损失（同一 magnitude 下损失权重被 λ 放大）。
    """
    if not isinstance(desirable, bool):
        raise TypeError("desirable 必须为布尔（KTO 用的是二元信号）")
    if magnitude < 0:
        raise ValueError("magnitude 必须非负（方向由 desirable 决定）")
    return prospect_value(magnitude if desirable else -magnitude,
                          alpha=alpha, beta=beta, lam=lam)


def anchor_regression(baseline, candidate, tol=0.0):
    """锚定集回归判定。

    参数：baseline / candidate 均为 {anchor_id: score}
    返回：{"ok": bool, "worst_delta": float, "regressed": [anchor_id, ...]}
    规则：任一锚点分数下降超过 tol → ok=False（拒绝该候选）。

    用途：偏好信号最易出的失效是「越偏好越坍缩」；锚定集是防坍缩护栏。
    """
    missing = set(baseline) - set(candidate)
    if missing:
        return {"ok": False, "worst_delta": float("-inf"),
                "regressed": sorted(missing)}
    worst = float("inf")
    regressed = []
    for k, b in baseline.items():
        delta = candidate[k] - b
        worst = min(worst, delta)
        if delta < -tol:
            regressed.append(k)
    return {"ok": not regressed, "worst_delta": worst,
            "regressed": sorted(regressed)}


def select_by_desirability(candidates, baseline, tol=0.0):
    """在候选中择优：先过锚定回归门，再取可欲效用最大者。

    candidates: [{"name": str, "desirable": bool, "magnitude": float,
                  "anchor_scores": {anchor_id: score}}, ...]
    返回：{"chosen": name|None, "rejected": [{"name","regressed"}...],
           "reason": str}

    关键语义：**任何使锚定集回退超容差的候选一律出局**，无论其可欲效用多高。
    """
    rejected = []
    viable = []
    for c in candidates:
        name = c.get("name")
        if not isinstance(name, str) or not name:
            rejected.append({"name": None, "regressed": ["BAD_NAME"]})
            continue
        reg = anchor_regression(baseline, c.get("anchor_scores", {}), tol=tol)
        if not reg["ok"]:
            rejected.append({"name": name, "regressed": reg["regressed"]})
            continue
        utility = kto_weight(bool(c.get("desirable")),
                             float(c.get("magnitude", 1.0)))
        viable.append((utility, name))

    if not viable:
        return {"chosen": None, "rejected": rejected,
                "reason": "无候选通过锚定回归门"}

    # 效用降序；同效用按名字典序（确定性）
    viable.sort(key=lambda x: (-x[0], x[1]))
    return {"chosen": viable[0][1], "rejected": rejected,
            "reason": "锚定回归通过且可欲效用最大"}
