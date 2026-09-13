# PREREG Round-4 — true-claim tests (2026-09-11)

Status: preregistered, no measurements yet

## Frozen design decisions

- Backend: qwen2.5:7b (digest from BACKEND.json at run time), temperature 0.
- Policies Track A: `direct`, `step-calc` (incumbent), `cot-zero` (exact prompt in Task 2), `few-shot` (exemplars gsm8k-01..04 file order, built by script in Task 2, frozen before any test run).
- Track A spend: heldout40 (40) + heldout-batch2-160 (160), all 4 policies, paired per question. Budget ≈ 800 calls × ~6 s ≈ 1.5 h.
- Track A headline pairs: step-calc vs cot-zero; step-calc vs few-shot; gate per pair on merged-200: McNemar two-sided p < 0.05 AND gain ≥ 0.02 AND challenger/incumbent mean-latency ≤ 2.0.
- Track A outcomes (exhaustive, obligatory): (i) step-calc passes both headline gates → record "first true claim" (README addition, Task 6); (ii) step-calc LOSES either headline gate with p < 0.05 against it → OBLIGATORY story rewrite (README Round-2 section downgraded: strawman disclosure + revised claim, Task 6); (iii) neither → inconclusive, recorded, no story change.
- Track B inputs (fetch-at-runtime, never committed): SVAMP `https://raw.githubusercontent.com/arkilpatel/SVAMP/main/SVAMP.json` (1000 rows, MIT upstream); MultiArith-test `https://huggingface.co/datasets/ChilleD/MultiArith/resolve/main/test.json` (180 rows); ASDiv `https://datasets-server.huggingface.co/rows?dataset=EleutherAI/asdiv&config=asdiv&split=validation` (2305 rows expected, CC-BY-NC-4.0 → runtime-only). sha256 of fetched bytes recorded in fetch log + results metadata.
- Track B policies: `direct` + frozen `step-calc` only, 1 call each, resume-capable. Budget ≈ 6970 calls × ~4 s ≈ 8 h background.
- Track B success rule (generalization claim): step-calc beats direct with p < 0.05 on SVAMP-full AND gain > 0 on all three sets. Else → honest negative #2 (TRANSFER record, no promotion machinery — transfer is observational).
- Track C models: gemma3:4b (local, Google family, 4B) primary; llama3.1:8b via `ollama pull` (6 GB VRAM fits ~4.9 GB Q4), fallback qwen2:7b (local) with fallback recorded. Per-model digests recorded in MODELS-round4.json.
- Track C scope per model: {direct, step-calc, concise-reason, cot-zero, few-shot} × heldout40 (200 calls ≈ 25 min), same-window per model. Headline: step-calc vs concise-reason (Round-2 claim replication) + step-calc vs cot-zero (Round-4 extension). Expansion to batch2-160 iff headline pair has p < 0.2 AND |gain| ≥ 0.02 (weak-signal spend rule).
- Nondeterminism note: temperature 0, one run per (policy, question); Ollama offers no seed control — documented limitation, same as Rounds 1–3.

## Amendment 1 (2026-09-13, appended BEFORE the Track B cot-zero run — no frozen text edited)

- Reason: the original Track B (line 13–14) compares `step-calc` against `direct`
  ONLY. Track A already proved `direct` is a strawman (number-only). A
  `step-calc` ≫ `direct` result across datasets is therefore **uninformative**
  (it re-derives "CoT-style ≫ number-only generalizes", already known and known
  to be expected). This was flagged in SELF_ASSESSMENT.md ("Track B 只与 direct
  对照…结果无信息量…运行前必须显式修订预注册并加入 cot-zero 对照").
- Amendment: the **primary Track B contrast is now `step-calc` vs `cot-zero`**
  (frozen `step-calc` and frozen `cot-zero`, 1 paired call each, over the same
  three fetch-at-runtime sets SVAMP / MultiArith / ASDiv). `direct` is demoted
  to a sanity check only (already run; see TRANSFER_RECORD.md).
- Decision rule (decidable, exhaustive): on EACH of the three sets, report the
  paired exact McNemar `step-calc` vs `cot-zero` (+ gain, + latency ratio).
  (i) if `step-calc` beats OR loses to `cot-zero` with p < 0.05 on any set →
  that is a new, informative finding (the self-evolved step-calc is NOT merely
  CoT beyond GSM8K); (ii) if none of the three is significant → consistent with
  the Track A null (step-calc ≈ cot-zero generalizes across datasets);
  (iii) any mixed pattern is reported as-is. No promotion machinery; observational.
