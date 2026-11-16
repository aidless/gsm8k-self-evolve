# QLoRA 云端作业卡 — 2026-11-16（岔口 ③）

**状态：BLOCKED_ON_COMPUTE（预注册完成，执行待 GPU 宿主可达）**

- 预注册与命令模板：`jobs/qlora-cloud-2026-11-16/PREREG.md`
- 机器可读作业卡：`jobs/qlora-cloud-2026-11-16/job_spec.template.json`
- 训练入口（固定）：`paper_agent/train/train_dpo.py`（`--smoke` max_steps=10 → 验证后 `--p2` 1 epoch；CFG: beta=0.1, lr=5e-5, bs1×grad8, max_len=384, seed=42, base `Qwen/Qwen3-4B` + SFT `paper_agent/outputs/tmlr-qwen3-4b-p1v2/checkpoint-136`，数据 `paper_agent/data/dpo_p0v2.jsonl`）
- 回执契约：`evokit.weight_updater.SubprocessWeightUpdater` + `validate_weight_receipt`（本地实算 `adapter_sha256` 与自报对表、`steps` 非负 int、`verifier_id=verifier-frozen-v1` 一致；任一不符 fail-closed）。云端命令生成：`cloud_lora_command(...)`（scp job spec → ssh 训练写 adapter → scp 拉回）。

## 现场探测（2026-11-16 03:57-08:00）
- `radeon-amd` root@36.150.116.206:33100 — SSH `Connection refused`（host 元数据注明 2026-11-12 自动销毁，probedAt=null）。
- `amd-hz` root@36.150.116.206:34677 — SSH `Connection refused`；历史 probe 记录 `gpus=["none"]`（128 CPU），不满足 QLoRA。
- 结论：当前无可达 GPU 宿主，未提交训练、不生成伪回执。解除阻塞后按 PREREG 执行 detached smoke→p2，并将真实回执落 `results/qlora-cloud-2026-11-16-run.json`。

## 已有真实通道证据（基线）
- `results/weight-channel-smoke-2026-11-11.md`：2 参数 3 步 SGD 经 `cloud_lora_command`/双端哈希/`run_interleaved_loop` 两轮（harness+weight accepted, receipt 验证通过）— **机制/通道 smoke，非 QLoRA 能力结论**。
