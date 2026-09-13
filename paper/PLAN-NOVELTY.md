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
marginal 池实测   : qwen2:7b (chal=step-calc, inc=concise-reason)  b=2 c=4 d=6  p=0.688 gain=-0.050
positive 池实测   : trackA  (chal=cot-zero, inc=direct)            b=159 c=0 d=159 p=2.7e-48 gain=+0.795

置换零（d 保持 =6，mean gain = -0.0029 ≈ 0 ✓）：
  R1 gate      FPR = 0.015
  R2 point     FPR = 0.320
  R6 no-stat   FPR = 0.320   # AMENDMENT 1 语义：保留 ε 阈值，仅去显著性检验
  R7 bestofk   FPR: k=1 → 0.357 ；k=2 → 0.620 ；k=4 → 0.838 ；k=8 → 0.968
```

结论（仅说明当时的设计意图；其中数字已被取代、不得引用）：设计当时看起来有区分度——门控把假阳压到 0.015，
而点估计 / 仅去显著性检验（保留 ε 阈值）为 0.32，选择压力下 naive 规则升到 0.97。
这正是预注册三分支要检验的东西。

> **以上 pilot 数字已被取代（controller ruling 10 / `PREREG-round5.md` §7.1）：作废、不可引用。**
> 该临时 pilot **未记录任何 seed**，也未逐指标记录 `(K, seed)`：其 FPR 位于 `/2000` 网格
> （0.015 = 30/2000，0.320 = 640/2000），而 FPR@k 中有三个值**不在交付运行 `K=200` 的网格上**
> （0.357 × 200 = 71.4、0.838 × 200 = 167.6、0.968 × 200 = 193.6 均非整数），因此这段文字
> 无法由任何单一已记录的 `(K, seed)` 复现，且无 pilot 脚本/产物落盘。
> **Task 1 必须先把重跑脚本提交、再运行**，并**逐指标**记录显式 `K` 与 seed；只有重跑后的数值
> 才可成为可引用的 pilot（与 `PREREG-round5.md` §7 一致）。

> 注意：以上 pilot 数字（mean gain、各 FPR、FPR@k）**仅为设计证据，尚不可由已提交产物重算**
> （无 pilot 池文件落盘），且已被上一条取代；只有 Task 1 的重跑脚本（先提交）连同其
> `(metric, K, seed)` 记录落盘后，这些数值才可作为结果引用 —— 与 `PREREG-round5.md` §7.3 一致。

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
- 置换零的操作是**对 discordant 题逐题独立地以 p=0.5 交换 chal/inc 标签**（复用现有标签、不引入新的随机成败），**不是保计数的标签置换**：逐题独立交换下 `b' ~ Binomial(d, 0.5)`、`E[gain] = 0`；而保计数置换会保留原 `(b, c)`，使 mean gain 非零，与本计划"mean gain≈0"的判据冲突。随机源固定为 `SEED=20260912`，逐池 child seed 与随机数消费顺序见 `PREREG-round5.md` §1。该逐题重排是 **NULL 族**（零池与 NULL 族候选）的构造；POSITIVE 族的 R7 候选用**保标签的题 bootstrap**（有放回重抽题、`chal`/`inc` 标签原样保留，真效应不被抹掉），它既不是零构造、也不产生零池（`PREREG-round5.md` §1 rule 5、§3、§5.2）。
- 结论只写实测支持的；不显著一律写"未复现"，不写"不存在"。

---

## File Structure

| 文件 | 职责 |
| --- | --- |
| `results/rounds/round5/PREREG-round5.md` | 冻结协议（先落盘） |
| `scripts/gate_rules.py` | 7 种决策规则的**唯一 canonical** 实现，统一接口（Ruling 18：`scripts/pilot_round5.py` 里的规则码是 **pilot-local**，Task 2 交付后必须与本模块对账——或加等价性测试（在 pilot 的参数上），或把 pilot 经本模块重跑并披露更新后的数值） |
| `scripts/build_pools.py` | 构造置换零池 / 真效应池 + 真值标注 + `pools.json` 顶层 `meta` 描述（由 `pools_meta()` 从池**计算**；R4 **可评估**，`r4_status` / `r4_evaluable` / `r4_note` / `byte_stability_0_3` 一并重算），并导出**唯一**读取器 `load_pools_json()` |
| `scripts/ablation_gate.py` | 消融主程序，输出逐规则 × 逐池族指标；**R4 行必须计算**——在 roster indices 4–9 的六个非盲选择集池上逐池给出配对检验决定（PREREG §5A） |
| `scripts/audit_gate_rules.py` | 独立审计：从原始 JSON 重算每条规则的决定（候选池必须用 `build_pools.py` 的已发布函数现场重算，不得读内嵌副本；**R4 同样重算**并与 `meta.r4_status` / `meta.r4_evaluable` 对账） |
| `results/rounds/round5/pools.json` | 池清单与真值标签（证据）。形如 `{"meta": {...}, "pools": [...]}`：每池一行；顶层 `meta` 由 `pools_meta()` 从池计算（`n_blind_pools` / `n_nonblind_pools` / `all_artefact_pools_blind` / `no_nonblind_pool_in_artefact` / `r4_evaluable` / `r4_status` / `r4_note` / `byte_stability_0_3`）。**必须用 `scripts/build_pools.py` 的 `load_pools_json()` 读取**——裸 `json.loads` 得到的是错误形状（`{"meta":…,"pools":[…]}` 而非池数组） |
| `results/rounds/round5/ablation.json` | 消融结果（证据） |
| `results/rounds/round5/ROUND5-RESULT.md` | 判定记录 |
| `paper/RESULTS.md` / `paper/CLAIM_LEDGER.md` / `paper/DRAFT.md` / `paper/SELF_ASSESSMENT.md` | 写回 |

**统一接口（所有规则必须满足，审计依赖它）：**

```python
# scripts/gate_rules.py
def decide(rule: str, pool: dict) -> dict:
    """pool = {"name": str, "n": int, "blind": bool, "truth": str,
               "chal_policy": str, "inc_policy": str,
               "hidden_passed": True, "safety_passed": True,
               "rollback_available": True, "bundle_signature_valid": True,
               "items": [{"qid": str, "chal": bool, "inc": bool}, ...]}
    返回 {"promote": bool, "p": float | None, "gain": float,
          "reasons": [str], "recomputable": bool}
    纯函数：同输入必须同输出；不得读网络、时钟、随机源。
    `hidden_passed` / `safety_passed` / `rollback_available` / `bundle_signature_valid`
    是池构造置 true 的**结构性常量**（PREREG-round5.md §1）：R1/R5/R6 的合取在池上因此
    退化为 statistical_passed / gain 判据；Task 1/2 的测试须断言四者为 True，使门控的
    负结论非空转。`chal_policy`/`inc_policy` 为 §1.1 的方向声明，缺一不可（符号增益不得
    脱离方向转录）。"""
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
  固定种子 SEED=20260912；每池 child_seed = SEED + source_pool_index
  （source_pool_index = 观测池在 Task 3 花名册中的 0 基序号；PREREG §1 的
  **Observed-pool roster (frozen)** 逐条列出同一序号，两处均不得重编号或换序）；每个源池一个
  random.Random(child_seed)，按 null index i=0..K-1 递增、逐题顺序各消费一次随机数
  （swap 当且仅当 draw < 0.5）；不得逐 null 重新播种。该实例在 K=200 个 null 块**之后**
  继续消费**候选块**（声明扩展，不得与 null 块交错），候选构造**按池族取用**
  （binding — PREREG §1 rule 5 / §5.2）：
    · NULL 族候选 = 重排（relabelling）：对 i=0..K-1、候选号 j=1..8 各消费一个块，
      逐 discordant 题按冻结题序各消费一次随机数（swap 当且仅当 draw < 0.5），
      得到候选池 C(source_pool, i, j)——真效应恒 0，这正是 NULL 族评价需要的候选；
    · POSITIVE 族候选 = **保标签的题 bootstrap**（label-preserving item bootstrap）：
      只对 POSITIVE 源池、且在 NULL 族候选流全部消费完之后：候选号 j=1..8
      （POSITIVE 单元只有 1 个，记 i=0），每块抽 n 次 u=rng.random()，按 int(u×n)
      从该池冻结题序中**有放回**重抽题，题目的 chal/inc 标签**原样保留**；
      候选项因此始终带着观测到的正效应，是合法的正例抽法。POSITIVE 族上做重排
      （把真效应抹成 0）是禁止的，正如 NULL 族上必须重排；两族候选不得混用。
    嵌套次序：i 外层、j 内层（单位 i 的候选块全部消费完才进入 i+1），块内按冻结题序；
    k 子集＝该单元候选块的前缀 j=1..k。
  R7 的操作性读数固定为 **k=8**（见本节末 R7 绑定说明与 PREREG §5.2）：候选独立于
  同一单元的 R2 零池；k=1 退化读法（接口无 candidates 时即池本身 ≡ R2）**不是**操作性读数，
  曲线端点 k=1（＝候选块 (i,1)，真实候选池）也不是。
  d==0 的池**不得作为 null 源**：permutation_nulls 抛 ValueError、build_pools 拒绝，
  不得静默跳过（静默跳过会无记录地缩小 FPR 分母）；如确有需要，只能作为 observed 池
  并在 Task 3 花名册（0..3 序号，见下文 Task 3 观测池清单）中显式声明"非 null 源"。测试须断言
  len(nulls) == K × (声明的 null 源数)。
  对每个真实池生成 K=200 个置换零池。
  所有池（observed 与 null）由构造置 hidden_passed = safety_passed =
  rollback_available = bundle_signature_valid = True（结构性常量，使 R1 的
  "五键合取"在池上退化为 statistical_passed，从而 R1 的负结论非空转）。

规则（7 条，实现须忠实于下述语义）：
  R1 gate       : 本工作五键门控；α=0.05，ε=0.02，盲集
  R2 point      : 当且仅当 gain > 0 即晋升（无任何检验）
  R3 unpaired   : 两样本比例检验（非配对）p<0.05 且 gain>=0.02
  R4 nonblind   : 本门控的配对检验，但在选择集（非盲）上计算（忽略 blind 约束）
                  **EVALUATED（correction round；PREREG-round5.md §5A）**：本仓库**确实存在**
                  非盲逐题数据——`results/runs/*.json` 的 `baseline.outcomes[]` /
                  `candidates[].evaluation.outcomes[]` 携带逐题 `{task_id, passed, details{policy}}`，
                  `results/rounds/round3/pilot-train40.json` 携带同粒度逐题数据
                  （`"oracle": "train-only"`）；此前"result/runs 只有聚合字段、故 R4 不可评估"的
                  结论是 **controller 的顶层键浅检查错误**，已更正。**Task 4 必须计算 R4 列**：
                  在 roster indices 4–9 的六个非盲选择集池上逐池给出配对精确 McNemar 决定
                  （α=0.05、gain>=ε=0.02），每行带 `(chal_policy, inc_policy)` 方向与
                  promoted/total 分母；Task 5 必须重算并与 `meta.r4_status` / `meta.r4_evaluable` 对账。
                  边界（binding）：这五个池是本循环**自己的选择集**（这正是 "non-blind" 的定义），
                  不得读出任何泛化声明；它们不是 null 源，故不产生零池，**不得报 R4 的 FPR**
                  （没有非盲零集），只报逐池决定；R1 因 §2 自身的 `pool["blind"] is True` 要求而
                  **按定义**拒绝全部五个，此点必须照实写明、不得当作发现。
                  由注册表的聚合选择集计数合成非盲池的做法仍然否决（不可验证的构造；构造 ≠ 测量，
                  且此处已有真实逐题数据，无需合成）。
                  Task 2 实现该规则；Task 4 计算；Task 5 重算校验
  R5 loose      : 本门控但 α=0.20（阈值敏感性）
  R6 no-stat    : 本门控保留效应量阈值 gain >= ε=0.02，仅去掉显著性检验
                  （原措辞"去掉 statistical_passed 一键（保留其余四键）"语义歧义，
                    采用语义见 PREREG-round5.md 的 AMENDMENT 1）
  R7 bestofk    : 从 k 个候选中按点估计取最优即晋升（选择压力）；
                  本文档所有 R7 **判定/决策**读数的 k **固定为 8**（k=8 于交付运行前钉住），
                  候选**按池族取用**（NULL 族=重排；POSITIVE 族=保标签题 bootstrap，见上），
                  与同单元 R2 零池独立；见本节末 R7 绑定说明。
                  描述性 k=1..7 曲线**照旧必须报告**（非判定读数，不受本 pin 约束）

池族：
  NULL      : 上述置换零（真值恒 0）
  POSITIVE  : cot-zero vs direct 的真实配对（真值巨大 >0）
              方向声明 (chal_policy=cot-zero, inc_policy=direct)：b=159 c=0 d=159 gain=+0.795
  MARGINAL  : 实测小效应对（qwen2:7b），方向声明
              (chal_policy=step-calc, inc_policy=concise-reason)：b=2 c=4 d=6 gain=-0.050；
              同一池反向读作 concise-reason(chal) 时 gain=+0.05。符号增益不得脱离方向转录
              （见 PREREG-round5.md §1.1 / §3）

指标：
  FPR   = NULL 池中被晋升的比例（越低越好；R2 的期望 = (1 − P(tie))/2，不是 0.5：
          d=6 时 P(tie)=C(6,3)/2^6=20/64=0.3125 → E[FPR_R2]=0.34375；只有大 d 池趋近 0.5。
          R1 预期≤α）
  TPR   = POSITIVE 池中被晋升的比例（越高越好）；本文件 POSITIVE 池只有 1 个
          → 分母 = 1：TPR 比较只是“R1 不掉真阳”的健全性检查（防空转），
          对规则之间**无鉴别力**，不得据此声称 R1 在 TPR 上优于 R2/R7（PREREG §5.1(c)）
  FPR@k = k 个并列候选下 bestofk 在 NULL 上的假阳率，k=1..8；
          k 子集＝该单元候选块的前缀 j=1..k（同一嵌套流，不是每个 k 重抽）；
          k=8 端点记为 FPR_R7@8（即 FPR@8(R7)，与 (i) 的 R7 项同一数量），
          (i)/(ii) 均只读该端点；k=1..7 仅作描述性曲线且 Task 4 必须报告；
          曲线端点 k=1＝候选块 (i,1)（真实候选池，≠ 池本身）——它既不是 k=1
          退化读法（接口无 candidates ⇒ 池本身），也不得替代 k=8
  可重算性 = audit_gate_rules.py 能逐规则重算决定（布尔）

判定分支（穷尽；精确统计量与比较式以 PREREG-round5.md §5/§5.1 为准）：
  (i)  R1 的 FPR 显著低于 R2 与 R7 且 TPR 不低于二者：
       pooled FPR_r = 晋升的 NULL 池数 / NULL 池总数（同一 NULL 集）；
       "低于" 定义为 WilsonUpper95(FPR_R1) < WilsonLower95(FPR_R2)
       且 WilsonUpper95(FPR_R1) < WilsonLower95(FPR_R7@8)（区间不重叠、R1 在下方；R7 读 k=8）
       （R7@8 = 在 k=8 个候选池上按点估计取最优；候选由候选块生成、不得用该单元自己的零池）
       且同一批 NULL 上的配对精确 McNemar（配对单位 = (source_pool, null_index)，
       每个源池恰 K=200 个配对单位，不得跨源池配对）对两个比较都同向且双侧 p < 0.05；
       R7 比较的单元决策 = bestofk 在该单元自己的 k=8 个候选池上取最优（候选块生成，
       该单元自身的 R2 零池不参与），不得以 k=1 退化读法替代；
       "TPR 不低于" = TPR_R1 >= TPR_R2 且 TPR_R1 >= TPR_R7@8（POSITIVE 池点估计；R7 同为
       k=8，且候选用 POSITIVE 族保标签 bootstrap——绝不用重排候选量真阳率）
       ——本文件 POSITIVE 池仅 1 个、分母 = 1：此款是“R1 不掉真阳”的健全性检查，
       对规则之间**无鉴别力**，不得据此声称 R1 在 TPR 上优于 R2 或 R7
       → 记录"门控价值成立"
  (ii) 未达 (i)，但 R1 的 FPR@8 同时低于 R2、R7 的 FPR@8 的 Wilson 下界：
       FPR@8(R1) < WilsonLower95(FPR@8(R2)) 且 FPR@8(R1) < WilsonLower95(FPR@8(R7))
       （FPR@8(R7) 即 FPR_R7@8：与 (i) 的 R7 项是同一个 k=8 统计量，两分支不得漂移）
       （k=8 为预注册最大 k，运行后不得改用其它 k；"曲线显著更平"不是判定装置）
       → 记录"选择压力下价值成立"
  (iii) 全部不达 → 记录"未证实"，N 不上调

预算：Task 1–5 零模型调用；Task 6 ≤ 400 次调用（heldout40 × 5 策略 × 2 次）。
```

> **R6 语义（binding，修正后）**：上表 R6 行原措辞"去掉 `statistical_passed` 一键（保留其余四键）"
> 有歧义——在本研究的池上其余四键是结构性常量，字面读法会使 R6 恒晋升、与实测 pilot FPR 0.320
> 矛盾。该歧义已由 `results/rounds/round5/PREREG-round5.md` 的 **AMENDMENT 1**（2026-09-12，
> 交付运行前）裁定为：**保留效应量阈值 `gain >= ε=0.02`，仅去掉显著性检验**。本计划 R6 行已按该语义
> 更正；Task 2 的 R6 测试与 Task 4 的 R6 列均以 AMENDMENT 1 为准，不得再按字面读法实现或报告。

> **R7 操作性读数（binding — k=8 于交付运行前钉住，只界定 R7 的判定/决策读数）**：与分支 (ii)
> 一致，本文档中一切 R7 **判定/决策**读数（分支 (i) 的 FPR 与 TPR、分支 (ii) 的 FPR@8）一律取
> **k=8**，记为 `FPR_R7@8`（即 `FPR@8(R7)`）与 `TPR_R7@8`。**本 binding 不覆盖描述性曲线**：
> 指标表要求 Task 4 报告的 `FPR@k` 曲线 k=1..7 照旧**必须报告**，它是描述性读数、不是判定装置，
> 不受 k=8 约束，也不得被当作判定依据。候选**按池族取用**（PREREG §1 rule 5）：NULL 族判定用
> §1 候选块生成的、属于该 `(source_pool, null_index)` 单元自己的 8 个重排候选池
> `C(source_pool, i, j)`，`j=1..8`；POSITIVE 族判定（`TPR_R7@8`）用**保标签的题 bootstrap**
> 候选 `C_pos(source_pool, i=0, j)`，`j=1..8`，绝不用重排候选量真阳率。不得复用该单元自身的
> R2 零池，以保持 §7.2 的独立性关系。**k=1 退化读法（接口无 `pool["candidates"]` 时退化为池
> 本身、行为等同于 R2）不是操作性读数**，且与曲线端点 k=1（＝候选块 (i,1)，真实候选池）
> 是两回事；任何以 k=1 代替 k=8 的报告必须先写修订声明。完整定义见
> `results/rounds/round5/PREREG-round5.md` §5.2。

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
- Create (Ruling 10): `scripts/pilot_round5.py`（重跑设计期 pilot 的已提交脚本；**已交付，采用此文件名**，Ruling 19）
- Output: `results/rounds/round5/pools.json`、`results/rounds/round5/PILOT.json`（**已交付，采用此文件名**，Ruling 19）

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

def test_every_pool_carries_structural_keys_true():
    for p in build_pools():                       # observed + permutation-null
        for k in ("hidden_passed", "safety_passed",
                  "rollback_available", "bundle_signature_valid"):
            assert p[k] is True, (p["name"], k)   # makes R1 non-vacuous

def test_zero_discordance_pool_is_rejected_not_silently_skipped():
    with pytest.raises(ValueError):
        permutation_nulls(mk_pool(b=0, c=0), k=200, seed=20260912)
```

- [ ] **Step 2: 运行确认失败**：`python3 -m pytest tests/test_build_pools.py -q` → FAIL（模块不存在）

- [ ] **Step 3: 实现**。关键点：**只重排 discordant 题**，concordant 题不动；`SEED=20260912`，每池 `random.Random(SEED + source_pool_index)` 且**不得逐 null 重新播种**（消费顺序见 Task 0 的"零的构造"）；`d==0` 抛 `ValueError`，不得静默跳过；每池记录 `name/truth/n/blind/chal_policy/inc_policy/hidden_passed/safety_passed/rollback_available/bundle_signature_valid/items/meta{source_pool,discordant_total,seed}`。候选流必须**按池族取用**（NULL 族重排、POSITIVE 族保标签题 bootstrap，见 Task 0「零的构造」与 PREREG §1 rule 5）：k 子集＝该单元候选块的前缀 j=1..k。

- [ ] **Step 4: 运行确认通过**

- [ ] **Step 5: 落盘 `pools.json`**（含 observed 池 + 各自的 200 个置换零），提交

- [ ] **Step 6: 重跑 pilot 并落盘（controller ruling 10）**：把设计期 mini pilot 写成仓库内脚本
  `scripts/pilot_round5.py`（Ruling 19：以此交付文件名为准，早期计划文本里的 `run_pilot.py` 作废），
  **先提交脚本、再运行**；对**每个**报告指标记录显式 `K` 与 seed，
  输出落盘 `results/rounds/round5/PILOT.json`（Ruling 19：以此交付文件名为准，早期文本里的 `pilot.json` 作废）
  并提交。只有这一步产出的数值可成为可引用的 pilot
  （`PREREG-round5.md` §7.1）；设计期 ad-hoc pilot 的数值已作废，不得引用、不得复制进任何产物。

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

- [ ] **Step 3: 实现**：R1/R5/R6 共用 `_gate(pool, alpha, eps, use_stat_key)`；R2 只看 gain；R3 非配对两比例检验（docstring 写明所用形式，如 Fisher 精确或正态近似）；R4 用配对检验但忽略 `blind` 约束（**correction round：本仓库**确实**有非盲逐题池——roster indices 4–9 的六个选择集池（fix round 3 补入 index 9 后该块穷尽）——故 R4 必须被实现，且必须在本研究语料上被评估（Task 4 计算、Task 5 重算校验）；Task 2 只需实现 + 手工池单测，见 File Structure 与 PREREG §5A**）；R7 由 Task 4 传入候选列表，**操作性读数固定 k=8**（候选由 Task 1 的候选块生成，`C(source_pool, i, j)`，`j=1..8`；候选构造**按池族取用**——NULL 族重排、POSITIVE 族保标签题 bootstrap（`C_pos`），不得混用；无 candidates 时的 k=1 退化路径仅作为接口行为并在 docstring 写明，不得作为操作性读数，见 PREREG §5.2）。

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
    assert len(obs) == 10, "4 blind + 6 non-blind (correction + fix round 3) observed pools"
    srcs = {p["meta"]["source_pool"] for p in obs}
    assert any(s.startswith("positive") for s in srcs)   # cot-zero vs direct
    assert any(s.startswith("marginal") for s in srcs)   # step-calc vs concise-reason
    assert len([s for s in srcs if s.startswith("nonblind-")]) == 6
    # 硬性约束（见"设计验证"）：α/非配对臂需要大 d 池
    assert any(p["meta"]["discordant_total"] >= 15 for p in obs), \
        "need a large-discordance observed pool for the alpha/unpaired arms"
    assert all(p["n"] > 0 for p in pools)
    # 每个池的 blind 必须与其声明来源一致（盲集 True / 选择集 False）；
    # 不再断言"没有非盲池"——那是建立在错误前提上的断言
    check_blind_labels(pools)
```

- [ ] **Step 2: 运行确认失败**

- [ ] **Step 3: 实现观测池装配**。观测池清单（**frozen roster，0 基序号即 `source_pool_index`，与 PREREG §1 的 Observed-pool roster (frozen) 一一对应，不得重编号或换序**）：
  - index 0 `positive-cotzero-vs-direct`（trackA，d=159）
  - index 1 `mid-stepcalc-vs-cotzero`（trackA，d=16）— **α/非配对臂的主池**
  - index 2 `mid-stepcalc-vs-fewshot`（trackA，d=23）
  - index 3 `marginal-stepcalc-vs-concise`（qwen2:7b，d=6）
  - index 4–9 **非盲选择集池**（correction round 追加 4–8、fix round 3 追加 9，`blind = False`，
    声明 *not a null source*）：
    `nonblind-concise-vs-direct`（d=20）、`nonblind-doublecheck-vs-direct`（d=6）、
    `nonblind-stepcalc-vs-concise`（d=10）、`nonblind-rectify-vs-concise`（d=8）、
    `nonblind-reflect-vs-stepcalc`（d=4）、
    `nonblind-roundingaware-vs-concise`（d=10，run `20260908-235617` 的第三个候选臂，n=40
    b=8 c=2 gain=+0.150，精确 McNemar p=0.109375）；逐题数据来自 `results/runs/*.json` 的
    `baseline.outcomes[]` / `candidates[].evaluation.outcomes[]` 与
    `results/rounds/round3/pilot-train40.json`（`"oracle": "train-only"`），**按记录在案的
    `(baseline policy, candidate policy)` / `oracle` 定位文件，不得凭文件名取用**；
    每个源文件必须**独立重算** `(n, b, c, d, gain)` 并与 PREREG §5A 的表逐项相等，不等即失败。
  并按 `blind` 字段标注该池取自盲集还是选择集（R4 依赖它）。**indices 0–3 四池全部 `blind = True`，
  indices 4–9 六池全部 `blind = False`；两类来源都真实存在，故 R4 **可评估**（Ruling 17 的
  "not evaluated" 结论建立在"results/runs/*.json 只有聚合字段"这一**错误前提**上，已在
  correction round 更正；见 PREREG §5A）。** 每池的 `blind` 必须与其**声明的来源**一致
  （盲 held-out 集 → `True`；选择集 → `False`；null 池继承源池标签），并由 `check_blind_labels()`
  断言、由测试证明误标必然失败。`pools.json` 的顶层 `meta` 必须由 `pools_meta()` 从池**计算**
  （`n_blind_pools` / `n_nonblind_pools` / `all_artefact_pools_blind` / `no_nonblind_pool_in_artefact` /
  `r4_evaluable` / `r4_status` / `r4_note` / `byte_stability_0_3`），`all_pools_blind` 等方法名不得再出现
  （它们宣称的是语料级事实，而实际只统计本 artefact 的池）。**indices 4–9 是 rule 4 的
  *not a null source* 逃生口：它们不产生置换零池**，所以 NULL 集仍恰为 indices 0–3 的 800 个零池，
  且 indices 0–3 的池必须与 correction 前的 artefact **逐字节相同**（由
  `PRE_CORRECTION_0_3` 锚定 + 测试从 git commit 读回原 artefact 校验）。**

- [ ] **Step 4: 运行确认通过** → **Step 5 提交**

---

### Task 4: 消融主实验

**Files:**
- Create: `scripts/ablation_gate.py`
- Output: `results/rounds/round5/ablation.json`

**Interfaces:**
- Consumes: Task 1/3 的池、Task 2 的 `decide`。**`pools.json` 必须经
  `scripts/build_pools.py::load_pools_json()` 读取**（artefact 形状是 `{"meta":…,"pools":[…]}`；
  裸 `json.loads` 得到的是错误形状，且会绕过描述/盲标一致性校验）
- Produces: `{"fpr": {...}, "tpr": {...}, "k_curve": {...}, "r4": {...}, "verdict_branch": "i"|"ii"|"iii"}`

- [ ] **Step 1: 实现 `run_ablation()`**：
  - 逐规则：`FPR = mean(decide(r,p)["promote"] for p in NULL)`；`TPR` 在 POSITIVE 上同理
  - **R4 必须计算（correction round；PREREG §5A）**：对 roster indices 4–9 的六个**非盲选择集池**
    逐池调用 `decide("R4", p)`，报 `{"per_pool": [{pool, chal_policy, inc_policy, gain, p, promote}],
    "promoted": k, "total": 6}`，并在同一张表上并列 R1 对**同样这六个池**的决定。
    边界（binding）：**不得报 R4 的 FPR**（无非盲零集，不得发明）；**不得**把这些选择集池的结果
    当成泛化证据；R1 拒绝全部六个是其定义（`pool["blind"] is True`）的必然结果，须照实标注，
    不得叙述成发现。`ablation.json` 的 R4 区块须与 `pools.json` 的 `meta.r4_status` /
    `meta.r4_evaluable` 对账。§5 的三个分支都不读 R4，故分支判定不受影响
  - **每一行都必须携带声明的方向 `(chal_policy, inc_policy)`（Ruling 20；PREREG §1.1）**：
    逐池行、pooled 行、k 曲线行、TPR 行概莫能外——有符号的 gain 一律与方向同格出现，
    不得脱离方向转录（如 `mid-stepcalc-vs-cotzero` 在 `(chal=step-calc, inc=cot-zero)` 下 gain = −0.010，
    反向读作 +0.010，是同一个池）。落盘 `ablation.json` 的每一行都要有这两个字段，便于审计逐行核对
  - R1 vs R2/R7：报 Wilson 95% 区间与 pooled FPR；"低于"按 PREREG §5.1 判定为
    WilsonUpper95(FPR_R1) < WilsonLower95(FPR_R2) 且 < WilsonLower95(FPR_R7@8)，
    并另报同一批零池上的**配对精确 McNemar**（配对单位 `(source_pool, null_index)`，
    每个源池恰 K=200 个配对单位，不得跨源池配对；须同向且双侧 p<0.05 才算"与区间一致"）
  - `k_curve`：**按 PREREG §1 的候选块**为每个 `(source_pool, null_index)` 单元生成 8 个候选池 `C(source_pool, i, j)`（`j=1..8`，与该单元自身的 R2 零池不同），`R7` 取点估计最优；报 `FPR@k`，k=1..8，但 **R7 的操作性读数固定 `k=8`**（`FPR_R7@8` / `TPR_R7@8`）；k=1..7 仅作描述性曲线，**该曲线 Task 4 必须报告且不受 k=8 约束**。`TPR_R7@8` 的候选用 POSITIVE 族保标签 bootstrap（`C_pos(source_pool, i=0, j)`），不得用重排候选；曲线端点 k=1＝候选块 (i,1)，≠ 池本身，也不得替代 k=8。
    候选流只属于 indices 0–3 的**已声明 null 源**（它们才有零单元）；indices 4–9 非 null 源，不得为其生成候选
  - 依预注册三分支给 `verdict_branch`；(ii) 的判定式为
    `FPR@8(R1) < WilsonLower95(FPR@8(R2))` 且 `< WilsonLower95(FPR@8(R7))`（k=8 固定，不得改用其它 k）

- [ ] **Step 2: 运行并落盘** → **Step 3 打印人类可读摘要（FPR/TPR 表 + k 曲线 + R4 逐池表 + 分支）** ——
  FPR/TPR 表与 R4 表分开（前者是盲零集指标，后者是选择集逐池决定，分母不同不得混表），
  且每行标出 `(chal_policy, inc_policy)` —— **Step 4 提交**

---

### Task 5: 独立审计（可重算性验证）

**Files:**
- Create: `scripts/audit_gate_rules.py`

**Interfaces:**
- Consumes: `pools.json`（**必须经 `scripts/build_pools.py::load_pools_json()` 读取**，artefact 形状
  是 `{"meta":…,"pools":[…]}`；裸 `json.loads` 是错误形状且绕过校验）、`ablation.json`、`gate_rules.py`
- Produces: exit 0 iff 每条规则的决定都能从原始 JSON 重算且与落盘一致

- [ ] **Step 1: 实现**：绕开 `ablation_gate.py`，用 `build_pools()` + `decide()` 重算全部决定，逐条比对
- [ ] **Step 1b（Ruling 20，binding）**：**候选池必须由已发布的函数现场重算**，不得从任何内嵌副本、
  序列化快照或 `ablation.json` 内嵌的候选列表读取：用 `scripts/build_pools.py` 的
  `iter_null_candidate_blocks(source_pool, i, j)`（NULL 族，`j=1..8`）与
  `positive_candidate_blocks(source_pool, i=0, j)`（POSITIVE 族）重新生成该单元自己的候选池，
  再逐单元取点估计最优；并断言重算结果与 `ablation.json` 记录的决定一致。只校验汇总布尔值、
  不重算候选流的审计是空转的，不算通过
- [ ] **Step 1c（correction round；PREREG §5A）**：**R4 必须参与重算**。审计对 roster indices 4–9
  的六个非盲选择集池独立重算 `decide("R4", p)`（含 `(chal_policy, inc_policy)` 方向与
  promoted/total 分母），与 `ablation.json` 的 R4 区块逐池比对，并与 `pools.json` 的
  `meta.r4_status` / `meta.r4_evaluable` 对账；同时校验**没有**出现 R4 的 FPR（无非盲零集）。
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
- **R2 的 FPR 期望 = (1 − P(tie))/2 是构造使然**（不是 0.5；d=6 时 = 0.34375，见 `PREREG-round5.md` §4.1）：这是"无错误控制"的应有之义，转述时必须说明，不得包装成"我们发现基线很差"，也不得把 d 较小时与 0.5 的偏离当成发现。
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
