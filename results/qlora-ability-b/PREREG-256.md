# 预注册：token 上限假设的可证伪实测（96 → 256）

**锁死时间**：2026-11-22T15:35:00Z（UTC，跑前）
**实例**：`j-rmovspv3vqzvrbutonoj5l2qsu`（root@36.150.116.206:35361，gfx1100 48 GiB，11-23 20:40Z 销毁）
**前置**：本笔记是「解析口径符号翻转」与「误差分型」两发的续发。上两发定位的混淆变量是 `max_new_tokens=96` 太短 + greedy 退化，但那只由文本形态启发式推断。本发把「token 上限」单独拎出来做干预实验。

## 唯一干预

- `cloud_eval.py` 的 `generate()` 里 `max_new_tokens` 从 **96 → 256**。
- 其余全部冻结：同一 base `Qwen/Qwen3-4B`、同一 SFT ckpt-136、同一 DPO adapter（sha `b5e8ff39193247ce8e61f3b18724e13ff1dd8102506c8983959836086a089db9`）、同一 heldout 60 题、同一 `do_sample=False` greedy、同一生成逻辑代码（云上 sha `1c30115e…` 与本地一致）。
- 两组都跑：base+SFT 与 base+DPO（DPO 不叠 SFT，`adapter = dpo or sft`）。
- 输出落到新目录 `eval-256/generations_{sft,dpo}.json`，**不覆盖** 96 的原产物。

## 跑前锁定的 96 基线（来自已落盘产物，不改）

| 指标 | SFT | DPO | 来源 |
|---|---|---|---|
| `L1_manifest` | 60 | 60 | error_taxonomy.json |
| `L2_scorable` | 48 | 51 | 同上 |
| `L3_heuristic_excluded` | **12** | **9** | 同上 |
| `NOANS_TRUNCATED_MIDSTEP` | **11** | 1 | 同上 |
| `NOANS_DEGENERATE` | 0 | **3** | 同上 |
| `NOANS_COMPUTED_BUT_UNFORMATTED` | 1 | 5 | 同上 |
| last_int 口径 | 26/60 | 34/60 | ability_report.json |
| first/last_answer 口径 | 45/60 | 35/60 | parser_sensitivity.json |
| `symbol_consistency` | UNSTABLE（两组共享） | UNSTABLE（两组共享） | parser_sensitivity.json |

## 判据（跑前锁定，事后不得改）

把 L3 拆成两个机制假设，各自可证伪：

- **H_token（token 上限假设）**：截断题是 96 token 不够写完所致。若成立，`NOANS_TRUNCATED_MIDSTEP` 在 256 下必须从 **SFT 11 → ≤3**（降幅 ≥8），且 SFT 的 `L3` 从 **12 → ≤4**。
- **H_greedy（贪心退化假设）**：退化题是 `do_sample=False` 陷入重复/Unicode 下标循环，加 token 也救不回。若成立，DPO 的 `NOANS_DEGENERATE` 在 256 下仍 **≥2**（不塌缩）。

三态判决（由上面两条的真假组合机械决定，不看数字大小调阈值）：

- `TOKEN_LIMIT_DOMINANT`：H_token 成立 **且** H_greedy 不成立 → 截断塌缩、退化不塌缩，token 上限是截断主因，退化是另一路问题。
- `MIXED`：两条都成立或部分成立 → 两个机制并存，按实际分型迁移矩阵如实报。
- `NEITHER`：H_token 不成立 → 加 token 救不回截断，说明截断另有原因（如 prompt/解码），token 上限不是主因。

**符号稳健性**（独立记录，不影响上面三态）：256 下重跑 `parser_sensitivity` 六口径，记 `symbol_consistency`。若仍 `UNSTABLE`，则确认「单口径报 GAIN 不可信」这个结论跨 token 预算稳健；若翻成 `STABLE`，如实报并标注只在一个 token 预算下成立。

## 诚实边界（写进报告）

1. **这是存在性/机制 probe，不是能力结论**：60 题、单一合成任务 `(A*B+C) mod M`，L3 塌缩只说明「测得全」，不等于「模型算术变强」。
2. **无 `finish_reason`**：generations 只有 `{id,answer,text}`，「截断/退化」仍是文本形态启发式（`NOANS_*` 一律 `heuristic=True`），没有解码器停止原因佐证。本发不假装解决这个归因瑕疵。
3. **不改现有口径/数字**：`ability_report.json` / `parser_sensitivity.json` / `error_taxonomy.json` 的 96 读数全部保留；256 产物单独落 `eval-256/` 与新诊断文件。
4. **实例有寿命**：destroy 11-23 20:40Z。若 256 两组没跑完，如实记 `INCOMPLETE`，不用旧产物补、不外推。

## 复现命令

```bash
# 云端（detached，引用冻结的云上路径）
cd /workspace/qlora-job/ability
nohup /opt/venv/bin/python cloud_eval.py \
  --base /workspace/models/Qwen3-4B \
  --sft  /workspace/qlora-job/sft/checkpoint-136 \
  --dpo  /workspace/qlora-job/ability/out/adapter_model.safetensors \
  --heldout /workspace/qlora-job/ability/synth_heldout.jsonl \
  --out-dir /workspace/qlora-job/ability/eval-256 \
  --max-new-tokens 256 > eval-256.stdout 2>&1 &

# 本地（拉回后）
python3 scripts/token_budget_probe.py --dir results/qlora-ability-b/eval-256 \
  --baseline results/qlora-ability-b/error_taxonomy.json \
  --out results/qlora-ability-b/token-budget-256.json
```
