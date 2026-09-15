# CLAIM LEDGER — gsm8k-self-evolve 可审计自进化门控框架

> 本账本把 A 线的可发表贡献从"0.925 报告"重构为"可审计、fail-closed 的自进化晋升门控"。
> 每条声明必须可由指向的 `文件:行` 独立重算；无证据或证据冲突的声明不进入正文。
> 状态：`confirmed` = 有可复算证据；`caveated` = 有证据但边界受限，正文须同步披露边界。

## 门控机制类（机制声明）

- **C1 · 配对显著性用精确 McNemar（双侧二项，非卡方近似）**
  证据：`evokit/stats.py:3-8`（`mcnemar_two_sided`：`2 * Σ_{i=0..k} C(n,i) / 2^n`，`k=min(better,worse)`）。
  状态：confirmed。配对单位 = 同题同配置（`run_round4.py:81-93`、`merge_trackA.py:44-62`）。

- **C2 · 账本一致性断言在每次晋升/合并时强制执行**
  证据：`evokit/stats.py:11-12`（`ledger_ok`：`total_b - total_a == better - worse`）；
  `scripts/promote_to_stable.py:53`；`scripts/merge_trackA.py:54`；`tools/verify_evidence_chain.py:101`。
  状态：confirmed。任何比 values 不一致都会触发 assert 中止。

- **C3 · 盲留出三集两两不相交（train 40 / held1 40 / held2 160）**
  证据：`scripts/promote_to_stable.py:66-75`；`tools/verify_evidence_chain.py:120-132`；
  `registry/version-registry.json` `disjoint_check`（40/40/160, pairwise_disjoint=true）。
  状态：confirmed。演化循环从不接触 held-out。

- **C4 · 晋升到 stable 需 5 个证据键同时为 true**
  证据：`scripts/promote_to_stable.py:125-140` 五键：`statistical_passed` /
  `hidden_passed` / `safety_passed` / `rollback_available` / `bundle_signature_valid`；
  落库见 `registry/version-registry.json`（`eecacc0312d7` stable evidence）。
  状态：confirmed。

- **C5 · 证据 bundle 由 Ed25519 自签名并绑定 manifest（5 构件 sha256 + heldout 证据 + disjoint 检查）**
  证据：`evokit/signing.py:14-41`（`sign_bundle`/`verify_envelope`）；
  `scripts/promote_to_stable.py:77-116`；`signed/bundle.json`（5 个 files 的 sha256）。
  状态：confirmed。

- **C6 · 自签名只提供完整性+可审计，不是第三方背书（诚实标注，不夸大）**
  证据：`signed/bundle.json` `signer_note`；`scripts/promote_to_stable.py:93`；
  README "Honest semantics" 段。
  状态：confirmed。这是本框架与"宣称独立可信"工作的重要区别。

- **C7 · 独立再验证脚本从头重算整条证据链，不信任任何缓存声称**
  证据：`tools/verify_evidence_chain.py` 5 检查（bundle digest / 5 构件哈希 /
  merged McNemar + ledger / disjoint / Ed25519 envelope），运行时 `PASS [1/5]..[5/5]`。
  状态：confirmed。

- **C8 · 回滚可用（round1 原件已备份）**
  证据：`registry/version-registry.json` `rollback_available: true`；
  `results/rollback-before-round2/` 目录（round1 active + evaluator 备份）。
  状态：confirmed。

- **C9 · 版本 registry append-only，完整记录 register→provisional→stable→rejected 历史**
  证据：`evokit/registry.py:10-19`（`transition` 追加 events，不改历史）；
  `registry/version-registry.json` `history` 数组（6 条事件，含 round3 `provisional-rejected`）。
  状态：confirmed。

- **C10 · 门控是 fail-closed 的：真增益晋升、假增益/无增益拒绝，都能被正确区分**
  证据：真增益 → round2 merged 200 McNemar p=1.08e-06 晋升（bundle manifest `heldout_evidence`）；
  负结果 → round3 `provisional-rejected`（reflect-retry/textgrad-prompt gate fail，`version-registry.json` history）；
  无增益 → round4 headline gate fail（`results/rounds/round4/ROUND4-TRACKA-RESULT.md`）。
  状态：confirmed。这是本框架的核心正贡献：**不制造假增益**。

## 实验结论类（落点声明）

- **C11 · round4 真基线对照：step-calc ≈ cot-zero，统计不可区分**
  证据：`results/rounds/round4/trackA-merged.json`（totals step-calc=184, cot-zero=186, few-shot=179, direct=27）；
  精确 McNemar p=0.8036（vs cot-zero）、p=0.4049（vs few-shot）；gain +0.010 / −0.025。
  状态：confirmed。

- **C12 · 0.925 的增量主要来自 direct→CoT 式提示，而非自进化超越标准 CoT 基线的独特增量**
  证据：`trackA-merged.json` direct=27 vs cot-zero=186（gain +0.795）；step-calc vs cot-zero 无显著差异（C11）。
  状态：caveated。这是对早先 Round-2 叙事（对照 weak strawman `direct`）的诚实修正，正文必须披露。
  溯源注记（2026-09-15）：旧 headline「0.125→0.925」两端点来自**不同集合**（0.125 = held1-40 的
  direct 5/40，`results/heldout-result.json`；0.925 = merged-200 的 step-calc 185/200，签名 bundle）；
  Round-2 时期无 direct 在 merged-200 上的运行，同集比较 = Round-4 的 0.135→0.920。
  185（晋升评估）与 184（Round-4 重跑）为同一策略两次独立 temperature-0 运行之差（§5 方差范围内）。

- **C13 · "无显著差异"≠"证明等价"（未预注册等价边际，n=200 对小效应功效不足）**
  证据：`results/rounds/round4/PREREG-round4.md:16`（temperature 0、单次、无种子控制）；
  `ROUND4-TRACKA-RESULT.md` 第 5 节诚实边界。
  状态：confirmed。禁止把 C11 演绎为"自进化无效"。

## 跨模型验证类（Track C，2026-09-12）

- **C17 · `step-calc` 相对 `cot-zero` 在 4 个模型上均无显著优势**
  证据：p = 0.804（qwen2.5:7b, n=200）/ 0.500（gemma3:4b）/ 1.000（qwen2:7b）/ 0.500（llama3.1:8b），
  见 `trackA-merged.json`、`trackC-gemma3-4b-heldout40.json`、`trackC-qwen2-7b-heldout40.json`、
  `trackC-llama31-8b-heldout40.json`；`ROUND4-TRACKC-RESULT.md` 第 2 节。
  状态：confirmed。方向一致（|gain| ≤ 0.05）。

- **C18 · Round-2 的"自进化增益"（step-calc ≫ concise-reason）未在其它模型复现**
  证据：gemma3:4b −0.075（p=0.453）、qwen2:7b +0.050（p=0.688）、llama3.1:8b −0.025（p=1.000）；
  原效应在 qwen2.5:7b 为 better:worse=33:4、p=1.08e-06（`signed/bundle.json` `heldout_evidence`）。
  状态：caveated。n=40 功效不足，"未复现"≠"证明不存在"；三个新模型 p 均 ≥0.45 故按预注册不扩展。

- **C19 · 唯一稳健的正效应是「CoT 式提示 ≫ 纯数字作答」（direct）**
  证据：direct vs 任一 CoT 式策略在 4 个模型上 p ≈ 1e-9…1e-48、gain +0.70…+0.95。
  状态：confirmed。这解释了早期 Round-2 "0.125→0.925" 的来源与自进化机制无关。

- **C20 · fail-closed 门控行为在 4 个模型上一致**
  证据：在 3 个新模型上重跑同一门控，headline gate 全部 FAIL、均不扩展
  （`ROUND4-TRACKC-RESULT.md` 第 4 节）。C10 由"单模型三方向"升级为"4 模型 × 三方向"。
  状态：confirmed。

## 前置条件 / 范围声明

- **C14 · 自签名密钥私钥从不发布，仅公钥 hex 入库**
  证据：`signed/agent-self.pub.hex`（65 字节公钥）；`README.md` Layout 段（"private key never published"）。
  状态：confirmed。

- **C15 · 主实验后端为 qwen2.5:7b（temperature 0）；跨模型扩展见 C17–C20，仍未覆盖公开基准迁移**
  证据：`results/rounds/round4/PREREG-round4.md:7`；`ROUND4-TRACKC-RESULT.md`（4 个模型）；
  Track B（SVAMP/MultiArith/ASDiv 迁移）**未运行**。
  状态：confirmed。

- **C16 · 无真实密钥 / 无个人绝对路径残留，可发布（发布门禁 5/5 PASS）**
  证据：`tools/check_publish.py` 运行时 `PUBLISH GATE PASS`；`OPEN_SOURCE_EXCLUSION.md` 第 2 节。
  状态：confirmed。

## 数据溯源与许可类（2026-09-12 核验）

- **C21 · 三个题目集逐字来自官方 GSM8K test split，且与 GSM8K train 零重叠**
  证据：`tools/verify_question_provenance.py` 运行结果 240/240 match official GSM8K test
  （test n=1319, sha256 `3730d312f6e3…`；train n=7473）；0 match train（无污染）；
  位置分布均匀散布（mean 644.7 vs 均匀期望 659.0；四分位 344/630/947；前后半 126/114；
  非连续块）→ 非"取前 N 题"式有偏选择。记录：`results/rounds/round4/QUESTION_PROVENANCE.json`。
  状态：confirmed。**此前"盲集为自建"的说法系未经验证的假设，现予撤回。**

- **C22 · GSM8K 的 MIT 归属义务已履行**
  证据：`THIRD_PARTY_NOTICES.md` 新增"Datasets redistributed"小节（Copyright (c) 2021 OpenAI,
  MIT, 含上游链接）。
  状态：confirmed。

- **C23 · 运行间方差已量化（2026-09-12）：定性判定稳定，幅度限 ±0.025 量级**
  证据：`results/rounds/round4/ROUND4-VARIANCE.md`；3 次重复、360 次调用（qwen2.5:7b, heldout40,
  {step-calc, cot-zero, concise-reason}）。逐策略准确率极差 ≤0.025（cot-zero/concise-reason 为 0.000）；
  **显著性判定翻转的配对数 = 0**（step-calc vs cot-zero p=0.625/1.00/1.00；
  vs concise-reason p=0.500/0.250/0.250）。复算：`scripts/variance_report.py`。
  残余限制：3 次重复、单模型、n=40（n=200 合并集未重复）。
  状态：confirmed。**本条由"方差未量化"升级为"已量化"**，README 原 ±10% 漂移估计未被复现（同文件记录，不以此否定新测量）。

- **C24 · 跨环境差异与 run-to-run 差异同量级（噪声包络 ±1–2/40）**
  证据：同一模型同一 40 题，云端 `cot-zero` 39/40、本地 38/40（差 1 题）；本地 3 次重复极差 ≤1 题。
  状态：confirmed。故任何单次 40 题结果只应在 ±0.025–0.05 内解读。

## 决策规则消融类（2026-09-12，round5 新颖性 head-to-head）

> 比较对象是**决策程序**（与相关工作公开描述一致的 idealised decision rules），不是
> REMO/SPHERE/TextGrad 那些系统本身（PREREG-round5.md Global Constraints）。零来自**置换 null**
> （对 discordant 题逐题独立以 0.5 交换 chal/inc 标签，真效应恒 0），非独立抽样。

- **C25 · 五键门控（R1）在置换零上的 FPR 显著低于任何"无错误控制"基线决策程序**
  证据：`results/rounds/round5/ablation.json:270-274`（R1 pooled `promoted=10, total=800, rate=0.0125,
  wilson95_upper=0.022855707711738636`）；`ablation.json:296-300`（R2 `330/800=0.4125`）；
  `ablation.json:428-432`（R7@8 `786/800=0.9825`）。R3=12/800、R5=33/800、R6=217/800
  （`ablation.json:322-326, 375-379, 401-405`）；复算入口 `scripts/ablation_gate.py`（零模型调用）。
  状态：confirmed。
  范围澄清（如实，2026-09-14）：该优势**仅在对比「无错误控制」的程序时**成立。对比另一条**有错误控制**
  的规则 R3（非配对两比例检验）时，R1 不显著更优：配对精确 McNemar **b=4, c=6, p=0.754**，Wilson 区间
  重叠（R1 [0.00680,0.02286] vs R3 [0.00860,0.02603]）。故「拒绝能力」的准确归因是**有一个 α=0.05 的
  有效显著性检验**，而非五键合取、也非配对（α 是可测杠杆：R5 α=0.20 显著劣于 R1，b=0,c=23,p≈2.38e-7）。

- **C26 · 同一批 800 置换零上的配对精确 McNemar 支持 R1 的 FPR 优势（方向一致且 p<α）**
  证据：`ablation.json:825-844`（R1 vs R2：`r1_only_b=0, baseline_only_c=320, exact_two_sided_p=
  9.363352709384397e-97 ≈ 2⁻³¹⁹`；R1 vs R7@8：`r1_only_b=0, baseline_only_c=776, exact_two_sided_p=
  5.0321474762477604e-234 ≈ 2⁻⁷⁷⁵`），配对单位 = `(source_pool, null_index)`，四个源池方向全一致。
  状态：confirmed。这是"区间不重叠"读数的**操作性校验**（PREREG §5.1 独立性保障）。

- **C27 · 判定分支为 (i)：「门控价值成立」（gate value established）**
  证据：`ablation.json:878`（`verdict_branch="i"`）；`ablation.json:812-856`（三分支逐条款）；
  判定式 `scripts/ablation_gate.py:336-384`（clause a 区间 disjoint+下方 / clause b paired McNemar
  一致 / clause c TPR 不下降）。状态：confirmed。该分支是 N 由 2→3 的预注册依据（PLAN-NOVELTY Task 7）。

- **C28 · 消融比较的是决策程序，不是 REMO/SPHERE/TextGrad 系统本身（且不声称复现/击败）**
  证据：`results/rounds/round5/PREREG-round5.md`（Global Constraints 第 2 条、§3 池族、§2 规则表）；
  `paper/PLAN-NOVELTY.md` Global Constraints。7 条规则均为 idealised 决策程序的重实现，
  不运行相关系统的代码。状态：confirmed（边界声明，正文与摘要必须同步写明）。

- **C29 · 零池来自 relabelling、非独立抽样；Wilson 区间按保守界读，操作性结论靠 McNemar**
  证据：`ablation.json:869`（`independence_note`：单源池 200 个零共享该池题目、非独立 Bernoulli）；
  `PREREG-round5.md` §1（"Null pools derived from one real pool share that pool's questions"）、
  §5.1 独立性保障。状态：confirmed。这是 FPR 读数的诚实边界，正文必须披露。

- **C30 · R4（non-blind）是定义性对照（分母 6），非发现，且无 R4 FPR 可声称**
  证据：`ablation.json:670-750`（`r4` 区块：`denominator=6`、`promoted=2`、
  `r1_by_construction_refuses_all=true`、`no_r4_fpr_is_claimed=true`、`r1_vs_r4_contrast_is_definitional=true`）；
  `ablation_gate.py:289-325`。R1 因要求 `blind is True` **按定义**拒绝全部 6 个非盲选择集池，
  R4 晋升其中 2/6——这是门控盲约束的定义后果，不是测量发现；无非盲零集，故无 R4 FPR。
  状态：confirmed（定义性，正文不得叙述成发现）。

## 提议器替代臂（Task 6，round5，新一代骨干，2026-09-14）

- **C31 · [已作废 INVALIDATED，2026-09-16，等待重跑]** 原声明：文本批判提议器的产物在
  Qwen3.8-27B-AWQ 上不优于零样本 CoT。
  **作废原因（数据取证）**：原 400 调用中仅前 140 次（held-01..14 × 5 策略 × 2 重复）真实到达模型。
  云端 vLLM 服务在运行中被外部 SIGTERM 优雅终止（`vllm-27b2.log`：09-14 15:17:56 shutdown 序列；
  同 GPU 现有其它工作负载），其后 260 次调用全部传输层失败——签名：latency=0、parsed=None、
  恰为 held-15..40 全部 26 题 × 5 策略 × 2 重复（`full.log` call 141 起）。runner 将传输失败
  误记为"模型答错"并计入 totals/headline，故 **totals（direct 1 / step-calc 13 / cot-zero 14 /
  few-shot 12 / textgrad 13，"n=40"）与 headline（b=0,c=1,p=1.0）不成立**——有效样本仅 n=14。
  处置：① 产物隔离（`results/rounds/round5/proposer-arm-qwen38-27b.QUARANTINE.md`；原 JSON
  作为证据原样保留、不修改）；② runner 缺陷修复（传输失败不计为有效数据、resume 重试失败格）；
  ③ 预算修订（400 有效格之外允许补偿性重试）后重跑 held-15..40。重跑完成前，正文不得引用
  任何 T6 数字（DRAFT §5.7 已改为隔离声明）。
  状态：**invalidated**（原 confirmed 判定撤回；教训已记 `.agent-memory/ledger/lessons.md`）。

## 明确不成立的声明（禁止写入正文）

- 不声称"自进化显著超越标准 CoT 基线"（被 C11 证伪为 inconclusive）。
- 不声称签名是独立第三方背书（C6 明确是 self-signed）。
- 不声称"盲集是自建的"（**已被 C21 证伪**：240 题逐字为官方 GSM8K test 原题）。
- 不声称 0.925 是**完整** GSM8K test 分数（它是 1319 题 test split 中散布的 240 题子集上的
  分数，非全集 1319 题；跨集/跨子集比较无效）。
- 不声称消融"复现了"或"击败了" REMO / SPHERE / TextGrad：C28——比较对象是与这些工作**公开描述一致的
  决策程序**（idealised decision rules），不是那些系统本身。
- 不声称 R4 的 FPR：C30——无非盲零集，R4 是分母 6 的定义性对照，不是泛化发现。
- 不声称 R1 在 TPR 上优于 R2/R7：POSITIVE 分母 = 1，clause (c) 是防空转 sanity guard、无鉴别力
  （`ablation.json:846-854`）。