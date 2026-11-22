# 解析口径敏感性（同一批 generations，换解析器重判）

样本 n=60；min_delta=0.05（PREREG 跑前锁定，本表不事后调）。
**符号一致性 = UNSTABLE**（判决随解析器翻转：GAIN↔REGRESSION，不能当能力结论）

| 解析口径 | base+SFT | base+DPO | delta | verdict |
|---|---|---|---|---|
| last_int | 26/60 | 34/60 | +0.1333 | GAIN |
| first_answer | 45/60 | 35/60 | -0.1667 | REGRESSION |
| last_answer | 45/60 | 35/60 | -0.1667 | REGRESSION |
| upto_answer | 46/60 | 40/60 | -0.1000 | REGRESSION |
| strict_last_line | 0/60 | 2/60 | +0.0333 | NO_GAIN |

格式遵从（最后一行整行 `Answer: <int>`）：base+SFT 0/60、base+DPO 5/60。

诚实边界：合成分=(A*B+C) mod M ≠GSM8K≠TMLR；本表只说明判决对解析器敏感，不外推为模型能力结论。
