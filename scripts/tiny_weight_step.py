#!/usr/bin/env python3
"""亚分钟权重更新 smoke：真的改权重，不是假装改。

纯 Python（零依赖、零 GPU）：一个 2 参数线性模型对固定数据点做 3 步 SGD，
把**改完之后**的权重写成 adapter 文件，最后一行回 {"steps": 3}。

用途只有一个：让 `evokit.weight_updater.SubprocessWeightUpdater` 的回执通道
（命令 → 产物 → 自算 sha256）在真实文件上跑通。它不训练任何语言模型，
不产生任何实验结论（AGENTS.md 第 17 条：本机只允许亚分钟 smoke）。
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

LR = 0.1
STEPS = 3
X = [1.0, 2.0]
TARGET = 1.0
INIT_WEIGHTS = [0.1, -0.2]


def main() -> None:
    spec_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])
    spec = json.loads(spec_path.read_text(encoding="utf-8"))

    # 用 job digest 扰动初始点：同一候选重跑得到同一结果（可复现），
    # 不同候选起点不同（不会得到同一个 adapter 哈希）。
    jitter = int(hashlib.sha256(str(spec.get("digest", "seed")).encode()).hexdigest()[:8], 16)
    w = [INIT_WEIGHTS[0] + (jitter % 7) / 1000.0, INIT_WEIGHTS[1]]

    loss = None
    for _ in range(STEPS):
        pred = sum(wi * xi for wi, xi in zip(w, X))
        err = pred - TARGET
        loss = err * err
        grad = [2 * err * xi for xi in X]
        w = [wi - LR * gi for wi, gi in zip(w, grad)]

    record = {"weights": w, "steps": STEPS, "final_loss": loss,
              "job_digest": spec.get("digest"), "verifier_id": spec.get("verifier_id")}
    out_path.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
    # 自报产物哈希：调用方会与本地实算值对表，不一致即判失败（防"报告成功"）
    import hashlib as _h
    sha = _h.sha256(out_path.read_bytes()).hexdigest()
    print(json.dumps({"steps": STEPS, "final_loss": loss,
                      "adapter_sha256": sha, "init_weights": INIT_WEIGHTS}))


if __name__ == "__main__":
    main()
