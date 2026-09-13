# Round 4 — Track B transfer record (frozen step-calc vs direct)

- 日期：2026-09-13（测量）+ 记录；分支 `round4-true-claims`。
- 后端：qwen2.5:7b，temperature 0（与 Round 1–4 一致，含 Track A）。
- 策略：`direct`（number-only）与冻结的 `step-calc` 各 1 次，逐题配对，逐集断言 ledger。
- 预注册规则（PREREG-round4.md）：**step-calc beats direct with p < 0.05 on SVAMP-full AND gain > 0 on all three sets**。

## 结果

| 数据集 | direct | step-calc | better | worse | McNemar p | gain |
|---|---|---|---|---|---|---|
| svamp (1000) | 647 | 920 | 290 | 17 | 2.787e-65 | +0.273 |
| multiarith (180) | 87 | 180 | 93 | 0 | 2.019e-28 | +0.517 |
| asdiv (2249) | 1589 | 2026 | 502 | 65 | 1.220e-84 | +0.194 |

## 判定：**GENERALIZE（预注册规则触发）**

规则三条件：
1. SVAMP-full `step-calc` 显著胜 `direct`：p = 2.787e-65 < 0.05 ✅
2. 三集 `gain > 0`：svamp +0.273、multiarith +0.517、asdiv +0.194 ✅
3. 结论：**step-calc 对 direct 的优势在三个外部算术词题集上泛化。**

## 诚实边界（不可过度演绎 —— 本判定不改变 Round-4 核心结论）

1. **这是 step-calc vs `direct`（number-only 稻草人基线），不是 vs 标准 CoT。**
   Track A 已证明 `step-calc ≈ cot-zero`（p=0.80，null）。本记录只表明：
   "CoT 式提示对 number-only 提示的优势，跨越 GSM8K / SVAMP / MultiArith /
   ASDiv 四个算术词题集复现"。这是预期内、已知的结论，**不是**自进化
   相对标准 CoT 的新增证据。自进化相对标准 CoT 的结论仍是 Track A 的
   inconclusive（无显著差异）。
2. ASDiv 抓取层排除 56 道非数值答案题（who/which/yes-no/颜色题，评估器为
   精确浮点相等，无法判分），保留 2249 道；排除清单见
   `inputs/asdiv.exclusions.json`。
3. 预算偏差：预注册写 ~6970 次调用，实际 (1000+180+2249)×2 = 6858 次，
   因 asdiv 排除 56 题而略低于预注册值。
4. 温度 0 但 Ollama 无种子控制，单次运行含不可控噪声（与 Round 1–4 同限）。
5. 数据集许可：输入集运行时下载、绝不入库（ASDiv CC-BY-NC-4.0；MultiArith
   许可不明），仅结果 JSON 入库。

## 数据源

- 结果 JSON：`transfer-svamp.json`、`transfer-multiarith.json`、`transfer-asdiv.json`（均有 ledger 断言）。
