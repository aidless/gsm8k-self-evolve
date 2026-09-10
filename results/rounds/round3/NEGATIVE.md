# Round 3 — Negative result (heldout-40 gate: STOP)

Task 7 gate outcome, verified by independent recompute: **STOP. Neither
challenger passes on heldout-40** (n=40, backend qwen2.5:7b, incumbent
step-calc 36/40). This file records the negative. A negative is a success
of the protocol: no promotion, no new runs, batch2-160 never contacted.

Gate rule (from results/rounds/round3/heldout40-round3.json metadata):
p < 0.05 AND gain >= 0.02 AND latency_ok (ratio <= 2.0)
-> run batch2-160 / promote only if merged p < 0.05 with ledger identity holding.

## Per-challenger paired counts (verbatim from brief)

| challenger      | score | better | worse | exact McNemar p | gain  | mean latency ratio | gate_pass |
|-----------------|-------|--------|-------|-----------------|-------|--------------------|-----------|
| reflect-retry   | 36/40 | 1      | 1     | 1.0             | 0.0   | 12.207/5.257=2.322 | false     |
| textgrad-prompt | 37/40 | 2      | 1     | 1.0             | 0.025 | 1.043              | false     |

## Failed gate conditions

- reflect-retry: gain=0.0 (< 0.02 min_gain) AND p=1.0 (not < 0.05) AND
  latency ratio 2.322 (> 2.0 cap -> fails latency independently).
- textgrad-prompt: gain=0.025 (>= 0.02 passes) BUT p=1.0 fails significance;
  latency ratio 1.043 (OK).
- gate_pass=false for both -> batch2-160 correctly never run
  (no second blind contact).

## Interpretation

- reflect-retry adds latency without significant gain on qwen2.5:7b.
- textgrad-prompt, frozen to baseline text, reproduces the null as expected.
- step-calc stays stable. No level change. No promotion.
