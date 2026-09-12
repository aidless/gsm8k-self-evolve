# METHOD — 可审计的自进化晋升门控

> A 线的可发表主体不是"我们进化出一个更强的 prompt"，而是"我们定义了一套**fail-closed 的门控**，使 prompt 策略的自进化晋升在每个环节都可由第三方从仓库文件重算"。
> 本文每个机制都给出可复算锚点（`文件:行`），对应 `CLAIM_LEDGER.md` 的 C1–C10。

## 问题域与对象

对象是 **prompt 策略**的评测门控自进化（非权重训练）：给定一个候选策略 `answer_policy`，
门控决定"是否晋升为 stable"。全部实验在本仓库可复算的后端上运行（qwen2.5:7b, temperature 0）。
一个策略的价值不是看单次准确率，而是看它在**配对**口径下相对 incumbent 是否带来**显著**增益。

## 机制 1：配对精确 McNemar（拒绝卡方近似）

统计引擎用**精确双侧二项检验**，不是 χ² 近似（`evokit/stats.py:3-8`）：

```
mcnemar_two_sided(better, worse) = min(1, 2 · Σ_{i=0..k} C(n,i) / 2^n),  k = min(better, worse), n = better + worse
```

配对单位 = **同一道题 × 同一配置**（`run_round4.py:81-93` 逐 `(policy, id)` 运行；
`merge_trackA.py:44-62` 从逐题 `details` 重算 better/worse）。这一步避免了"两次独立运行的总分做卡方"导致的配对信息丢失。

## 机制 2：账本一致性断言（ledger identity）

任何晋升/合并都强制断言"分数差 = 净获益"：

```
ledger_ok: total_b − total_a == better − worse
```

（`evokit/stats.py:11-12`，在 `promote_to_stable.py:53`、`merge_trackA.py:54`、
`verify_evidence_chain.py:101` 三处独立执行。）这条恒等式把**三个**来源（两个总分 + 配对净获益）
锁成一致，任一被篡改或记错都会 `assert` 中止。

## 机制 3：盲留出三集不相交（hidden_passed）

训练集(train 40)、盲留出批1(held1 40)、批2(held2 160) 在题目 id 上**两两不相交**，
演化循环从不接触 held-out（`promote_to_stable.py:66-75`、`verify_evidence_chain.py:120-132`）。
晋升判据（C4 的 `statistical_passed`）只允许基于这个盲合并集的 200 题配对结果。

## 机制 4：五键联合晋升门（fail-closed）

`provisional → stable` 必须**五个证据键同时为 true**（`promote_to_stable.py:125-140`）：

| 键 | 含义 |
| --- | --- |
| `statistical_passed` | 合并盲集 200 题配对 McNemar p < 0.05 且 gain ≥ 阈值 |
| `hidden_passed` | 三集不相交（机制 3） |
| `safety_passed` | 全部 run 的 `safety_violations == 0` |
| `rollback_available` | round1 原件已备份，可回滚（`results/rollback-before-round2/`） |
| `bundle_signature_valid` | 证据 bundle 的 Ed25519 自签名验证通过（机制 5） |

任一键为 false 即不晋升——这是"fail-closed"的机制落点。

## 机制 5：Ed25519 自签名证据 bundle（integrity + audit，非背书）

晋升时构建 manifest（5 个构件的 sha256 + heldout 证据 + disjoint 检查），
计算 canonical-JSON 摘要，用 Ed25519 自签名（`evokit/signing.py:14-41`、
`promote_to_stable.py:77-116`、`signed/bundle.json`）。

**诚实边界（C6）**：签名为 self-signed（`signer="agent-self"`），提供**防篡改 + 可审计**，
**不构成独立第三方背书**。`bundle.json` 的 `signer_note` 与 README 均显式声明这一点。

## 机制 6：独立再验证（从文件重算，不信任缓存）

`tools/verify_evidence_chain.py` 是独立于晋升脚本的第二实现，5 检查全部从头：
(1) bundle sha256 == canonical-manifest 摘要；(2) 5 个构件哈希与仓内文件逐字节一致；
(3) merged 200 题 McNemar + ledger 从逐题结果重算；(4) 三集不相交；
(5) Ed25519 envelope 校验（含过期检查）。运行预期 `ALL CHECKS PASSED`。

## 核心性质：fail-closed 被负结果正向证明

门控的价值在于**它拒绝假增益，也拒绝无增益**，而不只在于它接受真增益。三点证据（C10）：

1. **真增益被接受**：round2 `step-calc` vs `concise-reason` 合并 200 题，better:worse = 33:4，
   精确 McNemar p = 1.08e-06 → 晋升 stable（`bundle.json`、`version-registry.json`）。
2. **负结果被拒绝**：round3 `reflect-retry`/`textgrad-prompt` 挑战者 gate fail（p=1.0），
   `version-registry.json` 记录 `provisional-rejected`，incumbent 保持不变。
3. **无增益被拒绝**：round4 真基线对照，`step-calc` vs `cot-zero` p=0.80、vs `few-shot` p=0.40，
   headline gate fail → outcome (iii) inconclusive，**没有把统计噪声误判成提升**
   （`ROUND4-TRACKA-RESULT.md`）。

这三点合起来，说明该门控在**三个不同方向**都行为正确——这是它作为方法贡献的可证伪核心。