# token 上限假设的可证伪实测（96 → 256）

**判决 = MIXED**
唯一干预：max_new_tokens 96 -> 256 (only change, PREREG-256.md frozen)；预注册锁死 2026-11-22T15:35:00Z，本表不事后调阈值。

## 诚实边界

- generations 无 finish_reason，截断/退化为文本形态启发式，非客观归因
- 存在性 probe，不是能力结论；不宣称 DPO/SFT 谁算术更强
- PREREG-256.md:37 括号内'退化不塌缩'与形式条件相反是笔误；按形式定义判，未改判据
- 256 产物缺失记 INCOMPLETE，不外推；不改现有 96 口径与数字

## 判据与读数

- H_token（SFT 截断塌缩 + L3 塌缩）=成立：NOANS_TRUNCATED_MIDSTEP 11→1（≤3），L3 12→1（≤4）。
- H_greedy（DPO 退化不塌缩）=成立：NOANS_DEGENERATE 3→3（≥2）。
- 三态（PREREG:37-39 形式定义）：**MIXED**。

## 符号稳健性（独立记录，不并入三态）

- 96 口径符号一致性：UNSTABLE；256：UNSTABLE。
- 符号若仍 UNSTABLE，无论三态为何都不宣称能力增益（last_int 的 GAIN 是格式伪影）。

