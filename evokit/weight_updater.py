"""权重杠杆的真实落地通道：命令执行 → 产物哈希 → 回执。

为什么需要这一层：`lever_selector.run_interleaved_loop` 在 weight 轮调用
`weight_updater.apply(candidate)`，但"我训了"不能是一句话。SIA 的 Coupled
co-evolutionary Goodhart（arXiv:2605.27276 §Limitations）说的正是这件事：
harness 与权重共用同一个 verifier，任一侧的改动若不能独立复核，联合不动点就
只是两个互盲优化器的巧合。所以本模块把 weight 侧约束成一条可审计通道：

    apply(candidate)
      → 写出 job spec（含 candidate 摘要）
      → 执行命令（本地 smoke 或 ssh 到云端训练机）
      → **自己**算产物 sha256（不采信命令自报的哈希）
      → 返回 {"adapter_sha256", "verifier_id", "steps"}

任何一步缺失都抛错或返回不合契约的值，由调用方 fail-closed 停机。

边界（AGENTS.md 第 17 条）：本机只跑亚分钟 smoke；真训练走云端，命令模板里
留 HOST / SCRATCH / DATASET / STEPS 占位符，作业目录与断点由云端负责。
"""
from __future__ import annotations

import hashlib
import json
import shlex
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

SHA_CHUNK = 1 << 20


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(SHA_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class WeightUpdateJob:
    """一次权重更新的作业描述；摘要用于把回执钉回候选。"""

    candidate: Mapping[str, Any]
    verifier_id: str
    round_index: int

    def digest(self) -> str:
        payload = json.dumps({"candidate": dict(self.candidate),
                              "verifier_id": self.verifier_id,
                              "round": self.round_index},
                             sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class SubprocessWeightUpdater:
    """跑一条外部命令产出 adapter 文件，再自己算哈希。

    命令模板可用占位符：
      {job_spec}      job spec 的 JSON 文件路径（内含 candidate/verifier/round）
      {adapter_out}   期望的 adapter 产物路径
    命令 stdout 最后一行必须是 JSON：{"steps": <非负整数>}（可附加任意诊断字段）。
    adapter 文件不存在、steps 非法、sha 算不出 → 抛 RuntimeError，绝不返回伪回执。
    """

    command: str
    verifier_id: str
    workdir: Path
    timeout_seconds: float = 120.0
    adapter_name: str = "adapter.jsonl"
    extra: dict[str, Any] = field(default_factory=dict)
    calls: list[dict[str, Any]] = field(default_factory=list)

    def apply(self, candidate: Mapping[str, Any]) -> dict[str, Any]:
        job = WeightUpdateJob(candidate=candidate, verifier_id=self.verifier_id,
                              round_index=len(self.calls))
        job_dir = Path(tempfile.mkdtemp(prefix="wjob-", dir=str(self.workdir)))
        spec_path = job_dir / "job.json"
        spec_path.write_text(json.dumps({
            "candidate": dict(candidate), "verifier_id": self.verifier_id,
            "round": job.round_index, "digest": job.digest(), **self.extra,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        adapter_path = job_dir / self.adapter_name
        # 只替换两个具名占位符：命令里可能含花括号（JSON / shell），
        # 用 str.format 会把它们当占位符炸掉。
        command = (self.command
                   .replace("{job_spec}", shlex.quote(str(spec_path)))
                   .replace("{adapter_out}", shlex.quote(str(adapter_path))))
        completed = subprocess.run(command, shell=True, cwd=str(self.workdir),
                                   capture_output=True, text=True,
                                   timeout=self.timeout_seconds)
        self.calls.append({"command": command, "returncode": completed.returncode,
                           "stdout_tail": completed.stdout[-500:],
                           "stderr_tail": completed.stderr[-500:]})
        if completed.returncode != 0:
            raise RuntimeError(f"weight update command failed rc={completed.returncode}: "
                               f"{completed.stderr[-300:]}")
        reported = _last_json(completed.stdout)
        steps = reported.get("steps")
        if isinstance(steps, bool) or not isinstance(steps, int) or steps < 0:
            raise RuntimeError(f"command did not report a non-negative integer steps: {reported!r}")
        if not adapter_path.is_file():
            raise RuntimeError(f"adapter artifact missing: {adapter_path}")
        local_sha = sha256_file(adapter_path)
        reported_sha = reported.get("adapter_sha256")
        if isinstance(reported_sha, str) and reported_sha != local_sha:
            # 命令自报的哈希与盘上字节不一致 → 这条回执不可信
            raise RuntimeError(f"reported adapter sha mismatch: {reported_sha} != {local_sha}")
        return {"adapter_sha256": local_sha,
                "verifier_id": self.verifier_id, "steps": steps,
                "job_digest": job.digest(), "adapter_path": str(adapter_path)}


def _last_json(stdout: str) -> dict[str, Any]:
    for line in reversed([ln.strip() for ln in stdout.splitlines() if ln.strip()]):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise RuntimeError(f"no JSON object on stdout tail: {stdout[-300:]!r}")


def cloud_lora_command(*, host: str, port: int, scratch: str, trainer: str,
                       steps: int = 3) -> str:
    """生成一条"云端训练 + 拉回产物"的命令（供 SubprocessWeightUpdater 用）。

    形状：ssh 在训练机上跑 trainer（产物落远端 scratch），scp 把产物拉回
    {adapter_out}，随后本机自己算 sha256。远端 trainer 自报的哈希也会被对表，
    不一致即判失败——远端说成功不算成功，字节才算。
    本函数只生成字符串，不执行；真跑由调用方在作业卡里决定。
    """
    remote_job = f"{scratch}/job.json"
    remote_adapter = f"{scratch}/adapter.jsonl"
    return (
        # job spec 是本地文件，先送到训练机，否则远端 python 打不开它
        f"scp -P {port} -o BatchMode=yes {{job_spec}} {host}:{remote_job} && "
        f"ssh -p {port} -o BatchMode=yes {host} "
        f"'mkdir -p {scratch} && cd {scratch} && "
        f"STEPS={steps} python3 {trainer} {remote_job} {remote_adapter}' && "
        f"scp -P {port} -o BatchMode=yes {host}:{remote_adapter} {{adapter_out}}"
    )
