| stage | sources (raw files) | passed | n | score | 95% Wilson CI |
|---|---|---|---|---|---|
| seed: direct | `results/heldout-result.json#direct-baseline` | 5 | 40 | 0.125 | [0.055, 0.261] |
| round 1: concise-reason | `results/heldout-round2-result.json#concise_reason`, `results/heldout-batch2-result.json#concise_reason` | 156 | 200 | 0.780 | [0.718, 0.832] |
| round 2: step-calc (stable) | `results/heldout-round2-result.json#step_calc`, `results/heldout-batch2-result.json#step_calc` | 185 | 200 | 0.925 | [0.880, 0.954] |
