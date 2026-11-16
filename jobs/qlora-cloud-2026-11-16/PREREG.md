# 预注册：真 QLoRA 云端权重杠杆作业卡（岔口 ③）

- 时间：2026-11-16（America/Los_Angeles）
- 目标：将 `gsm8k-self-evolve/evokit/weight_updater.py` 的 `cloud_lora_command` 接到真实 LoRA/DPO 训练入口（`paper_agent/train/train_dpo.py`）的**可执行作业卡**，形成“候选→云端训练→adapter 产物→本地自算 sha256 对表→回执入 `run_interleaved_loop`”闭环；本卡预注册作业参数、回执契约与停机/恢复条件。**本卡不在本机跑训练**（AGENTS.md 第17条）。
- 前置已完成（本地 smoke，非能力结论）：`9608261` 回执契约 fail-closed + `2ec735e` 云端命令生成/双端哈希对表/`tiny_weight_step.py` 2 参数 3 步 SGD 真机回执（`results/weight-channel-smoke-2026-11-11.md`，radeon-amd:33100 当时可达，receipt `9be1afc7...`，loop 两轮 `stopped_reason=None final_score=0.93`）。

## 数据与评测（预注册）
- 训练数据（固定输入）：`paper_agent/data/dpo_p0v2.jsonl`（`train_dpo.py` 默认 `dpo_train_file`），**本次不改数据、不混入新样本**；作业前记录文件字节数与 sha256。
- 基座与初始化：`base_model=Qwen/Qwen3-4B`，`sft_adapter=paper_agent/outputs/tmlr-qwen3-4b-p1v2/checkpoint-136`（与 `train_dpo.py` CFG 一致）；无 adapter 时按脚本现有分支记录 `[warn]`，不伪造回执。
- 评测/verifier：权重轮 `evaluate` 必须返回 `verifier_id="verifier-frozen-v1"`（与 `run_interleaved_loop` 一致）；verifier 漂移 → `validate_weight_receipt`/loop fail-closed 停机。最小效益判据沿用 `min_gain=0.02`（`lever_selector` 默认），基线分来自同一 verifier 上的 incumbent。
- 预期收益边界：本作业验证**权重杠杆通道可被真实训练产物驱动且可审计回执**；不宣称 GSM8K/TMLR 指标提升，结果仅在本 verifier+数据+步数条件下解释。

## 训练超参与步数（固定，取自 `train_dpo.py` 可复现默认/烟雾档）
- LoRA/DPO：`beta=0.1, lr=5e-5, epochs=1, per_device_bs=1, grad_accum=8, max_len=384, seed=42, warmup_steps=5, logging_steps=5, save_steps=25`
- 步数：云端卡先跑 **`--smoke`（max_steps=10）** 作为可中断亚决策前的通道验证档；若通道与回执通过，再按预注册升级到 `--p2`（`max_steps=-1`，1 epoch）——升级必须记录同一 `job_digest` 派生链与新回执，不得复用 smoke 回执冒充 p2。
- 产物：`adapter_model.safetensors`/adapter 目录（按 PEFT 保存）+ 训练侧 stdout 末行 JSON `{"steps": <int>, ...}`；回执必含 `adapter_sha256`（本地实算）、`verifier_id`、`steps`、`job_digest`、`adapter_path`。

## 回执契约（fail-closed，`validate_weight_receipt` + `SubprocessWeightUpdater`）
- `adapter_sha256`：本地对拉回产物 `sha256_file` 计算；若命令自报 sha 与本地不一致 → `reported adapter sha mismatch`（拒绝）。
- `steps`：非负 int 且非 bool；缺失/非法 → 无效回执。
- `verifier_id`：必须与 loop 传入一致，否则 `weight_verifier_drift`。
- 缺产物/命令非 0/无 JSON stdout/形状错误 → 停机记录，不晋升。

## 运行形态与可恢复性
- 位置：云端 `SCRATCH=$HOME/dsh-scratch/qlora-cloud-2026-11-16`（或宿主可写 scratch）；作业目录按 run/job 隔离。
- 方式：`nohup`/`setsid` detached + 周期写 `job_state.json`（status/step/checkpoint_path/last_heartbeat/sha_when_done）；中断后可从 `save_steps` checkpoint 续跑（需记录 resume 命令与新回执）。
- 本地侧：只持有 job spec、拉回 adapter、算哈希、写 `results/qlora-cloud-2026-11-16-run.json`。

## 当前可达性与阻塞（2026-11-16 现场）
- `remote_host_list`：`radeon-amd`(root@36.150.116.206:33100, probedAt=null, 2026-11-12 自动销毁备注)、`amd-hz`(root@36.150.116.206:34677, probed 128 CPU **gpus=["none"]**)。
- SSH 快探针：`33100`/`34677` 均 `Connection refused`（BatchMode, 5s）。
- **判定：BLOCKED_ON_COMPUTE（非本机可解）**。在宿主不可达且已知无 GPU 的条件下，不伪造训练回执、不在本机启动长训。解除条件：可达 GPU 宿主 + 依赖环境（torch/bitsandbytes/peft/trl/datasets + 基座与 SFT adapter 可用）+ 预注册数据校验通过；解除后按本卡命令执行 detached smoke→p2。

## 解除后执行命令模板（待宿主就绪时原样使用/填充）
```bash
# 1) 预检数据与依赖（云端）
sha256sum paper_agent/data/dpo_p0v2.jsonl
python3 -c "import torch,trl,peft,bitsandbytes,datasets; print(torch.cuda.is_available())"
# 2) smoke（max_steps=10）
mkdir -p $SCRATCH/qlora-cloud-2026-11-16 && cd $SCRATCH/qlora-cloud-2026-11-16
nohup python3 /path/to/paper_agent/train/train_dpo.py --smoke --train-file /path/to/paper_agent/data/dpo_p0v2.jsonl --sft-adapter /path/to/paper_agent/outputs/tmlr-qwen3-4b-p1v2/checkpoint-136 --out-dir $SCRATCH/qlora-cloud-2026-11-16/smoke >smoke.stdout 2>smoke.stderr & echo $! > smoke.pid
# 3) 产物回传 + 本地 sha256 对表（经 SubprocessWeightUpdater/cloud_lora_command），写 results/qlora-cloud-2026-11-16-run.json
# 4) 通过后升级 --p2（记录新回执，不复用 smoke）
```
