# 选项 B 诊断：权重杠杆的"提升"是格式收敛，不是算术能力

**结论（一句话）**：PREREG 锁死的 `last_int` 解析口径判 base+DPO 相对 base+SFT **GAIN +0.1333**；
但同一批生成换显式 `Answer:` 口径判 **REGRESSION −0.1667**，且 `strict_last_line` 口径判 NO_GAIN。
**判决符号随解析器翻转 → 不得宣称 DPO 提升了算术能力。** 机制是输出变短、`Answer:` 后不再续写，
使 `last_int` 从"抓到续写数字"变成"抓到真答案"；DPO 组真算术错误 16 题，反而比 SFT 的 3 题多。

## 1. 复现命令（全部本地，零 GPU）

```bash
cd gsm8k-self-evolve
/usr/bin/python3 scripts/report_ability.py \
  --heldout results/qlora-ability-b/synth_heldout.jsonl \
  --gen-sft results/qlora-ability-b/generations/generations_sft.json \
  --gen-dpo results/qlora-ability-b/generations/generations_dpo.json \
  --out-json results/qlora-ability-b/ability_report.json

/usr/bin/python3 scripts/parser_sensitivity.py \
  --heldout results/qlora-ability-b/synth_heldout.jsonl \
  --gen-sft results/qlora-ability-b/generations/generations_sft.json \
  --gen-dpo results/qlora-ability-b/generations/generations_dpo.json \
  --out-json results/qlora-ability-b/parser_sensitivity.json \
  --out-md  results/qlora-ability-b/parser_sensitivity.md
```

## 2. 五口径对表（n=60，min_delta=0.05 跑前锁定）

| 解析口径 | base+SFT | base+DPO | delta | verdict |
|---|---|---|---|---|
| `last_int`（PREREG 锁死） | 26/60 | 34/60 | **+0.1333** | **GAIN** |
| `first_answer` | 45/60 | 35/60 | **−0.1667** | **REGRESSION** |
| `last_answer` | 45/60 | 35/60 | **−0.1667** | **REGRESSION** |
| `upto_answer` | 46/60 | 40/60 | −0.1000 | REGRESSION |
| `strict_last_line` | 0/60 | 2/60 | +0.0333 | NO_GAIN |

符号一致性 = **UNSTABLE**。四口径 REGRESSION / 一口径 GAIN / 一口径 NO_GAIN。

格式遵从（末行整行 `Answer: <int>`，不看对错）：base+SFT **0/60**、base+DPO **5/60**。

## 3. 伪影来自哪里（输出形状读数）

| 组 | 平均长度 | 最短/最长 | `Answer:` 后续写 "Step" | 完全没有显式 Answer |
|---|---|---|---|---|
| base+SFT | 225.3 | 178 / 268 | **9/60** | 12/60 |
| base+DPO | 120.2 | 48 / 292 | **0/60** | 9/60 |

SFT 组（上游 `tmlr-qwen3-4b-p1v2` 学术写作 SFT）倾向在给出答案后继续复述解题步骤，
`last_int` 取"最后一个整数"于是抓到续写里的数字 → 明明算对却判错。
DPO 组输出短一半、`Answer:` 后不再续写 → `last_int` 恰好命中。
**同一批输出，只是文本形状变了。**

## 4. 真算术错误计数（按显式 `Answer:` 逐题重算）

| 组 | 显式 Answer 正确 | 显式 Answer 错误（真算错） | 无显式 Answer |
|---|---|---|---|
| base+SFT | 45 | **3** | 12 |
| base+DPO | 35 | **16** | 9 |

DPO 真算错 16 题（例：s100003 exp=4 got=57；s100004 exp=6 got=44；s100005 exp=4 got=11333；
s100007 exp=4 got=5；s100011 exp=4 got=1；s100015 exp=6 got=0），SFT 仅 3 题。
按"显式答案对不对"这个更贴近算术能力的读数，**DPO 比 SFT 差 10 题**。

另：DPO 有 1 题（s100012，exp=2）输出被 Unicode 下标数字污染（`₁₅*₇₉=₁₁₈₅ ... ₂ is the result`），
常规 `\d+`/`Answer:` 正则都抓不到——这也是解析口径问题的另一面。

## 5. ground truth 与训练数据核查（排除标注/数据错误解释）

- heldout 60 行按 prompt 里的 A/B/C/M 独立重算 `(A*B+C) mod M`，与 `answer` **全部一致（mismatches=0）**
  → 分数差异不是标注错误。
- `synth_train.jsonl` 400 行：`chosen` 形如 `"59 * 63 = 3717. 3717 + 3 = 3720. 3720 mod 9 = 3. Answer: 3"`，
  `rejected` 末位错（`= 5. Answer: 5`）。**`prefix-share≥85%` 相同 0/400**、
  **仅末位数字不同 0/400**、`rejected` 里 A*B 乘积错 0 行
  → 偏好对在中间步骤就已分叉，DPO 学到的不只是"末位格式"，但效果仍主要表现为输出变短。

## 6. 诚实边界（不得外推的部分）

- 合成分 `(A*B+C) mod M` **≠ GSM8K ≠ TMLR 指标**；本报告不产生任何 GSM8K/TMLR 数字。
- n=60 是**存在性读数**（能不能拿分），不是效应量；未做多 seed、未做置信区间。
- 结论只在本任务 + 本 verifier（`verifier-frozen-v1`）+ 本步数（DPO 50 步 / 1 epoch）下成立。
- 非量化：全程 `--no-4bit` bf16 LoRA，与论文 bnb_4bit-NF4 口径不同。
- **不事后改 PREREG 的 `_last_int`**：GAIN 是预注册口径的诚实结果，符号翻转是它的适用范围边界，
  两者都留在盘上（`ability_report.json` + `parser_sensitivity.json`）。
- 权重更新本身未做能力评测的旧结论不撤销：写作偏好 DPO adapter（sha `b9ef9253…`）从未被评过、
  也不宣称被评过；本报告评的是合成任务重训的 adapter（sha `b5e8ff39…`）。
