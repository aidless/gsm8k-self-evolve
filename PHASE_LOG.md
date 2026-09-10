# P1 PHASE_LOG — A线 gsm8k-self-evolve（世界先进封顶）

- 结果 vs 验收 G1：发布门 `tools/check_publish.py` 5/5 PASS；`evokit` 4 passed；旧 bundle 纯净版可复算（f80af2f 哈希逐字节一致）；工作树 verifier [2/5] 诚实 FAIL 已解释（round3 加法演进，非缺陷）。G1 通过（附 caveat）。
- 产出物：`OPEN_SOURCE_EXCLUSION.md`、`tools/check_publish.py`（均 untracked 待提交）。
- 失败+纠正：verifier [2/5] FAIL → 查 git 历史定位 round3 两提交 → `git show f80af2f` 哈希证纯净版一致 → 落盘 caveat（1次纠正）；check_publish 自匹配 6 轮迭代（自扫描误报→逐行加白并注释， gate 本身是被测对象）。
- 未动：历史 log/bundle/registry（证据不可变）；未推送（Task10 仍 BLOCKED，需 fresh token+用户授权）。

## P1-HARDEN (2026-09-10, additive only)
- 做了什么（只加法）：新增 `tests/test_publish_gate.py`（6 个回归测试：gitignore 排除 docs/*.log/.superpowers、shippable 集无内部目录/.log、无 *.key/私钥、无真实密钥模式、LICENSE 存在且 MIT、gate 脚本 subprocess PASS）；新增 `SECURITY.md`（密钥零容忍+报告路径+指向 OPEN_SOURCE_EXCLUSION.md）；新增 `.github/workflows/verify.yml`（CI：pip install -r requirements.txt + pytest + check_publish，只读门禁）。requirements.txt 确认 `cryptography>=41` 已有下限，未改。results/、signed/、registry/、examples/ 未动。
- 验证结果：`python3 -m pytest -q` → 10 passed（含原有 4 个）；`python3 tools/check_publish.py` → 5/5 PASS + PUBLISH GATE PASS；`git status --short` → 仅 `SECURITY.md`、`tests/test_publish_gate.py`、`.github/workflows/verify.yml` 三个新增，无 *.log/docs 暂存。途中 1 次纠正：新测试文件字面量触发 gate 自匹配 → 改为字符串拼接构造 marker + 自跳过断言行后全过。
- 提交：`P1-HARDEN: publish-gate test + SECURITY + CI (additive only)`，绝不 push。

## P1-CLOSE (2026-09-10T15:33Z, additive only)
- 前置只读检查（workspace root）：`git -C gsm8k-self-evolve status --short` → 空（干净）；
  `git -C gsm8k-self-evolve log --oneline -3` → `6040d15 P1-HARDEN: publish-gate test + SECURITY + CI (additive only)` /
  `255c5c7 P-A1: publish-gate artifacts (exclusion doc + check_publish 5/5 + phase log)` /
  `4ab2a98 Merge round3-borrowed-iteration: negative result + P-A1 cleanup`。HEAD = 6040d15135dc6f4c99e386254ad27ee8abb8f747（与 controller 基线一致）。
- 测试（cwd=gsm8k-self-evolve）：`python3 -m pytest -q` → `10 passed in 0.70s`（复核 `10 passed in 0.29s`，两次全绿；
  gate 自匹配未复发，测试文件零修改，gate 语义未动）。
- 发布门（cwd=gsm8k-self-evolve）：`python3 tools/check_publish.py` 实际输出：
  `PASS [1/5] *.log ignored` / `PASS [2/5] docs/ + .superpowers/ excluded` /
  `PASS [3/5] no *.key / private key` / `PASS [4/5] no real secrets in shippable files` /
  `PASS [5/5] no personal abs paths (/root/exp-gsm8k provenance allowlisted)` /
  `PUBLISH GATE PASS: shippable set clean (docs/*.log/*.key excluded, history untouched)`。
- 诚实 case（预期 FAIL，非缺陷）：`python3 tools/verify_evidence_chain.py` 实际输出
  `PASS [1/5] bundle.sha256 == sha256(canonical manifest) = ad35903f5cb4...` 后
  `FAIL: artifact hash mismatch for gsm8k_evaluator.py`（exit 1）；
  `git show f80af2f:examples/gsm8k_evaluator.py | sha256sum` →
  `4a23f69463293b380bfd7a52be5f9e616af3d02f6e822f7be721b95015eb400e`（与预期值逐字一致），
  记为 round3-additive-evolution honest FAIL。results/、signed/、registry/、examples/ 未动。
- 本轮改动（只加法）：PHASE_LOG.md 追加本节 + 新建 FINAL_ACCEPTANCE.md；提交 `P1-CLOSE: publish gate + pytest green, no push`，本地提交不 push。
