# Round 4 — Track B transfer record (frozen step-calc vs direct)

- 日期：2026-09-13（测量）+ 记录；分支 `round4-true-claims`。
- 后端：qwen2.5:7b，temperature 0（与 Round 1–4 一致，含 Track A）。
- 策略：`direct`（number-only）与冻结的 `step-calc` 各 1 次，逐题配对，逐集断言 ledger。
- 预注册规则（PREREG-round4.md）：**step-calc beats direct with p < 0.05 on SVAMP-full AND gain > 0 on all three sets**。

## 结果

| 数据集 | direct | step-calc | better | worse | McNemar p | gain |
|---|---|---|---|---|---|---|
| svamp (1000) | 647 | 920 | 290 | 17 | 2.787e-65 | +0.273 |
| multiarith (180) | 87 | 180 | 93 | 0 | 2.019e-28 | +0.517 |
| asdiv (2249) | 1589 | 2026 | 502 | 65 | 1.220e-84 | +0.194 |

## 判定：**GENERALIZE（预注册规则触发）**

规则三条件：
1. SVAMP-full `step-calc` 显著胜 `direct`：p = 2.787e-65 < 0.05 ✅
2. 三集 `gain > 0`：svamp +0.273、multiarith +0.517、asdiv +0.194 ✅
3. 结论：**step-calc 对 direct 的优势在三个外部算术词题集上泛化。**

## 诚实边界（不可过度演绎 —— 本判定不改变 Round-4 核心结论）

1. **这是 step-calc vs `direct`（number-only 稻草人基线），不是 vs 标准 CoT。**
   Track A 已证明 `step-calc ≈ cot-zero`（p=0.80，null）。本记录只表明：
   "CoT 式提示对 number-only 提示的优势，跨越 GSM8K / SVAMP / MultiArith /
   ASDiv 四个算术词题集复现"。这是预期内、已知的结论，**不是**自进化
   相对标准 CoT 的新增证据。自进化相对标准 CoT 的结论仍是 Track A 的
   inconclusive（无显著差异）。
2. ASDiv 抓取层排除 56 道非数值答案题（who/which/yes-no/颜色题，评估器为
   精确浮点相等，无法判分），保留 2249 道；排除清单见
   `inputs/asdiv.exclusions.json`。
3. 预算偏差：预注册写 ~6970 次调用，实际 (1000+180+2249)×2 = 6858 次，
   因 asdiv 排除 56 题而略低于预注册值。
4. 温度 0 但 Ollama 无种子控制，单次运行含不可控噪声（与 Round 1–4 同限）。
5. 数据集许可：输入集运行时下载、绝不入库（ASDiv CC-BY-NC-4.0；MultiArith
   许可不明），仅结果 JSON 入库。

## 数据源

- 结果 JSON：`transfer-svamp.json`、`transfer-multiarith.json`、`transfer-asdiv.json`（均有 ledger 断言）。

## Amendment 1 注记（2026-09-13）

本记录是 `step-calc vs direct`，按 PREREG-round4.md **Amendment 1** 降级为
sanity check（direct 是稻草人，此对比**无信息量**，仅证明"CoT 式 ≫ 纯数字"
泛化——已知且预期内）。**主对照已修订为 `step-calc vs cot-zero`**（同一三集，
逐题配对，决策规则见 Amendment 1），**尚未运行**。运行命令见
`scripts/run_transfer_cotzero.py --help` 前的 docstring；跑完后的结果另写
`transfer-cotzero-*.json` + 新判定记录。

## Amendment 1 主对照结果（2026-10-05，qwen2.5:7b，temperature 0）

运行：`EVO_MODEL=qwen2.5:7b python3 scripts/run_transfer_cotzero.py`
产物：`transfer-cotzero-{multiarith,svamp}.json`（ASDiv 未跑，见下方边界 4）
判定规则：**verbatim 复制** PREREG-round4.md Amendment 1 的三支：
(i) 任一集 `p < 0.05` → 新发现；(ii) 三集全不显著 → 与 Track A null 一致；
(iii) 混合 → 原样报告。

### 已测集

| 数据集 | n | step-calc | cot-zero | better:worse | McNemar p | gain | 延迟比 | 判定 |
|---|---|---|---|---|---|---|---|---|
| MultiArith | 180 | 180 | 180 | 0:0 | 1.0000 | +0.000 | 1.353 | **饱和（见边界 1）** |
| SVAMP | 999 / 1000 | 919 | 933 | 30:16 | 0.0541 | −0.0140 | 1.092 | 未达显著，**距门槛 1~2 格（边界 2）** |
| ASDiv | 2249 | 未运行 | | | | | | |

SVAMP 的 n 是 999：整跑 1000 格因 `chal-513` 永久不收敛被 fail-closed 门拦下，
未产出正式 totals；此行为从保留的 `details` 复算的子集，见边界 2 与边界 5。

### 诚实边界

1. **MultiArith 那格是「饱和/无检验力」，不是「两臂无差异」。**
   两臂各 180/180，且**逐题答对集合完全相同**（对称差为空），故 discordant
   `d = b + c = 0`。d=0 时**任何样本量都救不回来**——统计量由同一对相同的答对集合
   算出，增大 n 只会把两个相同的集合一起放大。即使把全部 discordant 归到一侧，
   也需 `d ≥ 6` 才可能达到 `p < 0.05`（由 `scripts/trackB_power.py` 复算）。
   因此判定规则分支 (ii)（"三集全不显著 → 证实无差异"）**不能**靠 MultiArith
   支撑；这一集对该分支的贡献是零证据。把「饱和」写成「无差异」是统计上的偷换。
2. **SVAMP：整跑被 fail-closed 门拦下，故无正式 totals；999 格子集**，
   step-calc **919/999 = 0.9199** vs cot-zero **933/999 = 0.9339**，
   better:worse = **30:16**，discordant d = 46，
   exact McNemar **p = 0.054076031858869555**（gain −0.0140，cot-zero 更高）。
   方向为 cot-zero 更好；若显著，按判定规则分支 (i) 属「step-calc **输**给
   cot-zero」，同样是新发现。**该 p 不可解读为趋势**：b=31,c=16 即得 0.03999、
   b=32,c=16 得 0.02930、b=30,c=15 得 0.03570 —— 距离 0.05 门槛只差 1~2 格，
   任何一格翻转都会跨线。参见 [结果文件](transfer-cotzero-svamp.json)（保留为
   审计痕迹，含 2 格永久不收敛，见边界 5）。
3. **ASDiv 未运行**，而它才是判定规则能否落地分支 (ii) 的承重墙（外推约 60%+）。
   本记录因此**不足以**给出 Amendment 1 的最终三支判定，只给出已测两集。
4. **未运行的原因**：2026-10-05 复跑时确认整机处于内存 thrashing（swap 占 7.8G/16G，
   `llama-server` 自身 2.9G 被换出），正是 2026-10-04 那次 840/1000 运输失败风暴的
   成因。已测两集零运输错误；ASDiv 2249 题 × 2 臂 ≈ 4.5h 连跑，被判定为风险高于收益，
   待内存空出后另跑。**这不是"数据不支持"，是"尚未测"。**
5. **SVAMP 唯一两格超时是模型永久不收敛，不是运输故障。**
   `chal-513`（`David did 56 more push-ups than Zachary ... If David did 38
   push-ups ... altogether?`，expected 20）上 qwen2.5:7b 算出负数 `38-56` 后
   陷入自纠循环：`num_predict=1200` 时 41.9s 返回、`done_reason=length`、末段
   重复 34 次；默认 4096 仍 `length`（129.8s）；8192 时 220s 仍未返回。
   **同一题的 step-calc 提示 5.2s 正常答对**（parsed 20.0），cot-zero 提示连试
   4 次全部 TimeoutError，`--resume` 无法修复。已登记为
   `results/rounds/round4/inputs/svamp.json#chal-513`（见 `results/NONCITABLE.json`
   第 5 条），排除规则**先于检视子集声明**：一个 (策略, 题) 格当且仅当模型在该策略
   提示下可证明不终止时退出配对比较；该规则不依赖剩余格子的方向。
   整跑因该格触发门 → `INCOMPLETE: true` / `error_counts {'TimeoutError': 2}` /
   **无 totals 无 pairs**，故上表 999 格为子集复算而非整跑产出。
6. 本节所有数字由 `python3 scripts/trackB_power.py` 与
   `python3 tools/check_noncitable.py` 可复算；`INCOMPLETE` 文件不参与正式聚合
   （该脚本会显式 skip）。999 格子集的 d 与 p 可由
   `python3 scripts/transfer_subset.py` 从 `details` 重算。

### Track-B 主对照的检验力（由 `scripts/trackB_power.py` 复算）

| 数据集 | n | step-calc | cot-zero | discordant d | McNemar p | 状态 |
|---|---|---|---|---|---|---|
| multiarith | 180 | 180 | 180 | 0 | 1.0000 | **饱和（无检验力）** |

- 最极端偏斜（全部 discordant 归一侧）时仍需 **d ≥ 6** 才可能达到 `p < 0.05`；实测 MultiArith 的 d = 0，任何 n 都无法改变该统计量，因为正确题集合完全相同。

- 本节每个数字由 `python3 scripts/trackB_power.py` 从仓内文件复算；其 McNemar 本地实现与 `evokit.stats.mcnemar_two_sided` 在 5 组 (b, c) 上断言一致（abs 差 < 1e-12），未通过则脚本直接抛错。
- 外推（乐观假设：discordant 仅为 `direct` 对照的 15%，且 70% 的 discordant 偏斜给 step-calc），asdiv / svamp 仍会触发分支 (i)。因此 ASDiv 是该判定规则能否落地分支 (ii) 的承重墙，不是可选补充。
- 反面：外推在「discordant 砍到 15% 且偏斜仅 60%」时会失效（svamp 投影 p = 0.302）。所以「ASDiv 一定能显著」**不是**预注册的承诺，只是当前先验下的期望；分支 (ii) 仍可能被触发。
