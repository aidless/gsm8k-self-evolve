# QUARANTINE — proposer-arm-qwen38-27b.json（T6 首跑，已作废→已被 run2 取代）

> **状态更新（2026-09-16）**：本件隔离的理由与重跑要求已全部满足——run2
> （`proposer-arm-qwen38-27b-run2.json`）通过 AMENDMENT-2 rev.1 R1.4 验收门 a–d
> （valid=400/failed=0/全格 latency>0/重复一致性 398/400），C31 已以干净数据恢复 confirmed。
> **本件仍有效**：首跑 JSON 的一切数字继续禁止引用；本文件作为事故取证记录保留。
> 复用区核验：首跑 140 个有效格在 run2 中 0 不一致。

**原始状态：已隔离（INVALIDATED）。本 JSON 的一切 totals/pairs/headline 不得引用。**
日期：2026-09-16。隔离人：A 线会话（数据取证见下）。原 JSON 作为证据**原样保留、不修改**。

## 取证结论

1. **仅前 140 次调用有效**（held-01..held-14 × 5 策略 × 2 重复；`full.log` call 1–140，
   延迟合计 139.3 分钟，latency>0、parsed 有值）。
2. **call 141 起全部传输层失败**：云端 vLLM（Qwen3.8-27B-AWQ，端口 8000）于 09-14 15:17:56
   被外部 SIGTERM 优雅终止（`vllm-27b2.log` 完整 shutdown 序列，非崩溃；同 GPU 现已运行其它
   工作负载 pid 630287/652304）。held-15..40 共 26 题 × 5 策略 × 2 重复 = 260 格，
   签名一致：latency=0.0、parsed=None、passed=false（评估器 TransportError 路径的固定产物）。
3. **runner 缺陷放大了事故**：`run_one` 把评估器返回的传输错误记为 `passed=false` 的**有效数据格**，
   既消耗预算（calls_used=400/400）又混入 totals/headline；resume 逻辑视其为已完成、不会重试。
4. 因此产物中 `totals`（direct 1 / step-calc 13 / cot-zero 14 / few-shot 12 / textgrad 13）、
   `headline`（b=0, c=1, p=1.0, gain=−0.025, "n=40"）与 `repeats.agreement_vs_rep1`
   全部**把 260 个传输失败当成了模型答错**——方向上系统性压低所有策略、且 26 题全败使两次
   重复"高度一致"（失败是确定性的），一致性指标同样失真。

## 有效子集（仅供重跑后对照，不单独成结论）

held-01..14（n=14，两重复）：cot-zero 14/14，step-calc 13/14，textgrad 13/14，
few-shot 12/14（rep1）14/14（rep2），direct 1/14。样本过小，**禁止**据此下任何结论。

## 重跑要求（完成后方可解除隔离）

1. runner 修复：传输失败格标记 `call_failed`、不计入有效数据、不占用"有效格预算"、resume 自动重试；
   修复须带测试（注入 5xx/连接拒绝 → 断言不进 totals、可重试）。
2. 预算修订：AMENDMENT-2 rev.1 —— 400 有效格 + 至多 260 补偿重试（首跑已烧 400 次尝试，
   其中 260 次无数据产出）。
3. 服务守护：重跑期间监控 vLLM 存活；死亡即暂停（而非继续空转烧格）。
4. 重跑产物写**新文件**（如 `proposer-arm-qwen38-27b-run2.json`），本隔离件与其并存对照。
