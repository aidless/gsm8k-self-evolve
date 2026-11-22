# PREREG-B — 合成能力任务重训 + 配对评测（选项 B）

> 用户 2026-11-22 明确选定"合成更大规模有 ground truth 的能力任务重训 + 评测"。
> 这是**新作业卡**，独立预注册，与原 p2 写作偏好 DPO 完全无关。

## 1. 一句话

在一个**有精确 ground truth 的合成能力任务**上，先训出一个 DPO adapter，再在**训练时没见过的 heldout** 上
配对比较 `Qwen3-4B + SFT` 与 `Qwen3-4B + SFT + 新 DPO`，看**这次 DPO 到底有没有把任务准确率提上去**。

回答的问题：**权重线"改完有没有用"**——本会话此前只证明了"训练通道可跑、回执可审计"，从未测过
adapter 的能力读数。选项 B 补这个读数。

## 2. 任务定义（跑前锁定，不改）

- 任务：`(A*B + C) mod M` 分步算术，A/B 两位数、C 1–50、M 7–13。
- ground truth：Python 精确计算（`scripts/synth_ability.py`），**不靠模型自评、不靠 LLM judge**。
- DPO 偏好对：chosen = 完整正确分步链；rejected = 中间步骤与 chosen 完全相同、**仅最后余数错**
  （差分只在最后一步，给 DPO 一个干净可学信号）。
- 训练集 400 条 seed [0,400)；heldout 60 条 seed [100000,100060)；两区间不相交（脚本断言）。

## 3. 落盘字节（跑前固定）

- 训练数据 `results/qlora-ability-b/synth_train.jsonl` 400 行
  sha256 `b9c618ef9bd9f0231f79c1c6b6361bd0baaf29c4486e1f8caccdd7b30ab41e4c`
- heldout `results/qlora-ability-b/synth_heldout.jsonl` 60 行
  sha256 `dc733c516984b703496787ceafe65bd00a95a87296c88587921f2daf932f1e7e`

## 4. 判据（跑前固定，不事后调）

- 判分：模型输出抽最后一个整数，与 ground truth 精确相等才算对（`score_generations`）。
- 门槛：`min_delta = 0.05`（配对准确率差 ≥ +0.05 → GAIN；≤ −0.05 → REGRESSION；中间 → NO_GAIN）。
- 这是**预注册门槛**：先定 0.05 再跑，不因结果好看调小。

## 5. 训练

- 复用 `train_dpo.py`（不改代码，只换 `--train-file`）：
  `DPO_BASE_MODEL=/workspace/models/Qwen3-4B python train/train_dpo.py --no-4bit --gpu-mem-mib 12000
   --train-file /workspace/qlora-job/ability/synth_train.jsonl
   --sft-adapter /workspace/qlora-job/sft/checkpoint-136
   --out-dir /workspace/qlora-job/ability/out`
- 400 行、1 epoch（`--p2` 走 -1 steps = 1 epoch；本任务用 `--p2` 即 1 epoch）。
- 共享实例可能抢显存 → detached + 日志；OOM 则等 free≥36GiB 重试（复用 run_p2_retry 思路）。

## 6. 评测

- 两组同进程外分别加载（避免重复 4B 权重）：
  - A 组 = `Qwen3-4B + SFT(ckpt-136)` → heldout 60 题生成
  - B 组 = `Qwen3-4B + SFT(ckpt-136) + 新 DPO adapter` → heldout 60 题生成
- 贪心 `do_sample=False`、`max_new_tokens=96`（两同参数，只差 adapter）。
- 云端只**生成**落 `generations_{sft,dpo}.json`；**判分与汇总在本地**做（本地纯函数可复算）。

## 7. 诚实边界（跑前声明）

- 合成分 ≠ GSM8K ≠ TMLR；本任务结论**只在本任务 + 本 verifier + 本步数**下解释。
- 不宣称原 p2 写作偏好 adapter 的能力提升（那是另一个任务、另一份数据）。
- 不宣称"权重杠杆普遍有效"——单次合成任务，样本 60 题，是**存在性读数**不是效应量估计。
- 若 NO_GAIN / REGRESSION，如实报（不是失败，是"在这个可学信号上这一步没起作用"）。
- token/显存/墙钟是测量不是成本；不做 token→成本换算。