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

- **C13 · "无显著差异"≠"证明等价"（未预注册等价边际，n=200 对小效应功效不足）**
  证据：`results/rounds/round4/PREREG-round4.md:16`（temperature 0、单次、无种子控制）；
  `ROUND4-TRACKA-RESULT.md` 第 5 节诚实边界。
  状态：confirmed。禁止把 C11 演绎为"自进化无效"。

## 前置条件 / 范围声明

- **C14 · 自签名密钥私钥从不发布，仅公钥 hex 入库**
  证据：`signed/agent-self.pub.hex`（65 字节公钥）；`README.md` Layout 段（"private key never published"）。
  状态：confirmed。

- **C15 · 后端为 qwen2.5:7b（temperature 0），结论不推广到其他模型/任务**
  证据：`results/rounds/round4/PREREG-round4.md:7`；README Method/Result 段。
  状态：confirmed。

- **C16 · 无真实密钥 / 无个人绝对路径残留，可发布（发布门禁 5/5 PASS）**
  证据：`tools/check_publish.py` 运行时 `PUBLISH GATE PASS`；`OPEN_SOURCE_EXCLUSION.md` 第 2 节。
  状态：confirmed。

## 明确不成立的声明（禁止写入正文）

- 不声称"自进化显著超越标准 CoT 基线"（被 C11 证伪为 inconclusive）。
- 不声称签名是独立第三方背书（C6 明确是 self-signed）。
- 不声称 0.925 是标准 GSM8K test split 分数（是自建 blind held-out，见 C15 与 README 范围说明）。