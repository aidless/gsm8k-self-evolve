# p2 vs smoke 对比读数表（真 DPO，2026-11-21）

数据来源：`results/qlora-cloud-2026-11-21-run.json` + `results/qlora-cloud-2026-11-21/p2_train.stdout`；
由 `scripts/p2_vs_smoke.py` 只读提取，**未改论文任何数字，未重跑训练**。

| 指标 | smoke | p2 (1 epoch) |
|---|---|---|
| steps | 10 | 50 |
| epoch | 0.2 | 1.0 |
| train_runtime_s | 75.5 | 233.5468 |
| final loss | 0.0003683001942 | 7.366215409e-05 |
| step1 loss | 0.0007 | 0.0007 |
| step1 rewards chosen/rejected | 13.99/-5.5 | 14.16/-5.50 |
| rewards accuracy | 1.0 | [1.0] |
| reward margin (first→last) | — | 19.6661→27.2102 |
| adapter sha256 (前16) | e44f8acdcc6fdfad | b9ef9253093034ba |
| adapter bytes | 264308896 | 264308896 |

## 共性（不可比项）

- training_script: train_dpo.py --p2/--smoke (true DPO on chosen/rejected pairs)
- base_model: Qwen/Qwen3-4B
- train_file: dpo_p0v2.jsonl (400 rows)
- precision: bf16 non-quantized LoRA (--no-4bit; bitsandbytes unavailable on gfx1100)
- hardware: AMD Radeon Graphics gfx1100 48GiB
- verifier_id: verifier-frozen-v1

## 不构成能力结论（not claimed）

- no held-out GSM8K/TMLR metric; reward accuracy=1.0 means the model fit these 400 pairs, not generalization
- final loss decreasing from smoke to p2 is not evidence of capability improvement
- the two adapters are independent artifacts (different sha), not one resumed from the other
