"""双杠杆闭环，evaluate 换真实 ground-truth objective（不再是注入的 0.86/0.93）。

旧 `run_dpo_lever_loop.py` 的 evaluate 直接返回合成序列 0.86/0.93，验的是
"回执契约 + 交错骨架"能不能通，score 是假的。本脚本把 evaluate 换成
**盘上 ability-B 的真实读数**：两轮生成 `generations_{sft,dpo}.json` 由
`parser_sensitivity.py` 在同一 heldout 上按 PREREG 口径（last_int）重判，
权重轮的分数就是"真 DPO adapter 在真 heldout 上的真准确率"。

口径边界（这条不许省，L-ops-897）：
  PREREG 锁死 last_int，读数 delta +0.1333 GAIN；但换成显式答案口径是 −0.1667
  REGRESSION，symbol_consistency=UNSTABLE。本脚本按 PREREG 口径给出分数，
  同时把 UNSTABLE 边界写进 evidence.not_claimed——禁止拿 GAIN 宣称能力提升。

verifier: 本地 updater 只读 ability-B 的 adapter（目录只有 safetensors，无
trainer_state，故不能用 AdapterArtifactUpdater）→ 直接对 receipt 契约校验 →
与 dpo_receipt.json 逐字段对表（adapter_sha256 逐字节复算）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evokit.lever_selector import FailureProfile, run_interleaved_loop, validate_weight_receipt  # noqa: E402
from evokit.weight_updater import sha256_file  # noqa: E402

RESULTS = ROOT / "results" / "qlora-ability-b"
ADAPTER = RESULTS / "adapter" / "adapter_model.safetensors"
RECEIPT = RESULTS / "dpo_receipt.json"
PARSER_SENSITIVITY = RESULTS / "parser_sensitivity.json"
VERIFIER = "verifier-frozen-v1"
CROSSCHECK_FIELDS = ("adapter_sha256", "verifier_id", "steps", "base_model", "lora_r", "bytes")


class _AbilityWeightUpdater:
    """只读 ability-B adapter 的合约回执 updater（不训练、不评、只读字节）。

    ability-B 的 adapter 目录只有 safetensors，没有 trainer_state.json/config，
    所以复用不了 AdapterArtifactUpdater（它会因缺 trainer_state fail-closed）。
    这里直接对磁盘 receipt 做契约校验，并把 adapter_sha256 与盘上字节复算。
    """

    def __init__(self, receipt_path: Path, adapter_path: Path, verifier_id: str):
        self._receipt_path = receipt_path
        self._adapter_path = adapter_path
        self._verifier_id = verifier_id
        self.calls: list[dict[str, Any]] = []

    def apply(self, candidate: Any) -> Any:
        receipt = json.loads(self._receipt_path.read_text(encoding="utf-8"))
        if not isinstance(receipt, dict):
            # 读不出回执 = 没有可入证据链的产物 → 返回非 mapping，契约必判 invalid
            return None
        disk_sha = sha256_file(self._adapter_path)
        if disk_sha != receipt.get("adapter_sha256"):
            # 产物身份与回执不符 = 这次权重改动不可入证据链 → 返回非 mapping（fail-closed）。
            # 注意：绝不能返回一个"格式合法的假 sha"——那会让 validate_weight_receipt 放行，
            # 闸就成了装饰（本测试 test_sha_mismatch_on_disk_fails_closed 抓的就是这个）。
            self.calls.append({"candidate": candidate, "receipt": None,
                               "disk_sha": disk_sha,
                               "error": "adapter_sha_mismatch_on_disk"})
            return None
        cleaned = dict(receipt)
        self.calls.append({"candidate": candidate, "receipt": cleaned, "disk_sha": disk_sha})
        return cleaned


def _read_prereg_accuracy() -> dict:
    """PREREG 口径（last_int）的 base/adapter 真实准确率（从 parser_sensitivity.json 读）。"""
    sens = json.loads(PARSER_SENSITIVITY.read_text(encoding="utf-8"))
    prereg = sens["per_parser"]["last_int"]
    return {
        "base": prereg["sft_accuracy"],
        "adapter": prereg["dpo_accuracy"],
        "base_passed": prereg["sft_passed"],
        "adapter_passed": prereg["dpo_passed"],
        "total": prereg["total"],
        "delta": prereg["delta"],
        "symbol_consistency": sens.get("symbol_consistency"),
    }


def build_report(min_gain: float = 0.05, baseline_score: float = 0.0) -> dict:
    """跑双杠杆闭环：轮0 harness（基线分），轮1 weight（真实 ground-truth 分）。

    分数来源：ability-B 的 heldout（60 题，seed 区间与训练不重叠），
    两轮 generations 按 PREREG last_int 口径重判。轮1 的 delta 就是
    "真 DPO adapter vs SFT 基线"的 accuracy 差。
    """
    updater = _AbilityWeightUpdater(RECEIPT, ADAPTER, VERIFIER)
    prereg = _read_prereg_accuracy()

    def diagnose(round_i: int) -> FailureProfile:
        if round_i == 0:
            return FailureProfile(harness_errors=10, reasoning_errors=0)
        return FailureProfile(harness_errors=0, reasoning_errors=10)

    def propose_harness(round_i: int) -> dict:
        return {"lever": "harness", "round": round_i, "patch": "scaffold:add_retry_guard"}

    def propose_weight(round_i: int) -> dict:
        return {"lever": "weight", "round": round_i, "adapter": "qlora-ability-b-dpo"}

    def evaluate(candidate: Any, round_i: int) -> dict:
        # 轮0 = harness 轮，score 取真实 base 准确率；轮1 = weight 轮，取真实 adapter 准确率
        score = prereg["base"] if round_i == 0 else prereg["adapter"]
        return {"verifier_id": VERIFIER, "score": score, "round": round_i}

    report = run_interleaved_loop(
        rounds=2, diagnose=diagnose, propose_harness=propose_harness,
        propose_weight=propose_weight, evaluate=evaluate, verifier_id=VERIFIER,
        weight_updater=updater, min_gain=min_gain, baseline_score=baseline_score,
    )

    weight_receipt = report["rounds"][1]["weight_receipt"]
    cleaned, reason = validate_weight_receipt(weight_receipt, VERIFIER)
    raw_receipt = updater.calls[0]["receipt"] if updater.calls else {}
    disk_receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    crosscheck = {
        field: {
            "local": raw_receipt.get(field),
            "disk": disk_receipt.get(field),
            "match": raw_receipt.get(field) == disk_receipt.get(field),
        }
        for field in CROSSCHECK_FIELDS
    }

    return {
        "evidence": {
            "what_this_is": "weight lever driven by real ability-B DPO adapter; evaluate uses real ground-truth accuracy, not injected scores",
            "adapter_dir": str(RESULTS.relative_to(ROOT)),
            "training_script": "train_dpo.py --p2 on synthetic (A*B+C) mod M task",
            "training_hardware": "AMD Radeon Cloud gfx1100 48GiB bf16 (no_4bit)",
            "optimizer_steps": disk_receipt["steps"],
            "adapter_sha256": disk_receipt["adapter_sha256"],
            "objective_source": "parser_sensitivity.json last_int on ability-B heldout (60 questions, disjoint seed range)",
            "prereg_accuracy": prereg,
            "not_claimed": [
                "this script does not train anything; it only reads the adapter on disk and re-judges stored generations",
                "no capability improvement is claimed: the PREREG last_int +0.1333 GAIN is an artifact of output-shape convergence (SFT continues steps after Answer:, DPO does not); explicit-answer parsers give -0.1667 REGRESSION",
                "symbol_consistency is UNSTABLE across parsers; a single-parser GAIN must not be reported as capability",
            ],
        },
        "loop": report,
        "receipt_validation": {"reason": reason, "valid": cleaned is not None},
        "receipt_crosscheck_local_vs_disk": crosscheck,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "results" / "ability-lever-loop-2026-11-22.json"))
    ap.add_argument("--min-gain", type=float, default=0.05)
    ap.add_argument("--baseline", type=float, default=0.0)
    args = ap.parse_args()
    payload = build_report(min_gain=args.min_gain, baseline_score=args.baseline)
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
        "crosscheck_all_match": all(p["match"] for p in payload["receipt_crosscheck_local_vs_disk"].values()),
        "prereg_delta": payload["evidence"]["prereg_accuracy"]["delta"],
        "symbol_consistency": payload["evidence"]["prereg_accuracy"]["symbol_consistency"],
        "out": str(out),
    }, indent=2, ensure_ascii=False))
    return 0 if loop["stopped_reason"] is None else 1


if __name__ == "__main__":
    raise SystemExit(main())