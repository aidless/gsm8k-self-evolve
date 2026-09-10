# P1 PHASE_LOG — A线 gsm8k-self-evolve（世界先进封顶）

- 结果 vs 验收 G1：发布门 `tools/check_publish.py` 5/5 PASS；`evokit` 4 passed；旧 bundle 纯净版可复算（f80af2f 哈希逐字节一致）；工作树 verifier [2/5] 诚实 FAIL 已解释（round3 加法演进，非缺陷）。G1 通过（附 caveat）。
- 产出物：`OPEN_SOURCE_EXCLUSION.md`、`tools/check_publish.py`（均 untracked 待提交）。
- 失败+纠正：verifier [2/5] FAIL → 查 git 历史定位 round3 两提交 → `git show f80af2f` 哈希证纯净版一致 → 落盘 caveat（1次纠正）；check_publish 自匹配 6 轮迭代（自扫描误报→逐行加白并注释， gate 本身是被测对象）。
- 未动：历史 log/bundle/registry（证据不可变）；未推送（Task10 仍 BLOCKED，需 fresh token+用户授权）。

## P1-HARDEN (2026-09-10, additive only)
- 做了什么（只加法）：新增 `tests/test_publish_gate.py`（6 个回归测试：gitignore 排除 docs/*.log/.superpowers、shippable 集无内部目录/.log、无 *.key/私钥、无真实密钥模式、LICENSE 存在且 MIT、gate 脚本 subprocess PASS）；新增 `SECURITY.md`（密钥零容忍+报告路径+指向 OPEN_SOURCE_EXCLUSION.md）；新增 `.github/workflows/verify.yml`（CI：pip install -r requirements.txt + pytest + check_publish，只读门禁）。requirements.txt 确认 `cryptography>=41` 已有下限，未改。results/、signed/、registry/、examples/ 未动。
- 验证结果：`python3 -m pytest -q` → 10 passed（含原有 4 个）；`python3 tools/check_publish.py` → 5/5 PASS + PUBLISH GATE PASS；`git status --short` → 仅 `SECURITY.md`、`tests/test_publish_gate.py`、`.github/workflows/verify.yml` 三个新增，无 *.log/docs 暂存。途中 1 次纠正：新测试文件字面量触发 gate 自匹配 → 改为字符串拼接构造 marker + 自跳过断言行后全过。
- 提交：`P1-HARDEN: publish-gate test + SECURITY + CI (additive only)`，绝不 push。
