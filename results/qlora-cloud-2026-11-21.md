# 真 DPO 云端作业 — smoke + p2 全训均跑通，回执链闭合

日期 2026-11-21。实例 `rgapi-one-click-27950-a198367b`（AMD Radeon Cloud，SSH root@36.150.116.206:35361，gfx1100 48GiB bf16，11-23 20:40 销毁）。预注册见 `jobs/qlora-cloud-2026-11-16/PREREG.md`。

## 结论
- **smoke（10 步真 DPO）跑通**：loss 0.000368、step1 rewards chosen 13.99/rejected -5.50、accuracy 1.0、train_runtime 75.5s。产物 adapter sha256 `e44f8acdcc6fdfad0febc6a69c2207447dbcb237c3cf15960694bb626af743e9`（264308896B，252 个 lora_B 非零）。
- **回执链闭合**：`jobs/remote_receipt.py` 在云端读产物算出回执 → 拉回小 JSON → `evokit.lever_selector.validate_weight_receipt(receipt, "verifier-frozen-v1")` 返回 `reason=None`（契约通过）。
- **p2（1 epoch 全训）跑通**：前 7 次尝试因共享实例其它租户抢占 VRAM（free 一度 3.7GiB）在 `precompute_ref_log_probs` 的 `F.log_softmax` 处 HIP OOM（本方 PyTorch 仅占 ~8GiB，非本方峰值）；`run_p2_retry.sh` 等到连续 3 次 free≥36GiB 窗口后，**attempt 8 rc=0** 完成。50 steps / 1 epoch，train_runtime 233.5s，final_train_loss 7.37e-05，rewards accuracies 全程 1.0。产物 adapter sha256 `b9ef9253093034bab7e0cff0c72fa05dcdda6ab879fa4e3505c0927270bcc6a9`（264308896B，252 lora_B 非零），**与 smoke 回执不同**（独立 p2 回执）。
- **p2 回执独立验契约**：云端算 p2 回执 → `p2_receipt.json` → 本地 `validate_weight_receipt(receipt, "verifier-frozen-v1")` 返回 `reason=None`，且 sha 与 smoke 不同（未复用）。

## 关键口径（不可混淆）
1. **这是真 DPO，不是 SFT 续训**：本次跑的是 `train_dpo.py` + `dpo_p0v2.jsonl`（chosen/rejected 对），日志有 loss/rewards/chosen/rejected。此前本地 `paper_agent/outputs/tmlr-qwen3-4b-p2` 的 adapter（sha `f04022a9...`）是 SFT 续训（`train_agent.py` + `sft_p2chosen_train.jsonl`，无 DPO 字段），两者产物身份不同，不可互认。
2. **smoke ≠ p2（两份独立回执）**：PREREG 规定 smoke 是可中断的通道验证档，p2 升级必须有独立新回执、严禁拿 smoke 冒充。当前 `smoke_receipt.json`（sha `e44f8acd...`, steps 10）与 `p2_receipt.json`（sha `b9ef9253...`, steps 50）是两次训练各自产物，均过本地契约校验；`run.json` 的 `p2.status=SUCCESS`，`attempt=8`。
3. **token ≠ 成本**：全程无 token→金额换算；smoke 判据是通道 + 回执，不是 GSM8K/TMLR 指标提升。
4. **no_4bit 路径**：ROCm base 镜像装不了 bitsandbytes，全程 bf16 非量化 LoRA（48GiB 装得下 4B），与论文里的 bnb_4bit_NF4 不是同一量化口径。

## 复现命令
```bash
# 环境（云端 /opt/venv）
pip install trl==0.24.0 transformers==4.57.6 peft==0.18.1 accelerate==1.13.0 datasets==4.8.2
modelscope download --model Qwen/Qwen3-4B --local_dir /workspace/models/Qwen3-4B

# smoke（已成功）
cd /workspace/qlora-job && DPO_BASE_MODEL=/workspace/models/Qwen3-4B \
  PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
  nohup /opt/venv/bin/python train/train_dpo.py --smoke --no-4bit --gpu-mem-mib 20000 \
  --train-file /workspace/qlora-job/data/dpo_p0v2.jsonl \
  --sft-adapter /workspace/qlora-job/sft/checkpoint-136 \
  --out-dir /workspace/qlora-job/out/smoke

# 云端回执（无 GPU）
/opt/venv/bin/python remote_receipt.py /workspace/qlora-job/out/smoke > smoke_receipt.json

# 本地验契约
PYTHONPATH=gsm8k-self-evolve python3 -c \
  "import json; from evokit.lever_selector import validate_weight_receipt; \
   print(validate_weight_receipt(json.load(open('gsm8k-self-evolve/results/qlora-cloud-2026-11-21/smoke_receipt.json')),'verifier-frozen-v1'))"

# p2（attempt 8 抓到 3 次连续 free>=36 GiB 窗口后成功）
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
  nohup /opt/venv/bin/python train/train_dpo.py --p2 --no-4bit --gpu-mem-mib 12000 \
  --train-file /workspace/qlora-job/data/dpo_p0v2.jsonl \
  --sft-adapter /workspace/qlora-job/sft/checkpoint-136 \
  --out-dir /workspace/qlora-job/out/p2

/opt/venv/bin/python remote_receipt.py /workspace/qlora-job/out/p2 > p2_receipt.json
```

## 证据文件
- `results/qlora-cloud-2026-11-21-run.json` — 结构化结果 + 边界（status=P2_SUCCESS）
- `results/qlora-cloud-2026-11-21/smoke_receipt.json` — 云端算出的 smoke 回执（sha `e44f8acd...`, steps 10）
- `results/qlora-cloud-2026-11-21/p2_receipt.json` — 云端算出的 p2 回执（sha `b9ef9253...`, steps 50，独立）
- `results/qlora-cloud-2026-11-21/p2_adapter_config.json` — p2 adapter 配置（base Qwen/Qwen3-4B, r=32, alpha=16）
- `results/qlora-cloud-2026-11-21/p2_train.stdout` — p2 全训练指标（loss/rewards/accuracies/runtime）
- `jobs/remote_receipt.py` — 云端侧回执计算脚本
- `jobs/run_p2_retry.sh` — p2 显存窗口 retry daemon（attempt 8 成功）
- 云端日志 `/workspace/logs/dpo-smoke.stdout|stderr`、`/workspace/logs/dpo-p2-retry.log`、`/workspace/logs/dpo-p2.stdout`
