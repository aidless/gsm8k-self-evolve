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
- 4/5 构件哈希：`active.json`（bcaecf989905…）、`gsm8k40.json`、`heldout40.json`、`heldout-batch2-160.json` 与 manifest 一致；唯一差异 `examples/gsm8k_evaluator.py` 见 §3。

## 3. 已知 caveat：bundle 绑定纯净版 evaluator（非缺陷，是诚实演进）

- `signed/bundle.json`（`step-calc@ad35903f5cb4`，sha256 `ad35903f5cb4…f2edbc685d1`）绑定 round2 稳定时刻（commit `f80af2f`）的 5 构件。
- Round3（`7d328ab` reflect-retry、`c8651e5` textgrad-prompt）对 evaluator 纯加法扩展（+62/-2 行，`step-calc`/`concise-reason` 原路径走 `else` 分支不变），故工作树 `tools/verify_evidence_chain.py` [2/5] 对当前文件报告 `artifact hash mismatch for gsm8k_evaluator.py` 是**预期内**的诚实失败。
- 纯净版可复算（已实测通过）：`git show f80af2f:examples/gsm8k_evaluator.py | sha256sum` = `4a23f69463293b380bfd7a52be5f9e616af3d02f6e822f7be721b95015eb400e`，与 manifest 记录逐字节一致。
- 复现旧 bundle 全链：`git stash -u`（或 `git worktree add /tmp/a-pristine f80af2f`）后在纯净树运行 `python tools/verify_evidence_chain.py`（预期 ALL CHECKS PASSED）；工作树运行预期 [1/5] PASS + [2/5] 诚实 FAIL。新 bundle 未签发（round3 为 STOP 负结果，无 promotion）。

## 4. 发布前执行

```bash
python tools/check_publish.py   # 预期 PUBLISH GATE PASS
git status --short              # 确认无 *.log / docs/ / *.key 被暂存
```
