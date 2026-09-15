# AMENDMENT 2 — Task 6 backbone substitution (new-generation model)

**Status:** frozen before the amended deliverable run.
**Applies to:** Task 6 (the optional proposer-substitution arm) in `PREREG-round5.md` §6.
**Does not affect:** Tasks 0–5 and Task 7, which use zero model calls and re-analyse already-committed
run data. Their results are unchanged by this amendment.

## 1. What changed and why

The original §6 fixed the backbone at `qwen2.5:7b` for comparability with Track A. A workspace-level
model-selection policy issued on 2026-09-14 ("all new experiments use a new-generation backbone";
`AGENTS.md` item 21) prohibits opening a **new** experiment on a previous-generation model. Task 6 is
a new experiment (it introduces new model calls), so the original backbone choice is no longer
admissible. This amendment records the substitution; it is a dated design change, not a silent edit.

## 2. Amended design

| item | original §6 | amended |
| --- | --- | --- |
| backbone | `qwen2.5:7b` (ollama) | **`Qwen3.8-27B-AWQ`** (AWQ-INT4, `compressed-tensors`), served via **vLLM 0.27.1** OpenAI-compatible API as model id `qwen3.8-27b` |
| generation | ollama `/api/chat`, temperature 0 | OpenAI `/v1/chat/completions`, `temperature: 0`, `max_tokens` pinned per call |
| panel | `(direct, step-calc, cot-zero, few-shot, textgrad)` | **unchanged** |
| dataset | `examples/heldout40.json` (40 questions) | **unchanged** |
| budget | ≤400 calls (40 × 5 policies × 2 repeats) | **unchanged** |
| headline | `textgrad` (chal) vs `cot-zero` (inc) | **unchanged** |
| scoring / output shape | per `run_proposer_arm.py` | **unchanged** |
| transport | ollama HTTP | OpenAI-compatible HTTP (new flag `--openai-base` / `EVO_OPENAI_BASE`); ollama remains the default for the original path |

Everything that defines the *experiment* — panel, dataset, budget, headline, scoring, incremental
saving and output shape — is untouched. Only the model and the HTTP transport change.

## 3. Consequences for comparability (stated, not hidden)

1. **The amended Task 6 is NOT numerically comparable to Track A / Track C.** Those used
   qwen2.5:7b / gemma3:4b / qwen2:7b / llama3.1:8b. The amended arm answers a different question:
   *does the proposer-substitution conclusion hold on a new-generation backbone?*
2. **It is also not comparable to the aborted `qwen2.5:7b` run** (which was stopped at 263/400 calls
   under this policy). That partial artefact is retained but is **not citable** and must be marked as
   an off-policy partial run; it is not reported as a result.
3. **The 27B is a different scale class (27B vs 7B).** A difference between them therefore confounds
   *generation* with *scale*. The amended arm is reported as a single-backbone replication attempt on
   a newer, larger model — not as a scale study and not as a trend.

## 4. Pre-conditions verified before launch (evidence)

- the 27B AWQ model directory on the compute host: 20 GB, **5/5 shards present**, `model_type = qwen3_5`,
  `architectures = [Qwen3_5ForConditionalGeneration]`, `quantization_config.quant_method = compressed-tensors`.
- **The vLLM-loadable config is the ORIGINAL one** (`config.json.bak_orig`, 193 `model.language_model.*`
  ignore prefixes). The hand-fixed config (`config.json`, 0 old prefixes) that made the
  transformers/`compressed_tensors` path load **breaks vLLM's weight loader**
  (`AttributeError: 'MergedColumnParallelLinear' object has no attribute 'data'`). The two loaders
  therefore require *different* configs and both files are retained; this amendment uses the original
  config for vLLM. (Recorded as lesson `L-27b-config-1`.)
- vLLM 0.27.1 + transformers 5.16.1 (the isolated python env on the compute host, not the system
  interpreter), `VLLM_USE_FLASHINFER_SAMPLER=0`
  (flashinfer is not installed), `--enforce-eager` (skips a long 27B torch.compile that stalled).
- Server readiness: `GET /v1/models` returns id `qwen3.8-27b`.
- **A real generation was completed and timed**: 427 completion tokens in 50.8 s (**8.4 tok/s**,
  `finish_reason: stop`). This is the basis for the expected wall-clock (see §5).

## 5. Budget and expected wall-clock (disclosed)

The preregistered budget is unchanged at ≤400 calls. At the measured 8.4 tok/s and an observed ~400-token
answer length, one call is ≈50 s, so the full arm is ≈**5–6 hours** of wall-clock. This is a resource
fact, not a design change. Because the runner saves incrementally and is resumable, an interruption
loses at most one call.

## 6. Honest boundary

- The result is a **single-backbone** observation. It cannot establish that the proposer-substitution
  conclusion holds across new-generation models.
- A self-hosted quantized (AWQ-INT4) 27B is not the same object as the vendor's full-precision model;
  quantisation is a disclosed part of the instrument.
- If the amended arm cannot be completed within the budget, it must be recorded as **"not executed"**
  per §6, and never substituted with other data.

## 7. Deviation log

| # | date | change | reason |
| --- | --- | --- | --- |
| 1 | 2026-09-14 | Task 6 backbone `qwen2.5:7b` → `Qwen3.8-27B-AWQ` (vLLM, OpenAI API); transport made pluggable | workspace model-selection policy (AGENTS.md 21): new experiments use a new-generation backbone |
| 2 | 2026-09-14 | the aborted `qwen2.5:7b` partial run (263/400) retained but marked **not citable** | it is off-policy; retained only as an audit trail |

---

# Revision 1（2026-09-16）：首跑作废、预算口径修订、重跑条款

## R1.1 首跑事故（记录，不改写）

首跑（2026-09-14 启动）在 call 140/400 后被外部终止的 vLLM 服务拖垮：held-15..40 的
260 格全部为传输层失败（latency=0、parsed=None），被 runner 误记为有效数据。
产物 `proposer-arm-qwen38-27b.json` 已整批隔离（见同目录 QUARANTINE.md），**原样保留、
其一切聚合数字禁止引用**。事故取证：`vllm-27b2.log`（09-14 15:17:56 SIGTERM 优雅关停序列）、
`full.log`（call 141 起全败）、隔离件中的按策略×按题失败矩阵（26 题 × 5 策略 × 2 重复全中）。

## R1.2 预算口径修订

原 §5「≤400 calls」修订为双口径：
- **有效格（valid cells）≤ 400**：40 题 × 5 策略 × 2 重复，每格必须真实到达模型
  （latency > 0 或显式判定为模型答案）；
- **总尝试（attempts）≤ 800**：传输失败尝试单独计数、不占有效格预算、可重试；
- **熔断**：连续 ≥5 次传输失败 → 立即停机保存状态（exit 4），禁止空转烧格。

首跑已消耗尝试 400（其中有效 140、失败 260）；重跑额度 = 至多 260 有效格 + 相应尝试余量。

## R1.3 首跑 140 个有效格的复用合法性

重跑**复用** held-01..14 的 140 个有效格（不重测），依据：
1. 模型与权重不变（同一 `qwen38-27b-awq` 目录、原始 config——首跑与重跑均为原始 config，
   09-16 期间被外部改回手改版的 config 已在重启前恢复，见模型目录 `README_CONFIG_VERSIONS.txt`）；
2. 推理语义不变：temperature 0、max_tokens 1536、max-model-len 4096、同一 chat template；
   重跑服务的 `--gpu-memory-utilization 0.52` 与 `--limit-mm-per-prompt image=0` 只影响
   KV 缓存容量与多模态剖析，不改变单请求贪心解码的数值语义；
3. 跨运行噪声水平已由 §5.5/C23 量化（198/200 一致），复用引入的混批噪声不超过该水平，
   且重跑完成后将按重复一致性同法披露。

## R1.4 重跑执行条款

1. 前提：runner 修复落地（传输失败≠数据、resume 重试、熔断、attempts 记账）且测试全绿；
2. 重跑载体：`proposer-arm-qwen38-27b-run2.json`（由隔离件复制后经 --resume 补格），
   与隔离件并存对照；
3. 验收门（解除隔离、恢复 C31 判定的必要条件）：
   a. run2.json 中 valid_cells = 400 且 failed_cells = 0；
   b. 全部 400 有效格 latency > 0（延迟分布核查，教训条款）；
   c. headline/pairs/totals 全部仅由有效格计算，n 与计划一致（n=40）；
   d. 重复一致性按 rep1 vs rep2 全量报告；
4. 服务守护：重跑期间每 N 格检查服务存活由熔断条款承担；服务再次死亡 → 状态保留、
   恢复服务后 resume，**不得**让失败格进入数据。

## R1.5 偏离日志（追加）

| # | date | change | reason |
| --- | --- | --- | --- |
| 3 | 2026-09-16 | 首跑整批作废隔离；预算改双口径（有效格 400 + 尝试 800）+ 熔断；held-01..14 的 140 有效格复用；重跑写 run2.json | 外部终止服务导致 260 格传输失败被误记为数据（runner 缺陷同步修复） |
