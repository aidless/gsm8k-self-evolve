# Round 4 — Track C 判定记录（跨模型验证）

- 日期：2026-09-12
- 分支：`main`（自 round4-true-claims 合入后）
- 预注册：`results/rounds/round4/PREREG-round4.md` 第 15–16 行（Track C：多模型 × heldout40，
  headline = step-calc vs concise-reason 与 step-calc vs cot-zero，扩展规则 p<0.2 且 |gain|≥0.02）
- 设计偏离声明：预注册写 `llama3.1:8b via ollama pull`；本机 6 GB 显存可容纳其 Q4，
  已按预注册拉取并成功运行，**未启用 fallback**（`qwen2:7b` 作为额外第二个模型族一并运行，
  属加法、非替代）。

## 1. 四模型结果（heldout40，n=40，temperature 0）

| 模型（族） | direct | step-calc | concise-reason | cot-zero | few-shot |
| --- | --- | --- | --- | --- | --- |
| qwen2.5:7b（阿里）· n=200 合并盲集 | .135 | .920 | — | .930 | .895 |
| gemma3:4b（谷歌） | .025 | .850 | .775 | **.900** | .450 |
| qwen2:7b（阿里） | .050 | .875 | **.925** | .850 | .850 |
| llama3.1:8b（Meta） | .000 | .900 | .875 | **.950** | .700 |

来源：`trackC-gemma3-4b-heldout40.json`、`trackC-qwen2-7b-heldout40.json`、
`trackC-llama31-8b-heldout40.json`；qwen2.5:7b 行来自 `trackA-merged.json`（n=200，非同一集合，
仅作方向对照，**不可跨集做显著性比较**）。

## 2. Headline 配对（逐模型，精确 McNemar）

| 配对 | qwen2.5:7b (n=200) | gemma3:4b | qwen2:7b | llama3.1:8b |
| --- | --- | --- | --- | --- |
| step-calc vs cot-zero | p=0.804, +0.010 | p=0.500, +0.050 | p=1.000, −0.025 | p=0.500, +0.050 |
| step-calc vs concise-reason | （Round-2 记为 33:4, **p=1.08e-06**, +0.145） | p=0.453, −0.075 | p=0.688, +0.050 | p=1.000, −0.025 |

**扩展判定**：三个新模型上两个 headline 配对的 p 均 ≥ 0.45（>0.2），
按预注册 weak-signal 规则**均不扩展**到 batch2-160。

## 3. 三条可复现的跨模型结论

1. **`step-calc` 相对 `cot-zero` 无显著优势——4 个模型全部一致。**
   p = 0.804 / 0.500 / 1.000 / 0.500。这是本工作最强的跨模型不显著结果，方向也一致（|gain| ≤ 0.05）。
2. **Round-2 的"自进化增益"（step-calc ≫ concise-reason）未在其它模型复现。**
   在 gemma3:4b / qwen2:7b / llama3.1:8b 上分别为 −0.075 / +0.050 / −0.025（p ≥ 0.45），
   方向不一致。该增益在 qwen2.5:7b（演进所用模型）上是 p=1.08e-06。
3. **唯一稳健的正效应是「CoT 式提示 ≫ 纯数字作答」。**
   `direct` vs 任一 CoT 式策略在所有 4 个模型上均 p ≈ 1e-9…1e-48、gain +0.70…+0.95。
   即：早期 Round-2 叙事里的"0.125→0.925 提升"，跨模型看来自 `direct`→CoT 那一跳，与自进化机制无关。

附：`few-shot` 跨模型不稳定（.450/.850/.700/.895），在 gemma3:4b 与 llama3.1:8b 上显著劣于 `cot-zero`。

## 4. 门控性质在跨模型上被再次验证（C10 扩展）

在 3 个新模型上重跑同一 fail-closed 门控，结果全部为**拒绝**（headline gate FAIL、不扩展），
即门控没有在任何新模型上把"不显著差异"误判成"提升"。这使 C10 从"单模型三方向"升级为
"4 模型 × 三方向"的行为一致性证据。

## 5. 诚实边界（不可过度演绎）

- **n=40 功效不足**：三个新模型均为 40 题，对 ±0.05~0.15 的效应功效有限。
  "未复现"≠"证明不存在"；PREREG 的扩展规则本就要求出现 weak signal（p<0.2）才加大样本，
  而实测 p 均 ≥0.45，故按预注册不再投入。
- **非同集合比较**：qwen2.5:7b 行为 n=200 合并集，与三个 n=40 集**不可跨集做显著性比较**，
  仅作方向性对照。
- temperature 0、单次运行、无种子控制（与 Rounds 1–4 同一局限）。

## 6. 未做

- Track B（transfer：SVAMP / MultiArith / ASDiv）未运行。
  **设计提示（重要）**：PREREG 第 14 行的 Track B 成功规则只与 `direct` 对照，
  而本 Track C 已证明 `direct` 是稻草人基线；若运行 Track B，应**同时加入 `cot-zero` 对照**
  才能区分"step-calc 好"与"任何 CoT 式提示都好"。这属于对冻结预注册的**修订**，
  执行前必须显式披露该修订，不可静默偏离。