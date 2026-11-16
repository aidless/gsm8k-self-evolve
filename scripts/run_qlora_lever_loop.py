"""用盘上真实 QLoRA-4B adapter 驱动双杠杆循环，落一份可审计证据。

与 `tiny_weight_step.py` 的区别：那边是一个 2 参数的玩具 SGD，只能证明
"命令→产物→哈希→回执"这条线是通的；这里喂进去的是 **Qwen3-4B 上真跑过的
adapter**（264,308,896 字节，252 个 lora_B 张量全非零，trainer_state
global_step=25），证明权重杠杆能被真实训练产物驱动。

口径（2026-11-16 实测纠正）：该 adapter 由 `paper_agent/train/train_agent.py`
做 **SFT 续训**产出（`train_p2.log` 首行 `[resume] SFT adapter attached`，
`cfg_snapshot.json` mode=p1），**不是 DPO** —— `train_dpo.py --p2` 在 6GB 卡上
OOM 从未成功（见 `paper_agent/reports/train_dpo_smoke.log`）。

边界（AGENTS.md 第 1/2 条，也写进输出的 evidence 块）：
- 本脚本**不训练**，只读盘上产物；训练是 2026-09-10 在 6GB 卡上跑完的（train_p2.log）。
- evaluate 的分数是**注入的合成序列**，不是 GSM8K 指标，不能当能力结论引用。
- 结论边界：通道/契约成立 ≠ 模型变强。

用法：python3 scripts/run_qlora_lever_loop.py [--out results/xxx.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evokit.adapter_receipt import AdapterArtifactUpdater
from evokit.lever_selector import FailureProfile, run_interleaved_loop

WORKSPACE = ROOT.parent
ADAPTER = WORKSPACE / "paper_agent" / "outputs" / "tmlr-qwen3-4b-p2"
VERIFIER = "verifier-frozen-v1"

# 合成评测序列（harness 轮 / weight 轮交替的分数）。不当能力结论。
SCORES = {0: 0.86, 1: 0.93}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "results" / "qlora-lever-loop-2026-11-16.json"))
    args = ap.parse_args()

    updater = AdapterArtifactUpdater(adapter_dir=ADAPTER, verifier_id=VERIFIER,
                                     expected_base_model="Qwen/Qwen3-4B",
                                     workspace_root=WORKSPACE)

    def diagnose(round_i: int) -> FailureProfile:
        # R0 冷启动 → harness；R1 推理瓶颈占优 → weight。固定序列，可复算。
        if round_i == 0:
            return FailureProfile(harness_errors=10, reasoning_errors=0)
        return FailureProfile(harness_errors=0, reasoning_errors=10)

    def propose_harness(round_i: int) -> dict:
        return {"lever": "harness", "round": round_i, "patch": "scaffold:add_retry_guard"}

    def propose_weight(round_i: int) -> dict:
        return {"lever": "weight", "round": round_i, "adapter": "tmlr-qwen3-4b-p2"}

    def evaluate(candidate, round_i: int) -> dict:
        return {"verifier_id": VERIFIER, "score": SCORES[round_i]}

    report = run_interleaved_loop(
        rounds=2, diagnose=diagnose, propose_harness=propose_harness,
        propose_weight=propose_weight, evaluate=evaluate, verifier_id=VERIFIER,
        weight_updater=updater, min_gain=0.02, baseline_score=0.80,
    )
    payload = {
        "evidence": {
            "what_this_is": "weight lever driven by a real Qwen3-4B QLoRA SFT-continuation adapter on disk",
            "adapter_dir": str(ADAPTER.relative_to(WORKSPACE)),
            "training_log": "paper_agent/reports/train_p2.log",
            "training_script": "paper_agent/train/train_agent.py (SFT continuation, not DPO)",
            "training_ran_at": "2026-09-10T21:26:33-07:00 .. 21:34:18-07:00",
            "training_wall_clock_s": 448.8,
            "training_hardware": "NVIDIA GeForce RTX 3060 Laptop GPU 6144MiB (max_memory 4600MiB + CPU offload)",
            "optimizer_steps": 25,
            "pairs": 400,
            "train_file_sha256": "a0e41f5bb07bb5086cf0668002eefc97095caad5afe93dc0bcf275529d5e13e8",
            "not_claimed": [
                "no GSM8K/TMLR metric improvement is claimed",
                "this adapter is an SFT continuation, not a DPO product",
                "evaluate() scores are injected synthetic values, not model outputs",
                "this script does not train anything",
            ],
        },
        "loop": report,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "stopped_reason": report["stopped_reason"],
        "accepted": report["accepted"],
        "final_score": report["final_score"],
        "rounds": [{k: r[k] for k in ("round", "lever", "rule_id", "delta", "accepted")}
                   for r in report["rounds"]],
        "weight_receipt_steps": report["rounds"][1]["weight_receipt"]["steps"],
        "weight_receipt_sha16": report["rounds"][1]["weight_receipt"]["adapter_sha256"][:16],
        "out": str(out),
    }, indent=2, ensure_ascii=False))
    return 0 if report["stopped_reason"] is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
