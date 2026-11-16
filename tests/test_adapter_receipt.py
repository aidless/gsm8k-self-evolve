"""权重杠杆接真实 QLoRA 训练产物：adapter 目录 → 可审计回执。

为什么需要这一层：`weight_updater.py` 的 `SubprocessWeightUpdater` 能跑
一条命令并算产物哈希，但**"盘上这个 adapter 是不是真训过的"** 它不问。
如果拿一个刚初始化的 adapter（lora_B 全零）或一个基座对不上的 adapter
进账本，通道看起来通了，证据其实是空的。本文件的断言全部针对这个缺口。

契约（与 `validate_weight_receipt` 一致，供 `run_interleaved_loop` 消费）：
- adapter_sha256 = 本地实算 adapter_model.safetensors 的 sha256
- steps = trainer_state.json 的 global_step（没有这份文件就是未知步数，必须停）
- verifier_id 由调用方冻结
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evokit.adapter_receipt import AdapterArtifactUpdater, AdapterArtifactError
from evokit.lever_selector import validate_weight_receipt
from evokit.weight_updater import sha256_file

VERIFIER = "verifier-frozen-v1"
BASE = "Qwen/Qwen3-4B"


def _write_safetensors(path: Path, tensors: dict[str, tuple[tuple[int, ...], list[float]]]) -> None:
    """写一个最小的合法 safetensors（F32，够测试读 header 与取值）。"""
    header: dict[str, dict] = {"__metadata__": {"format": "pt"}}
    payload = bytearray()
    for name, (shape, values) in tensors.items():
        n = 1
        for d in shape:
            n *= d
        assert len(values) == n, (name, shape, len(values))
        header[name] = {"dtype": "F32", "shape": list(shape),
                        "data_offsets": [len(payload), len(payload) + 4 * n]}
        payload += struct.pack("<" + "f" * n, *values)
    raw = json.dumps(header).encode("utf-8")
    with path.open("wb") as f:
        f.write(struct.pack("<Q", len(raw)))
        f.write(raw)
        f.write(bytes(payload))


def _make_adapter(root: Path, *, base: str = BASE, r: int = 4,
                  b_values: list[float] | None = None,
                  global_step: int | None = 25) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "adapter_config.json").write_text(json.dumps({
        "peft_type": "LORA", "base_model_name_or_path": base,
        "r": r, "lora_alpha": 16,
        "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj",
                           "gate_proj", "up_proj", "down_proj"],
    }), encoding="utf-8")
    width = 8
    values = b_values if b_values is not None else [0.01] * (width * r)
    _write_safetensors(root / "adapter_model.safetensors", {
        "base_model.model.model.layers.0.mlp.down_proj.lora_A.weight": ((r, width), [0.02] * (r * width)),
        "base_model.model.model.layers.0.mlp.down_proj.lora_B.weight": ((width, r), values),
    })
    if global_step is not None:
        (root / "trainer_state.json").write_text(json.dumps({
            "global_step": global_step, "max_steps": global_step,
            "best_metric": 0.4894774556159973,
        }), encoding="utf-8")
    return root


# ---- 会放行的：真产物 ----

def test_trained_adapter_yields_valid_receipt(tmp_path: Path) -> None:
    root = _make_adapter(tmp_path / "adapter")
    receipt = AdapterArtifactUpdater(adapter_dir=root, verifier_id=VERIFIER).apply({"k": "v"})
    cleaned, reason = validate_weight_receipt(receipt, VERIFIER)
    assert reason is None, reason
    assert cleaned["steps"] == 25
    assert cleaned["adapter_sha256"] == sha256_file(root / "adapter_model.safetensors")
    assert cleaned["verifier_id"] == VERIFIER
    assert cleaned["adapter_path"].endswith("adapter_model.safetensors")


def test_receipt_records_base_model_and_lora_rank(tmp_path: Path) -> None:
    """回执要能自证"这是哪个基座、多宽的 adapter"，否则跨基座对表无从谈起。"""
    root = _make_adapter(tmp_path / "adapter", base=BASE, r=32)
    receipt = AdapterArtifactUpdater(adapter_dir=root, verifier_id=VERIFIER).apply({})
    assert receipt["base_model"] == BASE
    assert receipt["lora_r"] == 32


# ---- 必须停机的五种情形 ----

def test_lora_b_all_zero_is_rejected(tmp_path: Path) -> None:
    """lora_B 全零 = 刚初始化的 adapter，DPO 一步没走：这条回执不能进账本。"""
    root = _make_adapter(tmp_path / "adapter", b_values=[0.0] * 32)
    with pytest.raises(AdapterArtifactError) as ei:
        AdapterArtifactUpdater(adapter_dir=root, verifier_id=VERIFIER).apply({})
    assert "untrained" in str(ei.value)


def test_missing_weights_is_rejected(tmp_path: Path) -> None:
    root = _make_adapter(tmp_path / "adapter")
    (root / "adapter_model.safetensors").unlink()
    with pytest.raises(AdapterArtifactError) as ei:
        AdapterArtifactUpdater(adapter_dir=root, verifier_id=VERIFIER).apply({})
    assert "missing" in str(ei.value)


def test_missing_trainer_state_is_rejected(tmp_path: Path) -> None:
    """没有 trainer_state.json 就不知道走了几步 —— 未知步数不是 0 步。"""
    root = _make_adapter(tmp_path / "adapter", global_step=None)
    with pytest.raises(AdapterArtifactError) as ei:
        AdapterArtifactUpdater(adapter_dir=root, verifier_id=VERIFIER).apply({})
    assert "steps_unknown" in str(ei.value)


def test_base_model_mismatch_is_rejected(tmp_path: Path) -> None:
    root = _make_adapter(tmp_path / "adapter", base="Qwen/Qwen3-8B")
    with pytest.raises(AdapterArtifactError) as ei:
        AdapterArtifactUpdater(adapter_dir=root, verifier_id=VERIFIER,
                               expected_base_model=BASE).apply({})
    assert "base_model_mismatch" in str(ei.value)


def test_missing_adapter_config_is_rejected(tmp_path: Path) -> None:
    root = _make_adapter(tmp_path / "adapter")
    (root / "adapter_config.json").unlink()
    with pytest.raises(AdapterArtifactError) as ei:
        AdapterArtifactUpdater(adapter_dir=root, verifier_id=VERIFIER).apply({})
    assert "missing" in str(ei.value)



def test_trainer_state_found_in_single_checkpoint(tmp_path: Path) -> None:
    """真产物形态：save_total_limit=1 时 trainer_state.json 只在 checkpoint-N/ 里。

    adapters 顶层没有该文件不等于步数未知——回落到唯一 checkpoint 是合法的。
    """
    root = _make_adapter(tmp_path / "adapter", global_step=None)
    ck = root / "checkpoint-25"
    ck.mkdir()
    (ck / "trainer_state.json").write_text(json.dumps(
        {"global_step": 25, "max_steps": 25}), encoding="utf-8")
    receipt = AdapterArtifactUpdater(adapter_dir=root, verifier_id=VERIFIER).apply({})
    assert receipt["steps"] == 25
    assert receipt["steps_source"].endswith("checkpoint-25/trainer_state.json")


def test_conflicting_checkpoint_steps_is_rejected(tmp_path: Path) -> None:
    """两个 checkpoint 报不同步数 → 取哪个都无法自证，停机而不是随便挑一个。"""
    root = _make_adapter(tmp_path / "adapter", global_step=None)
    for i, step in (("checkpoint-10", 10), ("checkpoint-25", 25)):
        d = root / i
        d.mkdir()
        (d / "trainer_state.json").write_text(
            json.dumps({"global_step": step}), encoding="utf-8")
    with pytest.raises(AdapterArtifactError) as ei:
        AdapterArtifactUpdater(adapter_dir=root, verifier_id=VERIFIER).apply({})
    assert "steps_ambiguous" in str(ei.value)

def test_adapter_path_is_shareable_relative(tmp_path: Path) -> None:
    """回执要可分享：workspace_root 给定时，adapter_path 落相对路径。"""
    root = _make_adapter(tmp_path / "ws" / "adapter")
    receipt = AdapterArtifactUpdater(adapter_dir=root, verifier_id=VERIFIER,
                                     workspace_root=tmp_path / "ws").apply({})
    assert receipt["adapter_path"] == "adapter/adapter_model.safetensors"
    # _make_adapter 默认写了顶层 trainer_state.json（顶层优先），相对化后为：
    assert receipt["steps_source"] == "adapter/trainer_state.json"


def test_adapter_path_stays_absolute_without_root(tmp_path: Path) -> None:
    root = _make_adapter(tmp_path / "adapter")
    receipt = AdapterArtifactUpdater(adapter_dir=root, verifier_id=VERIFIER).apply({})
    assert receipt["adapter_path"].startswith(str(tmp_path))


# ---- 接真机产物（盘上没有就跳过，绝不伪造）----

REAL_ADAPTER = Path(__file__).resolve().parents[2] / "paper_agent" / "outputs" / "tmlr-qwen3-4b-p2"


@pytest.mark.skipif(not REAL_ADAPTER.is_dir(), reason="真 QLoRA 产物不在盘上")
def test_real_p2_adapter_yields_valid_receipt() -> None:
    receipt = AdapterArtifactUpdater(adapter_dir=REAL_ADAPTER, verifier_id=VERIFIER,
                                     expected_base_model=BASE).apply({})
    cleaned, reason = validate_weight_receipt(receipt, VERIFIER)
    assert reason is None, reason
    assert cleaned["steps"] == 25          # trainer_state.json global_step
    assert cleaned["adapter_sha256"] == sha256_file(REAL_ADAPTER / "adapter_model.safetensors")
