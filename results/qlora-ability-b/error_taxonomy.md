# 误差分型诊断：explicit 口径的"错"里有多少是算术错

## 诚实边界

- generations 只有 `{id, answer, text}`，**没有 finish_reason**。无法客观判定是否触到 `max_new_tokens=96` 上限。
- 因此 NOANS_* 四类的"截断/退化"判断全部是**启发式**（文本形态），每条带 `heuristic=True`，不能当成客观归因。
- 本尺子是诊断层，不改 parser_sensitivity / ability_report 的任何口径与数字。

## 两层口径

- L1 = 清单里 60 题（只能说"清单 60 题"）。
- L2 = 真正产出了规范 Answer 字段、能判对错的题数（这才该引用为实测规模）。
- L3 = 无 Answer 字段、根本没测到算术能力的题数（截断/退化/算出没写格式）。

### SFT (base)

- L1 清单规模：60
- L2 可评分规模（有规范 Answer 字段）：48
- L3 启发式排除（输出失败，未测到算术能力）：12

| 分型 | 题数 |
|---|---|
| ANSWER_CORRECT | 45 |
| ANSWER_WRONG_TRUEARITH | 3 |
| NOANS_TRUNCATED_MIDSTEP | 11 |
| NOANS_DEGENERATE | 0 |
| NOANS_COMPUTED_BUT_UNFORMATTED | 1 |
| NOANS_OTHER | 0 |

旧假设（NOANS 全算算术错）的真算术错 = 15；分型后 ANSWER_WRONG_TRUEARITH = 3。

### DPO (adapter)

- L1 清单规模：60
- L2 可评分规模（有规范 Answer 字段）：51
- L3 启发式排除（输出失败，未测到算术能力）：9

| 分型 | 题数 |
|---|---|
| ANSWER_CORRECT | 35 |
| ANSWER_WRONG_TRUEARITH | 16 |
| NOANS_TRUNCATED_MIDSTEP | 1 |
| NOANS_DEGENERATE | 3 |
| NOANS_COMPUTED_BUT_UNFORMATTED | 5 |
| NOANS_OTHER | 0 |

旧假设（NOANS 全算算术错）的真算术错 = 25；分型后 ANSWER_WRONG_TRUEARITH = 16。

## 结论

- 两种口径各有污染源：last_int 被 Answer 后续写数字污染；explicit 被 token 截断/解码退化污染。
- "explicit = 真算术能力"不成立：L3 题根本没测到算术能力却被记成"错"。
- "DPO 真算术错 16" 的分母不干净；真问题是 max_new_tokens=96 太短 + 贪心退化，输出质量成了混淆变量。

