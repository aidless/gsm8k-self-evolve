"""SIA 式双杠杆选择器与交错循环（harness / weight）。

设计来源：arXiv:2605.27276 *SIA: Self Improving AI with Harness & Weight
Updates*。原文的 Feedback-Agent 看完整执行轨迹选动作，动作空间同时包含
harness 侧（scaffold / 提示 / 工具）与权重侧（LoRA 更新）。本模块把「选哪根
杠杆」从冻结的 LLM prior 改成可审计的确定性规则，并落实两条论文里的教训：

1. **冷启动先改 harness**：SIA 的 Best-of-N BC 冷启动只在 E[r]≈0 时出现，
   此时先把 scaffold 立起来；两域的 harness-only 最优甚至不是 LLM。
2. **两杠杆共用固定 verifier 的 Goodhart 风险**：作者自述的 Coupled
   co-evolutionary Goodhart 指出，verifier 一变，此前所有跨轮比较都不再同币种。
   因此 verifier_id 在 campaign 开始即冻结，evaluate 回报的身份不一致立即
   fail-closed 停机，不晋升、不继续迭代。

边界：本模块**不训练、不评测、不产出实验结论**。weight 侧只接受外部注入的
updater（有 .apply(payload) 即可）；本机没有训练通道时选择器 fail-closed 走
harness，绝不假装改过权重（AGENTS.md 第 17 条：实验上云，本机只做编排）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

LEVERS = ("harness", "weight")

ADAPTER_SHA_RE = re.compile(r"^[0-9a-f]{64}$")


def validate_weight_receipt(receipt: Any, verifier_id: str) -> tuple[dict[str, Any] | None, str | None]:
    """把 weight_updater.apply() 的返回值校验成可入证据链的回执。

    返回 (清洗后的回执, 停机原因)，两者恰有一个非 None。契约：
    - 必须是 mapping；
    - `adapter_sha256` 为 64 位小写十六进制（权重产物的身份）；
    - `steps` 为非负整数（含 bool 拒绝，bool 是 int 子类）；
    - `verifier_id` 必须与循环冻结的 verifier 一致，否则判身份漂移。
    """
    if not isinstance(receipt, Mapping):
        return None, "weight_receipt_invalid"
    sha = receipt.get("adapter_sha256")
    if not isinstance(sha, str) or not ADAPTER_SHA_RE.match(sha):
        return None, "weight_receipt_invalid"
    steps = receipt.get("steps")
    if isinstance(steps, bool) or not isinstance(steps, int) or steps < 0:
        return None, "weight_receipt_invalid"
    observed = receipt.get("verifier_id")
    if observed != verifier_id:
        return None, "weight_verifier_drift"
    cleaned: dict[str, Any] = {"adapter_sha256": sha, "verifier_id": observed, "steps": steps}
    # 可选审计字段：有就透传，缺了不影响契约
    for optional in ("adapter_path", "job_digest"):
        value = receipt.get(optional)
        if isinstance(value, str) and value:
            cleaned[optional] = value
    return cleaned, None


@dataclass(frozen=True)
class FailureProfile:
    """一轮轨迹诊断：scaffold/工具/格式类错误 vs 能力/推理类错误。"""

    harness_errors: int
    reasoning_errors: int

    @property
    def total(self) -> int:
        return self.harness_errors + self.reasoning_errors


@dataclass(frozen=True)
class LeverSignal:
    """每轮杠杆动作的观测：杠杆、相对上一轮的增益、当时冻结的 verifier 身份。"""

    lever: str
    delta: float
    verifier_id: str


@dataclass(frozen=True)
class LeverDecision:
    lever: str
    rule_id: str
    reason: str


def _last_lever(history: Sequence[LeverSignal]) -> str:
    return history[-1].lever if history else ""


def select_lever(history: Sequence[LeverSignal], profile: FailureProfile,
                 weight_available: bool = True) -> LeverDecision:
    """按诊断剖面选杠杆，规则优先级固定，判定可逐条复核。

    R0 冷启动（无历史且无错误信号）→ harness
    R1 scaffold 类错误占优 → harness
    R2 能力类错误占优 → weight
    R3 权重通道未接入 → harness（fail-closed，绝不空转）
    R4 平分秋色 → 与上一轮严格交错（无上一轮则 harness）
    """
    if profile.harness_errors < 0 or profile.reasoning_errors < 0:
        raise ValueError("failure counts must be non-negative")
    for signal in history:
        if signal.lever not in LEVERS:
            raise ValueError(f"unknown lever: {signal.lever!r}")
    if not history and profile.total == 0:
        return LeverDecision("harness", "R0_cold_start",
                             "no history and no failure signal: build scaffold first")
    if profile.harness_errors > profile.reasoning_errors:
        return LeverDecision("harness", "R1_scaffold_bottleneck",
                             "scaffold/tool/format errors dominate")
    if profile.reasoning_errors > profile.harness_errors:
        if not weight_available:
            return LeverDecision("harness", "R3_weight_unprovisioned",
                                 "capability bottleneck but no weight updater injected")
        return LeverDecision("weight", "R2_capability_bottleneck",
                             "reasoning errors dominate: update weights")
    previous = _last_lever(history)
    chosen = "weight" if previous == "harness" else "harness"
    if chosen == "weight" and not weight_available:
        return LeverDecision("harness", "R3_weight_unprovisioned",
                             "interleave would pick weight, but updater is absent")
    return LeverDecision(chosen, "R4_interleave_tie",
                         "balanced profile: alternate levers")


def interleaved_plan(rounds: int, weight_available: bool = True,
                     verifier_id: str = "v-plan") -> list[LeverDecision]:
    """生成交错轮次计划（无外部副作用）。用于预注册与排期，不是实测结果。

    默认剖面恒为 (0,0)：首轮 R0 冷启动，此后 R4 平分秋色严格交错。
    """
    if rounds < 0:
        raise ValueError("rounds must be non-negative")
    history: list[LeverSignal] = []
    decisions: list[LeverDecision] = []
    for _ in range(rounds):
        decision = select_lever(history, FailureProfile(0, 0), weight_available)
        decisions.append(decision)
        history.append(LeverSignal(decision.lever, 0.0, verifier_id))
    return decisions


def run_interleaved_loop(*,
                         rounds: int,
                         diagnose: Callable[[int], FailureProfile],
                         propose_harness: Callable[[int], Any],
                         propose_weight: Callable[[int], Any],
                         evaluate: Callable[[Any, int], dict[str, Any]],
                         verifier_id: str,
                         weight_updater: Any = None,
                         min_gain: float = 0.02,
                         baseline_score: float = 0.0,
                         rollback: Callable[[str, Any, int], None] | None = None,
                         ) -> dict[str, Any]:
    """双杠杆交错循环骨架：诊断 → 选杠杆 → 应用 → 评测 → 接受/回滚。

    - 每轮只动一根杠杆（选择器结构性保证）；
    - verifier_id 全程冻结，evaluate 回报的身份不一致立即停机（fail-closed）；
    - 增益 < min_gain 判不晋升，调用可选 rollback 钩子恢复该杠杆；
    - weight_updater 为 None 时，选择器永不选 weight（R3），本机零训练。
    返回的 report 每轮带 rule_id / delta / accepted / rollback，可直接入证据链。
    """
    history: list[LeverSignal] = []
    records: list[dict[str, Any]] = []
    current_score = float(baseline_score)
    stopped_reason: str | None = None
    weight_available = weight_updater is not None

    for round_i in range(max(rounds, 0)):
        profile = diagnose(round_i)
        decision = select_lever(history, profile, weight_available)
        weight_receipt: dict[str, Any] | None = None
        if decision.lever == "harness":
            candidate = propose_harness(round_i)
        else:
            candidate = propose_weight(round_i)
            raw_receipt = weight_updater.apply(candidate)
            weight_receipt, invalid_reason = validate_weight_receipt(raw_receipt, verifier_id)
            if invalid_reason is not None:
                # 拿不到合契约的回执 = 这次权重改动无法进证据链 → 一句都不接受
                records.append({
                    "round": round_i, "lever": decision.lever, "rule_id": decision.rule_id,
                    "reason": decision.reason, "delta": None, "score": None,
                    "accepted": False, "rollback": True,
                    "observed_verifier": (raw_receipt.get("verifier_id")
                                          if isinstance(raw_receipt, Mapping) else None),
                    "expected_verifier": verifier_id, "weight_receipt": None,
                })
                stopped_reason = invalid_reason
                break
        measurement = evaluate(candidate, round_i) or {}
        observed_verifier = measurement.get("verifier_id")
        if observed_verifier != verifier_id:
            records.append({
                "round": round_i, "lever": decision.lever, "rule_id": decision.rule_id,
                "reason": decision.reason, "delta": None, "score": None,
                "accepted": False, "rollback": True,
                "observed_verifier": observed_verifier, "expected_verifier": verifier_id,
                "weight_receipt": weight_receipt,
            })
            stopped_reason = "verifier_drift"
            break
        score = float(measurement.get("score", 0.0))
        delta = score - current_score
        accepted = delta >= min_gain
        rolled_back = not accepted
        if rolled_back and rollback is not None:
            rollback(decision.lever, candidate, round_i)
        if accepted:
            current_score = score
        records.append({
            "round": round_i, "lever": decision.lever, "rule_id": decision.rule_id,
            "reason": decision.reason, "delta": delta, "score": score,
            "accepted": accepted, "rollback": rolled_back,
            "observed_verifier": observed_verifier, "expected_verifier": verifier_id,
            "weight_receipt": weight_receipt,
        })
        history.append(LeverSignal(decision.lever, delta, verifier_id))

    return {
        "rounds": records,
        "stopped_reason": stopped_reason,
        "accepted": [r["round"] for r in records if r["accepted"]],
        "final_score": current_score,
        "verifier_id": verifier_id,
    }
