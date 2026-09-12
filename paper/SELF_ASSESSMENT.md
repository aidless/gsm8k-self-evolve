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
- 扣 1 分的原因：盲集是**自建 200 题**，不是标准 GSM8K test split；Track B（泛化集）**未做**，
  transfer 无证据。Track C（跨模型）已于 2026-09-12 完成（3 个新模型族，见下），
  跨模型稳健性已有证据，但"自建集"短板仍在，故仍不给 4。

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

## 提分路径（把 2.70 推到可投线 3.0+ 需要做的事，均需真实证据）

1. ~~补 Track C（多模型）~~ **已完成（2026-09-12）**：gemma3:4b / qwen2:7b / llama3.1:8b 三个模型族跑完，
   fail-closed 行为一致、"不优于 cot-zero"跨 4 模型成立 → **Si 已由 2 升至 3**。
2. **补 Track B（泛化集）**：在 SVAMP/MultiArith/ASDiv 上验证 transfer，把 S 的"自建 200 题"短板补上
   （可能 S→4）。**注意**：PREREG 第 14 行的 Track B 只与 `direct` 对照，而 `direct` 已被证明是
   稻草人基线；运行前必须**显式修订预注册并加入 `cot-zero` 对照**，否则结果无信息量。
3. **标准集对齐**：把盲集换/扩到标准 GSM8K test split 出可比分数，消除"自建集"质疑。
4. **独立新颖性论证**：与 REMO/SPHERE/TextGrad 做**同条件 head-to-head 门控对比**，
   把 N 的"自我声明 Adjacent"升级为"实测差异化"（可能 N→3）。

第 2–4 项是剩余的三个真实短板。第 2 项是本机可跑但耗时（约 8 h）；第 4 项需要先具备可比实现。