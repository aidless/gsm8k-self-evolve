"""把一个 QLoRA adapter 目录变成可审计的权重回执（不训、不评、只读字节）。

与 `weight_updater.SubprocessWeightUpdater` 的分工：
- 那边负责**跑**一条训练命令，再从产物算哈希；
- 这边负责**判**盘上已有产物算不算一次真训练，产出与
  `lever_selector.validate_weight_receipt` 同契约的回执。

三条停机线（缺一条就白跑）：
1. `adapter_model.safetensors` 缺失 → 没有产物；
2. `trainer_state.json` 缺失 → 步数未知（未知不等于零步）；
3. 全部 `lora_B` 张量恒为零 → adapter 还是初始化的，一步没走。

第 3 条是这次真机跑通的直接教训：LoRA 的 `lora_A` 用 Kaiming 初始化、
`lora_B` 初始化为全零，所以"训练前"和"训练后"在文件大小上完全一样，
只有看 `lora_B` 是否离零才能分辨。仅凭 sha256 变化判"训过了"是不成立的，
因为任何重新保存都会换哈希。
"""
from __future__ import annotations

import json
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from evokit.weight_updater import sha256_file

WEIGHTS_NAME = "adapter_model.safetensors"
CONFIG_NAME = "adapter_config.json"
TRAINER_STATE_NAME = "trainer_state.json"
ZERO_EPS = 1e-12


class AdapterArtifactError(RuntimeError):
    """产物不可入证据链；消息即停机原因（前缀是机器可读的判据名）。"""


def _read_safetensors_header(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        head = handle.read(8)
        if len(head) != 8:
            raise AdapterArtifactError("missing: truncated safetensors header")
        n = struct.unpack("<Q", head)[0]
        raw = handle.read(n)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AdapterArtifactError(f"missing: corrupt safetensors header: {exc}") from exc


def _tensor_bytes(entry: Mapping[str, Any]) -> int:
    start, end = entry["data_offsets"]
    return int(end) - int(start)


def _lora_b_tensors(header: Mapping[str, Any]) -> list[str]:
    return [k for k in header if k != "__metadata__" and "lora_B" in k]


def _all_zero(path: Path, header: Mapping[str, Any], names: list[str]) -> bool:
    """只解包 lora_B 的字节块，不走 torch（这条检查要能在无 GPU 机器上跑）。"""
    offsets = [(header[n]["data_offsets"][0], header[n]["data_offsets"][1]) for n in names]
    with path.open("rb") as handle:
        head = handle.read(8)
        n = struct.unpack("<Q", head)[0]
        base = 8 + n
        for start, end in offsets:
            handle.seek(base + start)
            chunk = handle.read(end - start)
            if not chunk:
                raise AdapterArtifactError("missing: empty lora_B tensor block")
            if any(byte != 0 for byte in chunk):
                return False
    return True


def _resolve_steps(root: Path, state: Path) -> tuple[int, str]:
    """定位步数：顶层 trainer_state.json 优先，否则回落唯一 checkpoint。

    `save_total_limit=1` 的真实产物里，`trainer_state.json` 只在
    `checkpoint-N/` 下（顶层那份被 save_pretrained 覆盖掉了）。找不到就判
    `steps_unknown`；找到多份且互相矛盾判 `steps_ambiguous`——未知步数不是 0 步，
    两份不同步数也不能挑一个顺眼的用。
    """
    candidates: list[Path] = []
    if state.is_file():
        candidates.append(state)
    else:
        candidates.extend(sorted(root.glob("checkpoint-*/trainer_state.json")))
    if not candidates:
        raise AdapterArtifactError(
            "steps_unknown: no trainer_state.json at adapter root or in any checkpoint")

    seen: list[int] = []
    for path in candidates:
        payload = json.loads(path.read_text(encoding="utf-8"))
        value = payload.get("global_step")
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise AdapterArtifactError(f"steps_unknown: global_step={value!r} in {path.name}")
        seen.append(value)
    if len(set(seen)) > 1:
        raise AdapterArtifactError(
            f"steps_ambiguous: checkpoints disagree on global_step {sorted(set(seen))}")
    return seen[0], str(candidates[0])


def _shareable(path: Path, root: Path | None) -> str:
    """转成可分享的相对路径；root 给定且 path 在其下时才转，否则保持绝对。"""
    if root is not None:
        try:
            return str(path.resolve().relative_to(Path(root).resolve()))
        except ValueError:
            pass
    return str(path)


@dataclass
class AdapterArtifactUpdater:
    """把已存在的 adapter 目录折成回执；接口与 `SubprocessWeightUpdater.apply` 一致。"""

    adapter_dir: Path
    verifier_id: str
    expected_base_model: str | None = None
    workspace_root: Path | None = None
    extra: dict[str, Any] = field(default_factory=dict)
    calls: list[dict[str, Any]] = field(default_factory=list)

    def apply(self, candidate: Mapping[str, Any]) -> dict[str, Any]:
        root = Path(self.adapter_dir)
        weights = root / WEIGHTS_NAME
        config = root / CONFIG_NAME
        state = root / TRAINER_STATE_NAME

        if not weights.is_file():
            raise AdapterArtifactError(f"missing: adapter weights absent: {weights}")
        if not config.is_file():
            raise AdapterArtifactError(f"missing: adapter config absent: {config}")
        steps, steps_source = _resolve_steps(root, state)

        cfg = json.loads(config.read_text(encoding="utf-8"))
        base = cfg.get("base_model_name_or_path")
        if self.expected_base_model is not None and base != self.expected_base_model:
            raise AdapterArtifactError(
                f"base_model_mismatch: adapter trained on {base!r}, expected {self.expected_base_model!r}")

        header = _read_safetensors_header(weights)
        b_names = _lora_b_tensors(header)
        if not b_names:
            raise AdapterArtifactError("untrained: no lora_B tensors in adapter")
        if _all_zero(weights, header, b_names):
            raise AdapterArtifactError(
                "untrained: all lora_B tensors are zero (fresh init, zero optimizer steps)")

        # 回执进证据链时要可分享：adapter_path 记相对路径（cwd 无关的锚点）。
        # workspace_root=None 时才落绝对路径（本地调试用，不进账本）。
        shown = _shareable(weights, self.workspace_root)
        shown_steps = _shareable(Path(steps_source), self.workspace_root)
        receipt = {
            "adapter_sha256": sha256_file(weights),
            "verifier_id": self.verifier_id,
            "steps": steps,
            "steps_source": shown_steps,
            "adapter_path": shown,
            "base_model": base,
            "lora_r": cfg.get("r"),
            "lora_b_nonzero": len(b_names),
            "bytes": weights.stat().st_size,
            **self.extra,
        }
        self.calls.append({"candidate": dict(candidate), "receipt": dict(receipt)})
        return receipt
