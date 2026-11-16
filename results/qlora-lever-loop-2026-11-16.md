# 权重通道 × 真 QLoRA-4B SFT 续训 adapter（2026-11-16，本地）

**用途**：用盘上真实的 Qwen3-4B QLoRA adapter 驱动 `run_interleaved_loop`，证明权重杠杆能被**真实训练产物**（而非 2 参数玩具模型）喂入并产出可审计回执。对应岔口 ③ 的验收判据：`PREREG.md:11`「验证权重杠杆通道可被真实训练产物驱动且可审计回执；不宣称 GSM8K/TMLR 指标提升」。

## 产物身份（盘上字节，可复算）

| 项 | 值 |
| --- | --- |
| adapter 目录 | `paper_agent/outputs/tmlr-qwen3-4b-p2/` |
| 权重文件 | `adapter_model.safetensors` 264,308,896 字节 |
| `adapter_sha256`（本机实算） | `f04022a947b3074eb440c14e6cee70da59354b0a7e809939c75a125875d659a1` |
| `base_model_name_or_path` | `Qwen/Qwen3-4B` |
| LoRA | `peft_type=LORA, r=32, lora_alpha=16, lora_dropout=0.05, target_modules=[o_proj,k_proj,q_proj,gate_proj,v_proj,up_proj,down_proj]` |
| 张量 | 504 个 F32；252 个 `lora_B` **全非零**（首个 `layers.0.mlp.down_proj.lora_B.weight` mean|w|=0.00235, max|w|=0.00952, std=0.00284）——排除“全零初始化、一步未走”的假产物 |
| `trainer_state.json` | `checkpoint-25/trainer_state.json`：`global_step=25, max_steps=25, epoch=1.0, best_metric(eval_loss)=0.4894774556159973` |
| 训练日志 | `paper_agent/reports/train_p2.log`（头尾/进度条/指标齐全） |
| 产生它的脚本 | `paper_agent/train/train_agent.py`（`--out-dir paper_agent/outputs/tmlr-qwen3-4b-p2 --from-adapter .../p1v2/checkpoint-136 --train-file paper_agent/data/sft_p2chosen_train.jsonl`；日志首行 `[resume] SFT adapter attached+unfrozen` 是该脚本 :94 的打印串，`[data] train=400 val=240` 是 :109） |
| 训练方式 | **SFT 续训**（`cfg_snapshot.json` `mode=p1`、`train_file=...sft_p2chosen_train.jsonl`、`epochs=2`、`warmup_steps=8`、`lr=2e-4` cosine），lr 轨迹 `4.957e-05 → 1.386e-05` 与之吻合 |
| 与 p1v2 的关系 | 252 个 `lora_B` 相对 p1v2 平均变动 13.6%（median 13.6%，mean|Δ|=0.000331）→ 小幅续训，非从头新建 |
| 训练时间窗 | `2026-09-10 21:26:21-07:00`（cfg_snapshot mtime）→ `2026-09-10 21:34:18-07:00`（adapter 写入） |
| 训练时长 / 步数 | `train_runtime=448.8s`，`25/25 [07:28<00:00, 17.96s/it]`，400 pairs，1 epoch |
| 训练指标（log 实录） | `eval_loss=0.4895, eval_entropy=0.4484, eval_mean_token_accuracy=0.8967, train_loss=1.861` |
| 训练硬件（log 语境 + 当前探针） | 2026-09-10 在本机 `NVIDIA GeForce RTX 3060 Laptop GPU 6144MiB` 上跑通（`max_memory={0:"4600MiB","cpu":"12GiB"}` + CPU offload） |
| 训练数据 | `paper_agent/data/sft_p2chosen_train.jsonl` 400 行 / sha256 `a0e41f5bb07bb5086cf0668002eefc97095caad5afe93dc0bcf275529d5e13e8`（键：`messages/evidence_refs/synthetic/task_stage`），验证集 `paper_agent/data/sft_p0v2_val.jsonl` 240 条 |
| 续训起点 | `paper_agent/outputs/tmlr-qwen3-4b-p1v2/checkpoint-136`（SFT adapter，390M） |

## 通道与契约

新增实现（TDD，`gsm8k-self-evolve/tests/test_adapter_receipt.py` 10 passed）：
- `evokit/adapter_receipt.py`：`AdapterArtifactUpdater(adapter_dir, verifier_id, expected_base_model)` 只读盘上产物，产出与 `validate_weight_receipt` 同契约回执。
- 强制停机：`adapter_model.safetensors` / `adapter_config.json` 缺失、`trainer_state.json` 缺失（`steps_unknown`，未知≠0）、checkpoint 步数冲突（`steps_ambiguous`）、`lora_B` 全零（`untrained`）、`base_model_name_or_path` 不匹配（`base_model_mismatch`）。
- 步数来源：顶层 `trainer_state.json` 优先，否则回落唯一 `checkpoint-*/trainer_state.json`（匹配本产物的 `save_total_limit=1` 形态），并在回执中记录 `steps_source`。
- `lora_B` 非零判定：直接扫 safetensors payload 字节，不依赖 torch/GPU，便于在无 CUDA 环境做审计。

闭环脚本：`gsm8k-self-evolve/scripts/run_qlora_lever_loop.py` → `results/qlora-lever-loop-2026-11-16.json`

## 实测回执与循环

对 `tmlr-qwen3-4b-p2` 产出回执（`AdapterArtifactUpdater.apply` → `validate_weight_receipt` = `(cleaned, None)`）：
```json
{
  "adapter_sha256": "f04022a947b3074eb440c14e6cee70da59354b0a7e809939c75a125875d659a1",
  "verifier_id": "verifier-frozen-v1",
  "steps": 25,
  "steps_source": "paper_agent/outputs/tmlr-qwen3-4b-p2/checkpoint-25/trainer_state.json",
  "adapter_path": "paper_agent/outputs/tmlr-qwen3-4b-p2/adapter_model.safetensors",
  "base_model": "Qwen/Qwen3-4B",
  "lora_r": 32,
  "lora_b_nonzero": 252,
  "bytes": 264308896
}
```

`run_interleaved_loop(rounds=2, min_gain=0.02, baseline_score=0.80, verifier_id="verifier-frozen-v1")`：
- round 0：`lever=harness rule_id=R1_scaffold_bottleneck delta=+0.06 accepted=true`
- round 1：`lever=weight rule_id=R2_capability_bottleneck delta=+0.07 accepted=true`，`weight_receipt.steps=25 sha256前16=f04022a947b3074e`
- `stopped_reason=null, accepted=[0,1], final_score=0.93`

## 当前本地可行性边界（实测）

- **可行**：读取/审计本地真实 4B QLoRA 产物、实算 sha256、产出合约回执、驱动 `run_interleaved_loop` 闭环；本地有 `Qwen/Qwen3-4B` 基座 8.1G（本地模型库 `data1/models/Qwen3-4B`（相对该机根），3 shard 齐全）与完整训练栈（torch 2.14.1+cu130, transformers 5.17.0, peft 0.21.2, trl 1.17.1, bitsandbytes 0.50.2, datasets 5.1.0, accelerate 1.15.0）。
- **当前不可行（GPU 硬件态）**：`nvidia-smi` 报 `GPU requires reset / Recovery Action: Reset`，`torch.cuda.is_available()=False`（system python）。`/var/log/kern.log.1` 记录 `2026-11-13T04:47:49-08:00` 起 Xid 119 (GSP RPC timeout, pid=1065034 python3) → `2026-11-13T04:48:01-08:00` Xid 154 `GPU recovery action changed ... to 0x1 (GPU Reset Required)`；`uptime -s = 2026-11-04 22:47:00`，至今未重启。无 sudo 无法重置设备。→ **无法在不重启的前提下发起新一轮 CUDA 训练**；本轮用 2026-09-10 同卡真实产物闭环通道。
- CPU 4bit/QLoRA：system python `torch.cuda.is_available()=False` 且 bitsandbytes CUDA 训练路径不可用；4B 级 DPO 在 CPU 上远超亚分钟 smoke 边界，未作为替代路径执行。

## 这条证据**不是** DPO（口径纠正）

初版本文件把该产物写成「QLoRA DPO adapter」，实测推翻：`train_dpo.py --p2` 在这台机器上**从未成功过**。

- `paper_agent/reports/train_dpo_smoke.log` 尾部是真实 OOM：`torch.OutOfMemoryError: CUDA out of memory. Tried to allocate 742.00 MiB. GPU 0 has a total capacity of 5.67 GiB of which 468.06 MiB is free...`（抛在 `modeling_qwen3.py:494` 的 `lm_head`，栈经 `peft_model.py:2101` → `tuners_utils.py:333`）。
- `paper_agent/outputs/tmlr-qwen3-4b-p2smoke/` 只有 `cfg_snapshot.json`（796 字节），没有 adapter —— DPO smoke 没跑出产物。
- `train_p2.log` 里 **0 处** `beta/dpo/chosen/rejected` 痕迹，却有一处 `[resume] SFT adapter attached+unfrozen`；`cfg_snapshot.json` 的 `mode=p1`、`train_file` 指向 SFT 数据。
- DPO 数据 `paper_agent/data/dpo_p0v2.jsonl`（400 行，`prompt/chosen/rejected`，sha `520be7f...`）确实存在，但它**没有被这个 adapter 消费过**。

所以：通道判据「权重杠杆能被真实 QLoRA 训练产物驱动」**成立**（产物是真的，哈希是真的，步数是真的）；但「被 DPO 产物驱动」**不成立**。要补 DPO 这一格，得先解决 6GB 卡的 DPO 峰值显存（或换卡/上云），再跑 `train_dpo.py --p2`。

## 边界（必须连着引用）

- `evaluate()` 分数为脚本注入的合成序列，**不是** GSM8K/TMLR 指标，也不是模型输出。
- 本脚本**不训练**任何模型；训练已于 2026-09-10 在本机 6GB 卡完成，证据为 `train_p2.log` + `trainer_state.json` + 非零 `lora_B` + 落盘 safetensors 哈希。
- 结论边界：**权重杠杆通道可被真实 Qwen3-4B QLoRA 训练产物驱动且回执可审计**；不宣称能力提升，不替代预注册的云端/可复现全量实验。
- 若需“当下新跑一遍”完整 QLoRA 训练以刷新产物：需在恢复 GPU（重启或宿主重置 dGPU）后于离线可用的本地基座目录（该机 `data1/models/Qwen3-4B`）上执行 `paper_agent/train/train_dpo.py --p2`（已知 448.8s 量级先例），或改走可达 GPU 云端通道。
