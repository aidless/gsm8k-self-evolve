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
- 扣 1 分的原因：盲集是**自建 200 题**，不是标准 GSM8K test split；Track B（泛化集）与
  Track C（多模型）**未做**，transfer 与跨模型稳健性无证据。这是真实短板，不能忽视。

### Significance（重要性）— 2 / 4

- 正贡献是一个**面窄但可证伪**的审计门控框架，对"可复现的自改进"方向有增量价值。
- 负结果（自进化产物 ≈ cot-zero）有记录价值，但负结果的影响力天然受限；
  且仅在本机单模型成立，迁移性未知。
- 不给 3 分的原因：没有展示该门控在**其它代理/任务/模型**上依然有价值的证据。

### Clarity（清晰性）— 3 / 4

- README / METHOD / RESULTS / CLAIM_LEDGER / RELATED_WORK 结构清楚，诚实边界显式标注，
  每条声明可回溯到 `文件:行`。
- 不给满 4 的原因：尚未合并成单一投稿稿（无 abstract / intro / related-work 严格区分
  学术版式），当前为"仓库级重建"而非"论文级成稿"。

## 加权分

```
0.30×2 + 0.35×3 + 0.25×2 + 0.10×3 = 2.45 / 4
```

## 提分路径（把 2.45 推到可投线 3.0+ 需要做的事，均需真实证据）

1. **补 Track C（多模型）**：在 ≥2 个其它模型族（如 gemma3:4b / llama3.1:8b / qwen3:14b）
   重跑门控三方向，证明"fail-closed 随模型迁移"→ 直接拉 Si（可能到 3）。
2. **补 Track B（泛化集）**：在 SVAMP/MultiArith/ASDiv 上验证 step-calc 的 transfer，
   把 S 的"自建 200 题"短板补上（可能 S→4）。
3. **标准集对齐**：把盲集换/扩到标准 GSM8K test split 出可比分数，消除"自建集"质疑。
4. **独立新颖性论证**：与 REMO/SPHERE/TextGrad 做**同条件 head-to-head 门控对比**，
   把 N 的"自我声明 Adjacent"升级为"实测差异化"（可能 N→3）。

前两项正是原 PREREG-round4 已冻结但未执行的 Track C/B——它们是**已设计好的下一步**，
不是新的空想。是否继续投入云端算力（48G 卡 / 14b~35b 权重已在盘），取决于你是否要走"真投递"这一档。