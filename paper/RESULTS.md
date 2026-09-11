# RESULTS — 全链结果与诚实边界

> 本文件把 Round 1–4 的结果按"门控三方向"组织：真增益被接受、负结果被拒绝、无增益被拒绝。
> 结论段（C11–C13）是 **inconclusive**，而非"自进化有效/无效"的强断言。
> 所有数字可从 `results/`、`registry/version-registry.json`、`signed/bundle.json` 重算。

## 1. 门控接受真增益：Round 1–2（晋升 stable）

后端 qwen2.5:7b, temperature 0。配对口径精确 McNemar。

| 阶段 | 对比 | 准确率 | better : worse | McNemar p | 判定 |
| --- | --- | --- | --- | --- | --- |
| round1 (train 40) | `direct` → `concise-reason` | 0.15 → 0.65 | 20 : 0 | 1.9e-06 | provisional |
| round2 (train 40) | `concise-reason` → `step-calc` | 0.75 → 0.95 | 9 : 1 | 0.022 | provisional |
| **盲留出 200 合并** | `concise-reason` → `step-calc` | **0.780 → 0.925** | **33 : 4** | **1.08e-06** | **stable** |

来源：`bundle.json` `heldout_evidence`；`version-registry.json` `eecacc0312d7` stable evidence；
账本恒等式 185−156 = 33−4 = 29 成立（`verify_evidence_chain.py:101`）。

## 2. 门控拒绝负结果：Round 3（STOP，incumbent 保持 stable）

来源：`version-registry.json` history 的 `provisional-rejected`；`results/rounds/round3/`。

| 挑战者 | 分数 | better : worse | McNemar p | gain | 结论 |
| --- | --- | --- | --- | --- | --- |
| `reflect-retry` | 36/40 | 1 : 1 | 1.0 | 0.0 | gate fail |
| `textgrad-prompt` | 37/40 | 2 : 1 | 1.0 | 0.025 | gate fail |

两个挑战者均未达 p < 0.05 → 不晋升，`step-calc` 保持 stable。门控正确拒绝了把随机波动当提升。

## 3. 门控拒绝"无增益"：Round 4 真基线对照（inconclusive）

预注册：`results/rounds/round4/PREREG-round4.md`（冻结）。n=200 合并盲集，逐题配对四策略。

| 策略 | 正确数 | 正确率 |
| --- | --- | --- |
| `direct` | 27 | 0.135 |
| `step-calc`（incumbent） | 184 | 0.920 |
| `cot-zero`（零样本 CoT） | 186 | 0.930 |
| `few-shot`（冻结 4-shot） | 179 | 0.895 |

Headline 门禁（p < 0.05 且 gain ≥ 0.02 且 lat_ratio ≤ 2.0）：

| 配对 | better : worse | McNemar p | gain | 判定 |
| --- | --- | --- | --- | --- |
| step-calc vs cot-zero | 9 : 7 | 0.8036 | +0.010 | gate FAIL（不显著） |
| step-calc vs few-shot | 9 : 14 | 0.4049 | −0.025 | gate FAIL（不显著） |

来源：`trackA-merged.json`（`scripts/merge_trackA.py` 纯 recompute，重跑一致）。

## 4. 结论（诚实，含边界）

- **C10（fail-closed）成立**：门控在三个方向上行为正确——接受真增益(p=1.08e-06)、
  拒绝负结果(round3 p=1.0)、拒绝无增益(round4 p=0.80/0.40)。
- **C11 成立**：`step-calc` 与标准零样本 CoT **统计不可区分**（n=200）。
- **C12（caveated）成立**：0.125 → 0.925 的跳跃，**主要来自 `direct` → CoT 式提示**那一跳
  （direct 27 vs cot-zero 186，gain +0.795）；`step-calc` 相对 `cot-zero` 无独特增量。
  早先 Round-2 的对照基线 `direct`（number-only）是 weak strawman，未包含 cot-zero。
- **C13 成立**："无显著差异"**不是**"证明等价"——未预注册等价边际，n=200 对 ±2 题效应功效不足，
  temperature 0 无种子控制、单次运行。**禁止**把本结论演绎为"自进化无效"。

**一句话定位**：本工作证明了一套**fail-closed 的审计门控**能诚实地区分真增益与假增益/无增益，
并在此过程中发现其自身进化产物未显著超越标准 CoT 基线——这是一个**被诚实复现的边界结果**，
而非一个被夸大的 SOTA 声称。