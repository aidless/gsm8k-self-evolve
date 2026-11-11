# 权重通道端到端 smoke（2026-11-11）

**用途**：证明 P2 的 weight 杠杆不是"接口占位"，而是能真的执行一次权重更新、
把产物拉回来、自己算哈希、并让回执通过 `validate_weight_receipt()` 的契约。
**不是**实验结果，不训练任何语言模型，不产出任何可引用的效果数字。

## 环境

| 项 | 值 |
| --- | --- |
| 训练机 | `radeon-amd`（AMD Radeon Cloud 中国站，`root@36.150.116.206:33100`） |
| 主机名 | `j-uldaasom6p527yrvxtnm7x7rmk` |
| CPU / Python | 128 核 / Python 3.12.3 |
| GPU 工具 | ROCm SMI 存在（本次 smoke 未用 GPU） |
| 本机角色 | 只做编排与哈希校验（AGENTS.md 第 17 条） |

## 走了什么

```
SubprocessWeightUpdater.apply(candidate)
  → 写 job spec（含 candidate + verifier + round + digest）
  → scp job spec 到训练机
  → ssh 在训练机上跑 scripts/tiny_weight_step.py（纯 Python 2 参数 3 步 SGD）
  → scp adapter.jsonl 拉回本地
  → 本机 sha256(盘上字节)，并与训练机自报哈希对表
  → 返回 {adapter_sha256, verifier_id, steps, job_digest, adapter_path}
```

## 两次实测回执

1. 直接调用 updater：`adapter_sha256 = 9be1afc7a967ab3cc0a649e95f0c7492d724f3b56e2d628e9d1ef46e080e4051`，
   `steps = 3`，本地复算哈希一致，权重 `[0.364, 0.318]`（初始点 `[0.1, -0.2]`，确实被更新）。
2. 注入 `run_interleaved_loop(rounds=2)`：第 0 轮走 harness（`R1_scaffold_bottleneck`，accepted），
   第 1 轮走 weight（`R2_capability_bottleneck`，accepted），回执
   `adapter_sha256` 前 16 位 `78e85d44964ab4c2`；`stopped_reason=None`，`final_score=0.93`。

## 为什么这样算"真"

- **产物真**：adapter 文件是训练机上跑出来的，不是本地伪造；拉回后字节在盘上。
- **哈希真**：`sha256` 由本机对盘上字节现算，并交叉核对训练机自报值，不一致即抛错
  （`tests/test_weight_updater_smoke.py::test_reported_sha_mismatch_raises` 是反证）。
- **失败真**：命令失败 / 无产物 / stdout 无 JSON / 哈希不符，四种情形都有 RED 测试，
  全部抛错而不是返回伪回执。

## 边界（必须连着引用）

- 训练对象是 2 参数线性模型，**不是** Qwen3-4B，也不产生任何能力评测数字。
- 未使用 GPU；云端通道只用 CPU 与文件传输。
- 真正上 Qwen3-4B QLoRA 的续跑点：把 `cloud_lora_command(trainer=...)` 的 trainer
  换成 `paper_agent/train/train_dpo.py`（QLoRA 栈），`steps` 用作业卡里的密网格值，
  训练机选有 GPU 的实例；上游作业需要预注册（数据、步数、评测集、verifier 版本）
  并在云端 detached 运行，本机只读日志与回执。
