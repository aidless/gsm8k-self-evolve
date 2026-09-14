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
