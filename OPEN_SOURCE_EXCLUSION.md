# A线开源排除清单（发布时执行，不改历史证据）

> 结论：暂缓直接 `git push`，先执行本清单。历史 log 与内部计划不手改（证据不可变），发布时排除。

## 1. 排除项（发布包不得含）

- `docs/` — 含 `superpowers/plans/...round3...md` Task 10 推送需 fresh token 说明（单仓 Contents:write / classic public_repo，用完即删），属内部执行计划，不对外发布。`.gitignore` 已含 `docs/`。
- `results/**/ *.log` — `results/rounds/round3/` 运行日志首行含本机绝对路径（已实查，属运行日志，复现时按需重定向）。`.gitignore` 已含 `*.log`；`*.json` 证据保留。
- `.superpowers/` — 含本机绝对路径的执行简报（sdd scratch），`.gitignore` 已含 `.superpowers/`。
- `*.key` / 私钥 — 从不入库；`signed/agent-self.pub.hex` 为公钥可发布。
- `__pycache__/` / `*.pyc` — 已忽略。

## 2. 已验证的诚实说明（2026-09-10 实查，不编造）

- LICENSE：MIT，Copyright 2026 Liu Zewen（`LICENSE` 全文 21 行）。
- 真实密钥：0 命中（`sk-` / `ghp_` / `AKIA` / Bearer 长 token 全 0；token 字样仅 `fresh token` 推送说明与 `forbidden_tokens`，均在排除目录内）。
- 第三方：`THIRD_PARTY_NOTICES.md` 四行 — reflexion MIT（adapted）、textgrad MIT（concept+minimal）、dspy MIT（stretch）、hermes NOASSERTION（ideas only, zero code）；`third_party/` 仅 NOTICE，无大段拷贝。
- `/root/exp-gsm8k` 说明：`signed/bundle.json` manifest 键与旧脚本注释中的 `/root/exp-gsm8k/...` 是云端原始路径 provenance（通用云路径，非个人本机路径），解析时按 basename 落到仓内文件（见 `tools/verify_evidence_chain.py` `BASENAME_MAP`）。发布时保留并以本节说明，不视为泄露个人路径。
- 5/5 构件哈希：`active.json`（bcaecf989905…）、`gsm8k40.json`、`heldout40.json`、`heldout-batch2-160.json`
  与 manifest 一致；`gsm8k_evaluator.py` 由 `signed/artifacts/` 下的签名副本承载，见 §3。

## 3. bundle 绑定 round2 纯净版 evaluator —— 已处置：签名副本保留

- `signed/bundle.json`（`step-calc@ad35903f5cb4`，sha256 `ad35903f5cb4…f2edbc685d1`）绑定 round2 稳定时刻（commit `f80af2f`）的 5 构件。
- Round3（`7d328ab` reflect-retry、`c8651e5` textgrad-prompt）对 evaluator 纯加法扩展（+62/-2 行，`step-calc`/`concise-reason` 原路径走 `else` 分支不变）。
- Round4（`8ba147d` 增 `cot-zero` + 冻结 `few-shot` 两条真基线策略）与 Round5 继续纯加法扩展同一 evaluator；相对 round2 纯净版累计 **+70/-2 行**，原 `step-calc`/`concise-reason` 提示路径始终未改。
- **2026-10-17 处置**：旧行为是 [2/5] 哈希**实时工作树**文件，因此只能永远报
  `FAIL: artifact hash mismatch for gsm8k_evaluator.py`——bundle 钉住的是 round2 版，而工作树已合法演进。
  这曾是门侧缺陷，不是工件缺陷。现在改为哈希签名副本：原版字节逐字节保存为
  `signed/artifacts/gsm8k_evaluator.py`（3892 字节），`BASENAME_MAP` 指向它，[2/5] 通过。
  **未改任何记录哈希、未重签**（私钥不在仓库，重签本就不可行）。
- 纯净版可复算（已实测通过）：`git show f80af2f:examples/gsm8k_evaluator.py | sha256sum`
  = `4a23f69463293b380bfd7a52be5f9e616af3d02f6e822f7be721b95015eb400e`，与 manifest 记录逐字节一致，
  也与 `signed/artifacts/gsm8k_evaluator.py` 一致；当前工作树文件 sha256 = `524623ace3ff3b56…`（round5 版）。
- 复现全链（现在无需 checkout 到旧提交）：任意 checkout 直接运行
  `python tools/verify_evidence_chain.py` → 预期 `ALL CHECKS PASSED`（5/5）。新 bundle 未签发（round3 为 STOP 负结果，无 promotion）。

## 4. 发布前执行

```bash
python tools/check_publish.py   # 预期 PUBLISH GATE PASS
python tools/make_release.py    # 本地打包 shippable 集 -> dist/gsm8k-self-evolve-shippable.zip + SHA256SUMS
git status --short              # 确认无 *.log / docs/ / *.key 被暂存
```

> `make_release.py` 默认先跑门禁（fail closed），再按门禁的 shippable 集打包并输出归档 sha256；`dist/` 为本地产物已 `.gitignore`，不入库不推送。
