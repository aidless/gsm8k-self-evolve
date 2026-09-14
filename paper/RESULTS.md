# RESULTS — 全链结果与诚实边界

> 本文件把 Round 1–4 的结果按"门控三方向"组织：真增益被接受、负结果被拒绝、无增益被拒绝。
> 结论段（C11–C13）是 **inconclusive**，而非"自进化有效/无效"的强断言。
> 所有数字可从 `results/`、`registry/version-registry.json`、`signed/bundle.json` 重算。

## 0. 题目集来源（2026-09-12 核验，C21）

`examples/{gsm8k40,heldout40,heldout-batch2-160}.json` 共 240 题，经
`tools/verify_question_provenance.py` 逐题核对：

| 项 | 结果 |
| --- | --- |
| 与官方 GSM8K **test** split（n=1319）逐字匹配 | **240 / 240** |
| 与官方 GSM8K **train** split（n=7473）重叠 | **0**（无污染） |
| 在 test split 中的位置分布 | 均匀散布：mean 644.7（均匀期望 659.0），四分位 344/630/947，前半 126 / 后半 114，非连续块 |

即：这些题目**不是自造**，而是标准 GSM8K test 原题，且与训练集零重叠——数字因此可与
GSM8K 文献口径对话。范围说明：仅覆盖 1319 题中的 240 题子集，**不可**称"完整 GSM8K test 分数"。
GSM8K 的 MIT 归属见 `THIRD_PARTY_NOTICES.md`（C22）。

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

## 3b. Track C — 跨模型验证（2026-09-12，n=40 × 3 模型）

按 `PREREG-round4.md` 第 15–16 行设计，在另外 3 个模型族上重跑同一门控：

| 模型（族） | direct | step-calc | concise-reason | cot-zero | few-shot |
| --- | --- | --- | --- | --- | --- |
| qwen2.5:7b（阿里）· n=200 合并盲集 | .135 | .920 | — | .930 | .895 |
| gemma3:4b（谷歌） | .025 | .850 | .775 | **.900** | .450 |
| qwen2:7b（阿里） | .050 | .875 | **.925** | .850 | .850 |
| llama3.1:8b（Meta） | .000 | .900 | .875 | **.950** | .700 |

Headline 配对（精确 McNemar）：

| 配对 | qwen2.5:7b | gemma3:4b | qwen2:7b | llama3.1:8b |
| --- | --- | --- | --- | --- |
| step-calc vs cot-zero | p=0.804 | p=0.500 | p=1.000 | p=0.500 |
| step-calc vs concise-reason | p=1.08e-06（Round-2, n=200） | p=0.453 | p=0.688 | p=1.000 |

扩展判定：三个新模型 p 均 ≥ 0.45（>0.2）→ 按预注册 weak-signal 规则均不扩展。

来源：`trackC-*-heldout40.json`（`scripts/summarize_trackC.py` 重算并断言一致）；
完整判定见 `ROUND4-TRACKC-RESULT.md`。

## 4. 结论（诚实，含边界）

- **C10（fail-closed）成立**：门控在三个方向上行为正确——接受真增益(p=1.08e-06)、
  拒绝负结果(round3 p=1.0)、拒绝无增益(round4 p=0.80/0.40)。
- **C11 成立**：`step-calc` 与标准零样本 CoT **统计不可区分**（n=200）。
- **C12（caveated）成立**：0.125 → 0.925 的跳跃，**主要来自 `direct` → CoT 式提示**那一跳
  （direct 27 vs cot-zero 186，gain +0.795）；`step-calc` 相对 `cot-zero` 无独特增量。
  早先 Round-2 的对照基线 `direct`（number-only）是 weak strawman，未包含 cot-zero。
- **C13 成立**："无显著差异"**不是**"证明等价"——未预注册等价边际，n=200 对 ±2 题效应功效不足，
  temperature 0 无种子控制、单次运行。**禁止**把本结论演绎为"自进化无效"。
- **C17 成立**：`step-calc` 相对 `cot-zero` 无显著优势，**4 个模型一致**（p=0.804/0.500/1.000/0.500）。
- **C18（caveated）成立**：Round-2 的自进化增益（step-calc ≫ concise-reason）在 3 个新模型上**均未复现**
  （p ≥ 0.45，方向不一致）。n=40 功效不足，故只报"未复现"，不报"不存在"。
- **C19 成立**：唯一稳健的正效应是「CoT 式提示 ≫ 纯数字作答」，跨 4 个模型 p ≈ 1e-9…1e-48。
- **C20 成立**：fail-closed 门控在 4 个模型上行为一致（3 个新模型全部拒绝、均不扩展）。

## 5. 运行间方差（2026-09-12，C23/C24）

3 次重复、360 次调用（qwen2.5:7b, heldout40, `{step-calc, cot-zero, concise-reason}`）：

| 策略 | rep1 | rep2 | rep3 | 极差 |
| --- | --- | --- | --- | --- |
| concise-reason | .850 | .850 | .850 | 0.000 |
| cot-zero | .950 | .950 | .950 | 0.000 |
| step-calc | .900 | .925 | .925 | 0.025 |

- **显著性判定翻转的配对数 = 0**：step-calc vs cot-zero（p=.625/1.00/1.00）、
  vs concise-reason（p=.500/.250/.250）三轮均不显著。
- 跨环境差异同量级：同模型同 40 题，云端 cot-zero 39/40 vs 本地 38/40（差 1 题）。
- 故单次 40 题结果只应在 **±0.025–0.05** 内解读；定性结论稳健。
- 完整记录：`ROUND4-VARIANCE.md`；复算：`scripts/variance_report.py`。

## 6. 决策规则消融（2026-09-12，新颖性 head-to-head，C25–C30）

**问题**：门控的"拒绝假增益"能力，到底来自哪一步？我们把晋升决策抽象成 7 种**决策程序**
（R1–R7，`PREREG-round5.md` §2），在**同一批置换零**上比较它们的假阳性率（FPR）。
置换零的构造：对真实配对池的 `d` 道 discordant 题**逐题独立**以概率 0.5 交换 challenger/incumbent
标签，真处理效应恒为 0 而 discordance 结构保留；`SEED=20260912`，每源池 200 个零、共 4 源池 × 200 = 800 零
（`PREREG-round5.md` §1）。**零模型调用**：全部数字由 `scripts/ablation_gate.py` 从
`results/rounds/round5/pools.json` 重算。

| 规则 | 语义（简化） | 假阳性 FPR（800 零池） |
| --- | --- | --- |
| **R1 `gate`** | **本工作五键门控**（盲配对精确 McNemar p<0.05 **且** gain≥0.02，α=0.05, ε=0.02, 盲集） | **10 / 800 = 0.0125** |
| R2 `point` | 仅 `gain > 0`（无任何检验） | 330 / 800 = 0.4125 |
| R3 `unpaired` | 非配对两比例检验 p<0.05 且 gain≥0.02 | 12 / 800 = 0.015 |
| R5 `loose` | 门控但 α=0.20 | 33 / 800 = 0.04125 |
| R6 `no-stat` | 保留 gain≥ε=0.02、去掉显著性检验（AMENDMENT 1 语义） | 217 / 800 = 0.27125 |
| **R7 `bestofk`@8** | k=8 个候选取点估计最优即晋升（选择压力） | **786 / 800 = 0.9825** |

**判定分支 = (i)「门控价值成立」**（`ablation.json` `verdict_branch="i"`，`verdict_meaning="gate value established"`）：

- **(a) Wilson 95% 区间不重叠且 R1 在下方**（保守描述界）：WilsonUpper95(R1) = 0.0228557… <
  WilsonLower95(R2) = 0.3788842…，且 < WilsonLower95(R7@8) = 0.9708409…。
- **(b) 同一批 800 零池上的配对精确 McNemar 一致**（操作性校验，配对单位 `(source_pool, null_index)`）：
  R1 vs R2 → better=0, worse=320 ⇒ **p = 2⁻³¹⁹ ≈ 9.3634e-97**；
  R1 vs R7@8 → better=0, worse=776 ⇒ **p = 2⁻⁷⁷⁵ ≈ 5.0321e-234**。四个源池方向全一致。
- **(c) R1 不掉真阳（sanity guard）**：TPR = 1/1（POSITIVE 分母 = 1，**无鉴别力**，
  不得据此声称 R1 在 TPR 上优于 R2/R7；该款仅防空转，见下）。

**诚实边界（必须随正文披露）：**

1. **零来自 relabelling、非独立抽样**：同一源池的 200 个置换零共享该池的题目，不是独立 Bernoulli 试验。
   Wilson 区间只是**保守的描述界**，不是独立性假设成立下的推断；操作性结论由**配对 McNemar**承载
   （`ablation.json` `verdict.null_set.independence_note`，`PREREG-round5.md` §5.1 独立性保障）。
2. **R4 是定义性对照，非发现，且无 R4 FPR**：R4 = 在选择集（非盲）上计算配对检验。六个非盲选择集池
   上 R1 **按定义**拒绝全部（要求 `blind=True`），R4 晋升 2/6——这是门控盲约束的定义后果，分母 6，
   **不读作泛化发现**；无非盲零集，故不声称任何 R4 FPR。
3. **TPR 分母 = 1**：POSITIVE 池仅 1 个（cot-zero vs direct），每条规则的 TPR 都是单次 0/1 决定；
   clause (c) 是防空转 sanity guard，`no_discriminating_power=true`。
4. **比较的是决策程序，不是相关系统本身**：R1–R7 是与相关工作（REMO/SPHERE/TextGrad 等）公开描述一致的
   *idealised* 决策程序重实现，**不运行、不声称复现或击败任何系统**（`PREREG-round5.md` Global Constraints）。
5. R2 的 FPR 期望 = `(1 − P(tie))/2`（构造使然，非发现）；pooled 期望 0.43639（按各池 `d` 加权，
   `ablation.json` `pooled_r2_null_expectation`），观测 0.4125 与之同量级，符合"无错误控制"的定义。

**一句话定位**：本工作证明了一套**fail-closed 的审计门控**能诚实地区分真增益与假增益/无增益，
并在此过程中（i）发现其自身进化产物未显著超越标准 CoT 基线——一个**被诚实复现的边界结果**，
（ii）用同条件决策规则消融**实测**了该门控的拒绝能力来源（FPR 0.0125 vs 0.4125 vs 0.9825，
McNemar p<1e-96）——而非自我声明——因此它不是一个被夸大的 SOTA 声称。
## 7. 提议器替代臂（Task 6，2026-09-14，新一代骨干，C31）

**问题**：门控的结论是否与提议器解耦？把「文本批判式提议器」的产物（TextGrad/Reflexion 风格：
对 cot-zero 输出按批判提示词反思改写）与其余 4 个策略同池、同指标比较，headline = 提议器产物 vs
零样本 CoT（`PREREG-round5.md` §6；骨干变更见 `AMENDMENT-2-task6-backbone.md`）。

**骨干与环境**：Qwen3.8-27B 的 AWQ-INT4 量化（自托管 vLLM，新一代骨干），heldout40（盲），温度 0，
2 重复 = 400 调用（`results/rounds/round5/proposer-arm-qwen38-27b.json`）。**零本机模型调用**，
全程在远端算力上完成。

| 策略 | passed（n=40）rep1 / rep2 |
| --- | --- |
| `direct`（纯数字） | 1 / 1 |
| `step-calc` | 13 / 13 |
| `cot-zero`（标准零样本 CoT） | 14 / 14 |
| `few-shot` | 12 / 14 |
| `textgrad`（文本批判提议器产物） | 13 / 13 |

**headline**（`textgrad` 为 challenger、`cot-zero` 为 incumbent，§1.1 方向）：b=0、c=1、
精确 McNemar **p=1.0**、gain=−0.025 —— **提议器产物不优于零样本 CoT**。

**重复一致性**：200 单元格中 **198 一致**；headline 对在两次重复中 **100% 一致**；唯一差异是
few-shot 的 2 格（held-03 / held-09），与 §5 方差节的近确定性一致。

**诚实边界（随正文披露，不省略）：**
1. **单一骨干**——这是「结论在 27B 上复现」的单次观察，不构成"跨新一代模型都成立"的推广；
   27B 与 Track A/C 的 7B/4B/8B 混淆了代际与规模，**不可数值比**。
2. **AWQ-INT4 量化是仪器的一部分**（自托管压缩权重 ≠ 厂商全精度）。
3. 被平台政策叫停的 `qwen2.5:7b` 部分跑（263/400）**不可引用**，仅作审计痕迹保留（未提交）。

**一句话定位**：主结论（CoT 式提示 ≫ 纯数字 = 1 vs 12–14）与 headline（提议器产物 ≈ 标准 CoT）在
**新一代 27B 骨干上复现**——门控的结论不随提议器类型与骨干代际而变。
