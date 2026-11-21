"""用真 DPO p2 adapter（AMD Radeon Cloud 云端训练产物）驱动双杠杆闭环。

与 `run_qlora_lever_loop.py` 的区别：那边是本地 6GB 卡 SFT 续训 adapter
（sha f04022a9…，非 DPO）；这里喂的是 2026-11-21 在 AMD Radeon Cloud 上
用 `train_dpo.py --p2` + `dpo_p0v2.jsonl` 真跑的 50-step DPO adapter
（sha b9ef9253…，264308896B，252 个 lora_B 张量非零）。

verifier: 本地 AdapterArtifactUpdater 只读产物算回执 → validate_weight_receipt
过契约 → 与云端 remote_receipt.py 算出的 p2_receipt.json 逐字段对表。

边界（写进 evidence.not_claimed）：本脚本不训练、evaluate 分数是合成序列
不是 GSM8K 指标；通道成立 ≠ 模型变强。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evokit.adapter_receipt import AdapterArtifactUpdater
from evokit.lever_selector import FailureProfile, run_interleaved_loop, validate_weight_receipt

WORKSPACE = ROOT.parent
ADAPTER = ROOT / "results" / "qlora-cloud-2026-11-21" / "p2"
CLOUD_RECEIPT = ROOT / "results" / "qlora-cloud-2026-11-21" / "p2_receipt.json"
VERIFIER = "verifier-frozen-v1"
EXPECTED_SHA = "b9ef9253093034bab7e0cff0c72fa05dcdda6ab879fa4e3505c0927270bcc6a9"
SCORES = {0: 0.86, 1: 0.93}
CROSSCHECK_FIELDS = ("adapter_sha256", "verifier_id", "steps", "base_model", "lora_r", "bytes")


def build_report() -> dict:
    updater = AdapterArtifactUpdater(
        adapter_dir=ADAPTER, verifier_id=VERIFIER,
        expected_base_model="Qwen/Qwen3-4B", workspace_root=WORKSPACE,
    )

    def diagnose(round_i: int) -> FailureProfile:
        if round_i == 0:
            return FailureProfile(harness_errors=10, reasoning_errors=0)
        return FailureProfile(harness_errors=0, reasoning_errors=10)

    def propose_harness(round_i: int) -> dict:
        return {"lever": "harness", "round": round_i, "patch": "scaffold:add_retry_guard"}

    def propose_weight(round_i: int) -> dict:
        return {"lever": "weight", "round": round_i, "adapter": "qlora-cloud-p2-dpo"}

    def evaluate(candidate, round_i: int) -> dict:
        return {"verifier_id": VERIFIER, "score": SCORES[round_i]}

    report = run_interleaved_loop(
        rounds=2, diagnose=diagnose, propose_harness=propose_harness,
        propose_weight=propose_weight, evaluate=evaluate, verifier_id=VERIFIER,
        weight_updater=updater, min_gain=0.02, baseline_score=0.80,
    )

    weight_receipt = report["rounds"][1]["weight_receipt"]
    cleaned, reason = validate_weight_receipt(weight_receipt, VERIFIER)
    # 对表用 updater 的原始回执（与云端 remote_receipt 同一层）：
    # validate 后的回执故意只留 3 个契约字段，base_model/lora_r/bytes 已被剥离。
    raw_receipt = updater.calls[0]["receipt"]
    cloud = json.loads(CLOUD_RECEIPT.read_text(encoding="utf-8"))
    crosscheck = {
        field: {
            "local": raw_receipt.get(field),
            "cloud": cloud.get(field),
            "match": raw_receipt.get(field) == cloud.get(field),
        }
        for field in CROSSCHECK_FIELDS
    }

    return {
        "evidence": {
            "what_this_is": "weight lever driven by a real Qwen3-4B DPO adapter trained on AMD Radeon Cloud",
            "adapter_dir": str(ADAPTER.relative_to(ROOT)),
            "training_script": "train_dpo.py --p2 (chosen/rejected pairs, not SFT)",
            "training_hardware": "AMD Radeon Graphics gfx1100 48GiB bf16 (no_4bit, bf16 LoRA)",
            "optimizer_steps": cloud["steps"],
            "train_file_sha256": "520be7f85d599668b415a221fa4f3b80342129c6d93e8cc7c3fc99d50677c28f",
            "adapter_sha256": cloud["adapter_sha256"],
            "not_claimed": [
                "no GSM8K/TMLR metric improvement is claimed",
                "evaluate() scores are injected synthetic values, not model outputs",
                "this script does not train anything; it only reads the adapter on disk",
            ],
        },
        "loop": report,
        "receipt_validation": {"reason": reason, "valid": cleaned is not None},
        "receipt_crosscheck_local_vs_cloud": crosscheck,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "results" / "dpo-lever-loop-2026-11-21.json"))
    args = ap.parse_args()
    payload = build_report()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    loop = payload["loop"]
    print(json.dumps({
        "stopped_reason": loop["stopped_reason"],
        "accepted": loop["accepted"],
        "final_score": loop["final_score"],
        "levers": [r["lever"] for r in loop["rounds"]],
        "weight_receipt_sha16": loop["rounds"][1]["weight_receipt"]["adapter_sha256"][:16],
        "receipt_reason": payload["receipt_validation"]["reason"],
        "crosscheck_all_match": all(p["match"] for p in payload["receipt_crosscheck_local_vs_cloud"].values()),
        "out": str(out),
    }, indent=2, ensure_ascii=False))
    return 0 if loop["stopped_reason"] is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
