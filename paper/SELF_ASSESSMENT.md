# SELF_ASSESSMENT — TMLR 四维加权自评

> 方法：TMLR 四维（Novelty / Soundness / Significance / Clarity）4 分制，
> 加权 0.30N + 0.35S + 0.25Si + 0.10C。纪律：**无证据不给 4 分**；
> 本自评的字面诚实优先于"显得能投中"。
> 结论：这是"可投但需再补一轮实验"的水平，不是"稳中"的水平。

## 逐维打分

### Novelty（新颖性）— 2 / 4

- 单组件均非新：配对 McNemar、Ed25519 签名、append-only registry、rollback 均为成熟工具。
- 边际新颖在于**组合**：把上述组件串成一个 fail-closed 的"五键晋升门"，并用
  **三个方向的负/正结果**（C10）证明其行为正确。
- 不给 3 分的原因：vs 已有自进化/自验证工作（`RELATED_WORK.md` 的 REMO/SPHERE/TextGrad）
  的差异化目前是**自我声明**的"Adjacent 差一句话"，未经独立评审确认，不能自封新颖。

### Soundness（严谨性）— 3 / 4（最强维度）

- 所有数字可由仓库文件重算：`verify_evidence_chain.py` 5/5、`merge_trackA.py` 重跑一致、
  ledger 恒等式三处强制执行、发布门禁 5/5。
- 统计方法具体且正确：配对精确 Binomial McNemar（非卡方近似），配对单位 = 同题同配置。
- 有冻结预注册（round4 PREREG），有诚实边界披露（self-signed、toy 规模、n=200 功效、
  temperature 0 无种子）。
- **更正（2026-09-12）**：原"扣 1 分"理由写的是"盲集是自建 200 题，不是标准 GSM8K test split"。
  该说法**未经验证即假设**，经 `tools/verify_question_provenance.py` 核验后**撤回**：
  240 题逐字为官方 GSM8K test 原题（240/240），与 GSM8K train **零重叠**（无污染），
  且在 test split 中**均匀散布**（mean 644.7 vs 均匀期望 659.0；前后半 126/114），非有偏取样。
  该理由不成立，属自评中的事实性错误。
- 扣 1 分的**实际**原因（更正后）：**所有 headline 数字为单次运行，run-to-run 方差未量化**
  （README 记录 40 题单次运行曾观测 0.65→0.75 漂移；temperature 0 且无种子控制）；
  且评估只用 1319 题 test split 中散布的 240 题子集，绝对准确率不可跨子集比较。
- 注：题目来源的澄清使数字**可与 GSM8K 文献口径对话**（标准原题而非自造），
  这是证据质量的实质提升；但因上述残余短板仍在，Soundness 仍保守给 3，不上调。

### Significance（重要性）— 3 / 4

- 正贡献是一个**面窄但可证伪**的审计门控框架，对"可复现的自改进"方向有增量价值。
- 负结果（自进化产物 ≈ cot-zero）有记录价值。
- **Track C（2026-09-12）在 3 个新模型族上重跑同一门控**：fail-closed 行为一致
  （headline gate 全部拒绝、均不扩展），且「step-calc 不优于 cot-zero」在 4 个模型上一致
  （p=0.804/0.500/1.000/0.500）——结论不再受"仅单模型"质疑。
- 仍不给 4 的原因：未在公开基准（Track B / 标准 GSM8K test split）上验证迁移；
  影响力上限受"自建集 + 提示级自进化"限制。

### Clarity（清晰性）— 3 / 4

- README / METHOD / RESULTS / CLAIM_LEDGER / RELATED_WORK 结构清楚，诚实边界显式标注，
  每条声明可回溯到 `文件:行`。
- 不给满 4 的原因：尚未合并成单一投稿稿（无 abstract / intro / related-work 严格区分
  学术版式），当前为"仓库级重建"而非"论文级成稿"。

## 加权分

```
0.30×2 + 0.35×3 + 0.25×3 + 0.10×3 = 2.70 / 4      （2026-09-12，Track C 后）
```

（上一次，Track C 前：`0.30×2 + 0.35×3 + 0.25×2 + 0.10×3 = 2.45`）

## 提分路径（把 2.70 推到 3.0+ 需要做的事，均需真实证据）

0. **量化 run-to-run 方差（当前最高性价比）**：关键配对（step-calc vs cot-zero 等）
   在相同题目上重复 ≥3 次运行，报出运行间方差与合并区间。这直接消掉 Soundness 的
   残余短板（可能 S→4，加权 →3.05）。成本最低（本机可跑，约 1–2 h）。
1. ~~补 Track C（多模型）~~ **已完成（2026-09-12）**：gemma3:4b / qwen2:7b / llama3.1:8b 三个模型族跑完，
   fail-closed 行为一致、"不优于 cot-zero"跨 4 模型成立 → **Si 已由 2 升至 3**。
2. ~~核实题目来源~~ **已完成（2026-09-12）**：C21 证明 240 题为官方 GSM8K test 原题、
   零 train 污染、均匀散布；C22 补齐 GSM8K MIT 归属。原"自建集"扣分理由撤回（见上）。
3. **补 Track B（泛化集）**：在 SVAMP/MultiArith/ASDiv 上验证 transfer。**注意**：PREREG 第 14 行
   的 Track B 只与 `direct` 对照，而 `direct` 已被证明是稻草人基线；运行前必须**显式修订预注册
   并加入 `cot-zero` 对照**，否则结果无信息量。本机可跑但耗时（约 8 h），当前机器有内存压力，
   建议另择时机。
4. **独立新颖性论证**：与 REMO/SPHERE/TextGrad 做**同条件 head-to-head 门控对比**，
   把 N 的"自我声明 Adjacent"升级为"实测差异化"（可能 N→3）。