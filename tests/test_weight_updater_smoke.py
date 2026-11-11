# 权重通道端到端 smoke：命令 → 真实产物 → 自算 sha256 → 回执 → 循环接受。
#
# 这里训练的是一个 2 参数线性模型（scripts/tiny_weight_step.py，纯 Python 3 步
# SGD，亚分钟），目的是验证**回执通道**而不是训练效果。真 LoRA 走云端模板
# （evokit.weight_updater.CLOUD_LORA_TEMPLATE），本机不跑长训练（AGENTS.md 17）。
import json
import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evokit.lever_selector import FailureProfile, run_interleaved_loop  # noqa: E402
from evokit.weight_updater import (  # noqa: E402
    SubprocessWeightUpdater, sha256_file,
)

TRAINER = ROOT / "scripts" / "tiny_weight_step.py"
VERIFIER = "verifier-frozen-v1"


def _updater(tmp_path, command):
    return SubprocessWeightUpdater(command=command, verifier_id=VERIFIER,
                                   workdir=tmp_path, timeout_seconds=60.0)


def test_real_weight_update_flows_through_loop(tmp_path):
    # GREEN：命令真产出 adapter 文件，回执 sha 与盘上字节一致，循环接受该轮
    # 工作区路径含字面反斜杠（F:\deepseek），必须过 shlex.quote
    command = (f"{shlex.quote(sys.executable)} {shlex.quote(str(TRAINER))} "
               "{job_spec} {adapter_out}")
    updater = _updater(tmp_path, command)
    report = run_interleaved_loop(
        rounds=2,
        diagnose=lambda i: FailureProfile(harness_errors=0, reasoning_errors=6),
        propose_harness=lambda i: {"answer_policy": "h"},
        propose_weight=lambda i: {"lora_rank": 8, "lr": 1e-4},
        evaluate=lambda cand, i: {"score": 0.95, "verifier_id": VERIFIER},
        verifier_id=VERIFIER, weight_updater=updater,
        min_gain=0.02, baseline_score=0.80,
    )
    weight_rounds = [r for r in report["rounds"] if r["lever"] == "weight"]
    assert weight_rounds and report["stopped_reason"] is None
    receipt = weight_rounds[0]["weight_receipt"]
    assert receipt["steps"] == 3
    assert receipt["verifier_id"] == VERIFIER
    produced = Path(receipt["adapter_path"])
    assert produced.is_file()
    assert receipt["adapter_sha256"] == sha256_file(produced)
    # 权重真的变了：产物里的权重不等于初始点
    weights = json.loads(produced.read_text(encoding="utf-8"))["weights"]
    assert weights != [0.1, -0.2]
    assert len(weights) == 2


def test_missing_artifact_raises_instead_of_faking_receipt(tmp_path):
    # RED 反证：命令 rc=0 但没写产物 → 抛错，不允许"成功"一个不存在的权重
    command = f"{sys.executable} -c \"print('{{\\\"steps\\\": 3}}')\""
    updater = _updater(tmp_path, command)
    try:
        updater.apply({"lora_rank": 8})
    except RuntimeError as exc:
        assert "adapter artifact missing" in str(exc)
    else:
        raise AssertionError("missing artifact must raise, not return a receipt")


def test_non_json_stdout_raises(tmp_path):
    # RED 反证：stdout 没有 JSON 回执 → 抛错
    command = f"{sys.executable} -c \"print('done')\""
    updater = _updater(tmp_path, command)
    try:
        updater.apply({"lora_rank": 8})
    except RuntimeError as exc:
        assert "no JSON object" in str(exc)
    else:
        raise AssertionError("stdout without JSON must raise")


def test_failed_command_raises(tmp_path):
    # RED 反证：训练命令失败 → 抛错，不许静默跳过
    updater = _updater(tmp_path, "exit 3")
    try:
        updater.apply({"lora_rank": 8})
    except RuntimeError as exc:
        assert "rc=3" in str(exc)
    else:
        raise AssertionError("failing command must raise")


def test_reported_sha_mismatch_raises(tmp_path):
    # RED 反证：命令自报的哈希与盘上字节不一致 → 回执不可信，必须抛错
    liar = tmp_path / "liar.sh"
    liar.write_text(
        "#!/bin/sh\n"
        "printf 'x' > \"$2\"\n"
        "printf '{\"steps\": 1, \"adapter_sha256\": \"%s\"}\\n' "
        "0000000000000000000000000000000000000000000000000000000000000000\n",
        encoding="utf-8")
    updater = _updater(tmp_path, f"sh {shlex.quote(str(liar))} {{job_spec}} {{adapter_out}}")
    try:
        updater.apply({"lora_rank": 8})
    except RuntimeError as exc:
        assert "reported adapter sha mismatch" in str(exc)
    else:
        raise AssertionError("sha mismatch must raise")
