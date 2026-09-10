# A线功效预注册 PREREG-efficacy-batch2

- 日期: 2026-09-10
- 分支: gsm8k-self-evolve / round3-borrowed-iteration
- 冻结基线: results/rounds/round3/heldout40-round3.json（n=40, backend qwen2.5:7b, incumbent step-calc 36/40=0.90, mean_latency 5.257s）
- 负结果封存: results/rounds/round3/NEGATIVE.md（reflect-retry 36/40 p=1.0 gain=0.0 latency_ratio=2.322 gate=false；textgrad-prompt 37/40 p=1.0 gain=0.025 latency_ratio=1.043 gate=false）
- 关联 claim: c2cbd110-ed56-492c-896e-fcde4744c09b (pending)

## H1（唯一主假设）

任一 challenger 在 heldout-40 主测试上同时满足以下三门才触发 batch2-160：
1. exact McNemar p < 0.05（配对单位=同题同后端，ties 计入分母）
2. gain = (challenger_score - 36/40) >= 0.02
3. latency_ratio = challenger_mean_latency / 5.257 <= 2.0

任一门失败 = gate_pass=false = 不跑 batch2-160，不晋升，维持 step-calc。

## 杀死条件（kill）

- batch1 任一 challenger gate_pass=false（当前 Round3 实际状态：两个均为 false）
- batch2 若被触发但 merged p >= 0.05 或 ledger identity 不成立 → 不晋升

## 功效说明（power）

- n=40 时 ±1 题 = ±0.025，噪声约 ±10%，只适合做门禁，不做功效宣称。
- batch2-160 为条件触发的确认样本；触发后主检验为 merged exact McNemar，Holm 校正（如多 challenger）。
- 延迟比独立否决：>2.0 直接 fail，不进入 p 值讨论（reflect-retry 已因此 fail）。

## 防 p-hacking

- 主测试单次：每个 challenger 只跑一次 heldout-40，不挑题、不重跑刷 p。
- 不混用不同组/配置统计量；mean(d) 必须等于组间均值差（assert）。
- batch2-160 在 gate_pass=true 前永不触达（当前永不触达）。

## 执行顺序

1. P-A1 清理提交（只拆分 commit，不动冻结证据）
2. batch1 主测试（已完成：Round3 结果即 batch1，不得重写）
3. 当且仅当 gate_pass=true → batch2-160（当前不触发）

## 服务器

- 已注册 srv-1a0813ef419（seetacloud-h3），本次预注册不投递新任务，仅落文档。
