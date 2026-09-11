# Round 4 — Track A 判定记录（true-baseline comparison）

- 日期：2026-09-11（测量）+ 2026-09-12（判定记录）
- 分支：`round4-true-claims`
- 预注册：`results/rounds/round4/PREREG-round4.md`（冻结，2026-09-11）
- 数据源：`trackA-heldout40.json`（n=40）+ `trackA-batch2-160.json`（n=160），合并为 `trackA-merged.json`（n=200，纯 recompute，无模型调用）
- 后端：qwen2.5:7b，temperature 0（与 Round 1–3 一致）

## 1. 结果（n=200，逐题配对，四策略）

| 策略 | 正确数 | 正确率 | 平均延迟(s) |
| --- | --- | --- | --- |
| `direct` | 27 | 0.135 | 3.307 |
| `step-calc`（稳定 incumbent，A 线自进化产物） | 184 | 0.920 | 8.869 |
| `cot-zero`（零样本 CoT 基线） | 186 | 0.930 | 10.505 |
| `few-shot`（冻结 4-shot 基线） | 179 | 0.895 | 11.938 |

## 2. Headline 门禁（预注册第 10 行，逐条）

| 配对 | better | worse | McNemar p（双侧精确） | gain | lat_ratio | 判定 |
| --- | --- | --- | --- | --- | --- | --- |
| step-calc vs cot-zero | 9 | 7 | 0.803619 | +0.010 | 1.184 | **不显著 → gate FAIL** |
| step-calc vs few-shot | 9 | 14 | 0.404873 | −0.025 | 1.346 | **不显著 → gate FAIL** |

门禁条件：p < 0.05 **且** gain ≥ 0.02 **且** lat_ratio ≤ 2.0。两对均不满足 p < 0.05，故均为 FAIL。

## 3. 判定：outcome (iii) — inconclusive

按 PREREG 第 11 行的三项穷尽判定：

- (i) step-calc **同时通过**两个 headline gate → 未发生（两对 p 均 > 0.05）。
- (ii) step-calc 在 p < 0.05 下**显著输给**任一基线 → 未发生（p=0.80 / p=0.40，均不显著）。
- (iii) **neither → inconclusive，记录，不改故事线** → **本判定**。

结论：**无证据表明 step-calc 显著超越或显著劣于标准 CoT / few-shot 基线。**

## 4. 关键诚实发现（本轮的真正价值）

- `direct`（number-only）与任一 CoT 式策略（step-calc / cot-zero / few-shot）之间是**巨大且显著**的差距（p ≈ 1e-47…1e-42）。
- 但 step-calc 与 cot-zero / few-shot 之间**统计不可区分**。
- 因此，README Round-2 报告的 `step-calc` 0.925 的增量，**主要可归因于 `direct → CoT 式提示` 那一跳，而非"评分门控自进化"本身产生了超越标准 CoT 基线的独特增量**。A 线早先的对照基准 `direct`（number-only）是一个相对弱的稻草人基线，未包含 cot-zero 这一标准对照。

## 5. 诚实边界（不可过度演绎）

- "无显著差异"不是"证明等价"。等价性检验需预注册的等价边际和/或更大样本；本实验 n=200 对检测小效应（如 ±2 题）功效不足，**未预注册等价性**。
- 本结论仅在本机 qwen2.5:7b、该盲集、temperature 0、单次运行条件下成立；不推广到更强模型或其它任务。
- temperature 0 且 Ollama 无种子控制，单次运行含不可控噪声，与 Round 1–3 同一局限（PREREG 第 17 行）。

## 6. 未做（预注册后续，需资源确认）

- Track B（泛化/transfer：SVAMP / MultiArith / ASDiv，runtime-fetch，≈8h）
- Track C（多模型：gemma3:4b / llama3.1:8b 等，验证结论是否随模型迁移）
- 本轮 Track A 仅回答"是否真超越标准提示基线"——答案为 inconclusive（否）。