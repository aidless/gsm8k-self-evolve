# 新颖性 head-to-head：晋升门控的决策规则消融 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **位置说明（偏离技能默认）：** 技能默认存 `docs/superpowers/plans/`，但本仓 `.gitignore` 排除了 `docs/`（发布排除项），故本计划存 `paper/PLAN-NOVELTY.md` 以纳入版本控制。

**Goal:** 把新颖性从"自我声明的 Adjacent 差一句话"变成"实测差异化"——用同条件实验证明 fail-closed 晋升门控在**拒绝行为**（错误率控制 + 选择压力下的稳定性）上优于与相关工作一致的决策程序，使自评 N 由 2 升到 3。

**Architecture:** 不新跑训练、不新拉模型。核心是**决策规则消融**：同一批配对数据上比较 7 种晋升决策规则。仪器是**置换零（permutation null）**——在真实 discordant 对上按题随机重排挑战者/现任标签，真值恒为 0 且保留 discordance 结构，因此任何"晋升"都是假阳。另有一条 proposer 替代臂（需少量新生成）证明门控与提议器解耦。

**Tech Stack:** Python 3.12 标准库；复用 `evokit/stats.py`（`mcnemar_two_sided` / `ledger_ok`）；数据来自 `results/rounds/round4/*.json`；增量落盘复用 `scripts/run_paired_incremental.py`。

**Spec:** `paper/CLAIM_LEDGER.md`（C1–C24）、`RELATED_WORK.md`、`results/rounds/round4/{PREREG-round4.md,ROUND4-TRACKA-RESULT.md,ROUND4-TRACKC-RESULT.md,ROUND4-VARIANCE.md}`、`paper/METHOD.md`。

## 开工前的实测修正（已执行，必须记录）

计划初稿拟用"同策略两次运行"构造零效应池。**执行前实测否定了该设计**：

```
variance-qwen25-7b rep1/rep2/rep3，逐策略两两配对：
  concise-reason rep1 vs rep2: better=0 worse=0 agree=40
  concise-reason rep1 vs rep3: better=0 worse=0 agree=40
  concise-reason rep2 vs rep3: better=0 worse=0 agree=40
  cot-zero       ×3         : better=0 worse=0 agree=40 （全部）
  step-calc      rep1 vs rep2: better=1 worse=0 agree=39
  step-calc      rep1 vs rep3: better=1 worse=0 agree=39
  step-calc      rep2 vs rep3: better=0 worse=0 agree=40
```

9 个池中 **7 个 discordant 对数 = 0**。temperature 0 下重复运行近乎确定，用它们做零池会使**所有**规则的假阳率恒为 0，比较退化为无信息量。

**修正：** 零效应池改由**逐题标签置换**构造（见 Task 1）。原始重复数据仅用于已完成的方差结论（C23/C24）与"重复近乎确定"这一新事实的记录。

## 设计验证（已执行的真实 pilot，证明该设计有区分度）

在写计划后、执行前，用真实数据跑了一次 mini pilot（K=2000 次置换，非交付结果，仅证明设计可用）：

```
marginal 池实测   : qwen2:7b step-calc vs concise-reason  b=2 c=4 d=6  p=0.688 gain=-0.050
positive 池实测   : trackA  cot-zero vs direct            b=159 c=0 d=159 p=2.7e-48 gain=+0.795

置换零（d 保持 =6，mean gain = -0.0029 ≈ 0 ✓）：
  R1 gate      FPR = 0.015
  R2 point     FPR = 0.320
  R6 no-stat   FPR = 0.320
  R7 bestofk   FPR: k=1 → 0.357 ；k=2 → 0.620 ；k=4 → 0.838 ；k=8 → 0.968
```

结论：设计**确实有区分度**——门控把假阳压到 0.015，而点估计/去掉统计键为 0.32，
选择压力下 naive 规则升到 0.97。这正是预注册三分支要检验的东西。

**由此得到的一条硬性设计约束（必须写进 Task 3/4）：** 在 d=6 的池上，精确 McNemar 的 p 只能取
{0.031, 0.219, …}，**α=0.05 与 α=0.20 的决定完全相同**（pilot 中 R5 ≡ R1）。因此
**R5（α 敏感性）与 R3（非配对）必须在大 d 池上评估**——仓库里现成可用的有
`step-calc vs cot-zero`（d=16）、`step-calc vs few-shot`（d=23）、`cot-zero vs few-shot`（d=15）。
不得只用 d=6 的池跑这两条臂，否则会得出"α 无影响"这种由离散性造成的假结论。

## Global Constraints

- 所有数字必须由交付证据独立重算，不编造、不从别处复制。
- **不得声称"我们复现/击败了 REMO / SPHERE / TextGrad"**。比较对象是"与这些工作公开描述一致的**决策程序**"（idealised decision rules），不是那些系统本身。正文与摘要均须写明这一边界。
- 预注册先行：`PREREG-round5.md` 必须先落盘（含判定规则、指标定义、零的构造方式、失败分支），再运行消融。
- 除 Task 6 外**不新增任何模型调用**；Task 6 预算上限须写进预注册。
- 置换零必须**无放回地重排现有标签**，不得引入新的随机成败；随机源须固定种子且可复算。
- 结论只写实测支持的；不显著一律写"未复现"，不写"不存在"。

---

## File Structure

| 文件 | 职责 |
| --- | --- |
| `results/rounds/round5/PREREG-round5.md` | 冻结协议（先落盘） |
| `scripts/gate_rules.py` | 7 种决策规则的**唯一**实现，统一接口 |
| `scripts/build_pools.py` | 构造置换零池 / 真效应池 + 真值标注 |
| `scripts/ablation_gate.py` | 消融主程序，输出逐规则 × 逐池族指标 |
| `scripts/audit_gate_rules.py` | 独立审计：从原始 JSON 重算每条规则的决定 |
| `results/rounds/round5/pools.json` | 池清单与真值标签（证据） |
| `results/rounds/round5/ablation.json` | 消融结果（证据） |
| `results/rounds/round5/ROUND5-RESULT.md` | 判定记录 |
| `paper/RESULTS.md` / `paper/CLAIM_LEDGER.md` / `paper/DRAFT.md` / `paper/SELF_ASSESSMENT.md` | 写回 |

**统一接口（所有规则必须满足，审计依赖它）：**

```python
# scripts/gate_rules.py
def decide(rule: str, pool: dict) -> dict:
    """pool = {"name": str, "n": int, "blind": bool, "truth": str,
               "items": [{"qid": str, "chal": bool, "inc": bool}, ...]}
    返回 {"promote": bool, "p": float | None, "gain": float,
          "reasons": [str], "recomputable": bool}
    纯函数：同输入必须同输出；不得读网络、时钟、随机源。"""
```

---

### Task 0: 预注册 round5（必须先于一切执行）

**Files:**
- Create: `results/rounds/round5/PREREG-round5.md`

**Interfaces:**
- Consumes: 无
- Produces: 冻结的规则清单、零的构造方式、指标定义、判定分支（后续任务不得违背，违背须写修订声明）

- [ ] **Step 1: 写协议正文**，必须逐条包含：

```
零的构造（核心）：给定一个真实配对池的 discordant 题集 D（|D|=d>0），
  对该 d 道题**逐题独立**以概率 0.5 交换 chal/inc 标签，其余题保持 concordant 不变。
  该重排下真实处理效应恒为 0，且 discordant 总数仍为 d。
  固定种子；对每个真实池生成 K=200 个置换零池。

规则（7 条，实现须忠实于下述语义）：
  R1 gate       : 本工作五键门控；α=0.05，ε=0.02，盲集
  R2 point      : 当且仅当 gain > 0 即晋升（无任何检验）
  R3 unpaired   : 两样本比例检验（非配对）p<0.05 且 gain>=0.02
  R4 nonblind   : 本门控的配对检验，但在选择集（非盲）上计算
  R5 loose      : 本门控但 α=0.20（阈值敏感性）
  R6 no-stat    : 本门控去掉 statistical_passed 一键（保留其余四键）
  R7 bestofk    : 从 k 个候选中按点估计取最优即晋升（选择压力）

池族：
  NULL      : 上述置换零（真值恒 0）
  POSITIVE  : cot-zero vs direct 的真实配对（真值巨大 >0）
  MARGINAL  : 实测小效应对（如 qwen2:7b 的 step-calc vs concise-reason，gain≈+0.05）

指标：
  FPR   = NULL 池中被晋升的比例（越低越好；R2 预期≈0.5，R1 预期≤α）
  TPR   = POSITIVE 池中被晋升的比例（越高越好）
  FPR@k = k 个并列候选下 bestofk 在 NULL 上的假阳率，k=1..8
  可重算性 = audit_gate_rules.py 能逐规则重算决定（布尔）

判定分支（穷尽）：
  (i)  R1 的 FPR 显著低于 R2 与 R7（Wilson 95% 区间不重叠）且 TPR 不低于二者
       → 记录"门控价值成立"
  (ii) 未达 (i)，但 R1 的 FPR@k 曲线显著平于 R2/R7 → 记录"选择压力下价值成立"
  (iii) 全部不达 → 记录"未证实"，N 不上调

预算：Task 1–5 零模型调用；Task 6 ≤ 400 次调用（heldout40 × 5 策略 × 2 次）。
```

- [ ] **Step 2: 冻结并提交**

```bash
git add results/rounds/round5/PREREG-round5.md
git commit -m "round5: preregister gate decision-rule ablation (permutation null, frozen before any run)"
```

---

### Task 1: 池构造器（置换零 + 真效应池）

**Files:**
- Create: `scripts/build_pools.py`
- Test: `tests/test_build_pools.py`
- Output: `results/rounds/round5/pools.json`

**Interfaces:**
- Consumes: `results/rounds/round4/{trackA-merged.json,trackC-*.json}`
- Produces: `build_pools() -> list[dict]`；`permutation_nulls(pool, k, seed) -> list[dict]`

- [ ] **Step 1: 写失败测试** —— 锁定置换零的三条关键性质

```python
def test_permutation_null_has_zero_expected_gain_and_keeps_discordance():
    base = mk_pool(b=9, c=7)                     # 真实池，d=16
    nulls = permutation_nulls(base, k=200, seed=1)
    assert len(nulls) == 200
    for p in nulls:
        assert p["truth"] == "null"
        b = sum(1 for it in p["items"] if it["chal"] and not it["inc"])
        c = sum(1 for it in p["items"] if it["inc"] and not it["chal"])
        assert b + c == 16, "discordant total must be preserved by relabelling"
    gains = [g(p) for p in nulls]
    assert abs(sum(gains) / len(gains)) < 0.05, "mean null gain must be ~0"

def test_permutation_null_is_deterministic_given_seed():
    base = mk_pool(b=9, c=7)
    assert permutation_nulls(base, 50, 3) == permutation_nulls(base, 50, 3)

def test_real_pool_keeps_observed_labels():
    base = mk_pool(b=9, c=7)
    assert base["truth"] == "observed"
    b = sum(1 for it in base["items"] if it["chal"] and not it["inc"])
    assert b == 9
```

- [ ] **Step 2: 运行确认失败**：`python3 -m pytest tests/test_build_pools.py -q` → FAIL（模块不存在）

- [ ] **Step 3: 实现**。关键点：**只重排 discordant 题**，concordant 题不动；`random.Random(seed)`；每池记录 `name/truth/n/blind/items/meta{source_pool,discordant_total,seed}`。

- [ ] **Step 4: 运行确认通过**

- [ ] **Step 5: 落盘 `pools.json`**（含 observed 池 + 各自的 200 个置换零），提交

---

### Task 2: 7 条决策规则实现（统一接口）

**Files:**
- Create: `scripts/gate_rules.py`
- Test: `tests/test_gate_rules.py`

**Interfaces:**
- Consumes: `evokit.stats.{mcnemar_two_sided, ledger_ok}`
- Produces: `decide(rule: str, pool: dict) -> dict`（接口见 File Structure）

- [ ] **Step 1: 写失败测试** —— 用**手工构造的**小池锁定每条规则语义

```python
def test_r2_point_promotes_on_any_positive_gain():
    pool = mk_pool(b=3, c=2)                       # gain>0 但不显著
    assert decide("R2", pool)["promote"] is True
    assert decide("R1", pool)["promote"] is False

def test_gate_never_promotes_on_exact_tie():
    assert decide("R1", mk_pool(b=2, c=2))["promote"] is False

def test_r6_without_stat_key_promotes_on_gain_alone():
    pool = mk_pool(b=3, c=2)
    assert decide("R6", pool)["promote"] is True
    assert decide("R1", pool)["promote"] is False

def test_r4_requires_blind_flag():
    pool = mk_pool(b=9, c=4, blind=False)
    assert decide("R4", pool)["promote"] is True      # 非盲：只用配对检验
    assert decide("R1", mk_pool(b=9, c=4, blind=False))["promote"] is False  # 门控要求盲

def test_all_rules_are_pure():
    pool = mk_pool(b=9, c=4)
    for r in ["R1","R2","R3","R4","R5","R6","R7"]:
        assert decide(r, pool) == decide(r, pool), f"{r} not pure"
```

- [ ] **Step 2: 运行确认失败**

- [ ] **Step 3: 实现**：R1/R5/R6 共用 `_gate(pool, alpha, eps, use_stat_key)`；R2 只看 gain；R3 非配对两比例检验（docstring 写明所用形式，如 Fisher 精确或正态近似）；R4 用配对检验但忽略 `blind` 约束；R7 由 Task 4 传入候选列表。

- [ ] **Step 4: 运行确认通过** → **Step 5 提交**

---

### Task 3: 池族装配与规模校核

**Files:**
- Modify: `scripts/build_pools.py`
- Test: `tests/test_build_pools.py`（追加）

- [ ] **Step 1: 写失败测试**：断言三族齐备、规模符合预注册、且**覆盖多个 discordance 水平**

```python
def test_pool_families_present_and_sized():
    pools = build_pools()
    nulls = [p for p in pools if p["truth"] == "null"]
    obs   = [p for p in pools if p["truth"] == "observed"]
    assert len(nulls) >= 400, "expected >=400 permutation-null pools"
    srcs = {p["meta"]["source_pool"] for p in obs}
    assert any(s.startswith("positive") for s in srcs)   # cot-zero vs direct
    assert any(s.startswith("marginal") for s in srcs)   # step-calc vs concise-reason
    # 硬性约束（见"设计验证"）：α/非配对臂需要大 d 池
    assert any(p["meta"]["discordant_total"] >= 15 for p in obs), \
        "need a large-discordance observed pool for the alpha/unpaired arms"
    assert all(p["n"] > 0 for p in pools)
    assert all(p["blind"] in (True, False) for p in obs)
```

- [ ] **Step 2: 运行确认失败**

- [ ] **Step 3: 实现观测池装配**。观测池清单（每个配 200 个置换零）：
  - `positive-cotzero-vs-direct`（trackA，d=159）
  - `mid-stepcalc-vs-cotzero`（trackA，d=16）— **α/非配对臂的主池**
  - `mid-stepcalc-vs-fewshot`（trackA，d=23）
  - `marginal-stepcalc-vs-concise`（qwen2:7b，d=6）
  并按 `blind` 字段标注该池取自盲集还是选择集（R4 依赖它）。

- [ ] **Step 4: 运行确认通过** → **Step 5 提交**

---

### Task 4: 消融主实验

**Files:**
- Create: `scripts/ablation_gate.py`
- Output: `results/rounds/round5/ablation.json`

**Interfaces:**
- Consumes: Task 1/3 的池、Task 2 的 `decide`
- Produces: `{"fpr": {...}, "tpr": {...}, "k_curve": {...}, "verdict_branch": "i"|"ii"|"iii"}`

- [ ] **Step 1: 实现 `run_ablation()`**：
  - 逐规则：`FPR = mean(decide(r,p)["promote"] for p in NULL)`；`TPR` 在 POSITIVE 上同理
  - R1 vs R2/R7：报 Wilson 95% 区间（不重叠即判"低于"），并另报同一批零池上的配对 McNemar
  - `k_curve`：对每个 NULL 池构造 k 个"候选"（对该池再做 k 次独立标签置换），`R7` 取点估计最优；`FPR@k`，k=1..8
  - 依预注册三分支给 `verdict_branch`

- [ ] **Step 2: 运行并落盘** → **Step 3 打印人类可读摘要（FPR/TPR 表 + k 曲线 + 分支）** → **Step 4 提交**

---

### Task 5: 独立审计（可重算性验证）

**Files:**
- Create: `scripts/audit_gate_rules.py`

**Interfaces:**
- Consumes: `pools.json`、`ablation.json`、`gate_rules.py`
- Produces: exit 0 iff 每条规则的决定都能从原始 JSON 重算且与落盘一致

- [ ] **Step 1: 实现**：绕开 `ablation_gate.py`，用 `build_pools()` + `decide()` 重算全部决定，逐条比对
- [ ] **Step 2: 运行确认 exit 0**
- [ ] **Step 3: 故意篡改 `ablation.json` 一个布尔值 → 确认审计 exit 1（证明非空转）→ 恢复**
- [ ] **Step 4: 提交**

---

### Task 6: proposer 替代臂（唯一需新生成的实验，可选）

**Files:**
- Create: `scripts/run_proposer_arm.py`
- Output: `results/rounds/round5/proposer-arm-*.json`

- [ ] **Step 1: 在预注册预算内（≤400 次调用）运行**，`qwen2.5:7b`，heldout40，文本批判式提议器
- [ ] **Step 2: 用与 Track C 同口径汇总（headline：该提议器产物 vs cot-zero）**
- [ ] **Step 3: 落盘 + 提交**
- [ ] **Step 4: 若预算/机器不允许，明确记为"未执行"，不得用其它数据代替**

---

### Task 7: 写回论文与自评

**Files:**
- Modify: `paper/CLAIM_LEDGER.md`、`paper/RESULTS.md`、`paper/DRAFT.md`、`paper/SELF_ASSESSMENT.md`

- [ ] **Step 1: 新增 claim**（C25…）逐条挂 `文件:行`；新增"不得写入正文"的声明（禁止声称复现了相关系统）
- [ ] **Step 2: `RESULTS.md` 新增 §6 消融**；`DRAFT.md` 相关工作段把"自我声明差异"换成"实测差异"，边界写进 Limitations
- [ ] **Step 3: `SELF_ASSESSMENT.md` 依 `verdict_branch` 定 N**：分支 (i)/(ii) → N=3（给理由）；分支 (iii) → N 保持 2，如实记"未证实"
- [ ] **Step 4: 机器检查**：`check_publish.py`、`pytest`、`verify_question_provenance.py` 全绿；DRAFT 数字重算全过
- [ ] **Step 5: 提交并同步 `main`（worktree 方式）**

---

## Edge Cases and Failure Modes

- **置换零与原池共享题目**：同一真实池的 200 个零池共享同一批题，**不是独立样本**。故 Wilson 区间须按此保守解释，并在正文声明"零池来自重排、非独立抽样"。可另加"跨池"零池（不同策略、不同题集）作稳健性补充，单独报告。
- **R2 的 FPR 预期≈0.5 是构造使然**：这是"无错误控制"的应有之义，转述时必须说明，不得包装成"我们发现基线很差"。
- **R1 的 FPR 可能为 0**（离散检验在小 d 下保守）：如实报告 0 与区间上界，不得写成"零错误率"。
- **预注册被违反**：任何偏离须在 `ROUND5-RESULT.md` 顶部写"修订声明"。
- **不得把 idealised 规则说成真实系统**：正文与摘要均须写明。
- **机器内存压力**：Task 1–5 零模型调用不受影响；Task 6 若失败记为未执行。

## Self-Review

- **Spec coverage**: 目标（N 2→3）→ Task 7 Step 3；"同条件对比"→ Task 4 同池同指标；"不得声称复现"→ Global Constraints + Task 7 Step 1；"零新增调用"→ Task 6 单列且设预算上限；**开工前修正**→ 置换零构造（Task 0/Task 1 已按实测改写）。
- **Placeholder scan**: 无 TBD/TODO；测试步骤给出可运行代码；`mk_pool`/`g` 为测试夹具，在使用处就地定义。
- **Type consistency**: `decide(rule, pool)` 与 `pool` 结构（含 `truth`/`blind`）在 File Structure 单处定义，Task 1–5 全部引用同一签名；`truth ∈ {null, observed}` 全程一致（初稿的 `positive/marginal` 改为 `observed` + `meta.source_pool`，避免"真值类别"与"效应方向"混淆）。

## Execution Handoff

Plan complete and saved to `paper/PLAN-NOVELTY.md`. Two execution options:

1. **Subagent-Driven (recommended)** — 每任务派新 subagent，任务间我来审，迭代快
2. **Inline Execution** — 本会话内按 executing-plans 批量执行，设检查点

Which approach?
