"""评测合成能力任务：base (Qwen3-4B) vs base+DPO-adapter 的配对准确率。

选项 B 的评测端。heldout 与 train 用不相交 seed（见 synth_ability），ground truth
由 Python 精确算出，模型答案用 score_response 抽最后一个整数精确比对——不靠模型
自评、不靠 LLM judge、不看合成分数。

纯逻辑（load_heldout / summarize / verdict）本地 TDD；推理（run_generation）只在云端
加载模型时调用。base 与 adapter 在同一进程内依次前向，避免重复加载 4B 权重。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from synth_ability import score_response


def load_heldout(path: str) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            assert "id" in d and "prompt" in d and "answer" in d, "heldout 缺字段"
            rows.append(d)
    return rows


def build_prompt(row: dict) -> str:
    return row["prompt"]


def score_generations(heldout: list[dict], generations: list[str]) -> dict:
    """把模型逐题输出与 ground truth 比对，返回每题对错 + 汇总。

    generations 与 heldout 必须一一对齐；长度不符 fail-closed 拒绝（避免错位计分）。
    """
    if len(generations) != len(heldout):
        raise ValueError(f"generation/heldout 长度不符: {len(generations)} vs {len(heldout)}")
    details = []
    for row, gen in zip(heldout, generations):
        ok = score_response(gen, row["answer"])
        details.append({"id": row["id"], "expected": row["answer"],
                        "parsed": _last_int(gen), "correct": ok})
    passed = sum(d["correct"] for d in details)
    return {"passed": passed, "total": len(details),
            "accuracy": round(passed / len(details), 4), "details": details}


def _last_int(text: str):
    import re
    nums = re.findall(r"-?\d+", (text or "").strip().replace(",", ""))
    try:
        return int(nums[-1]) if nums else None
    except ValueError:
        return None


def verdict(base: dict, adapter: dict, min_delta: float = 0.05) -> dict:
    """配对比较判决。delta = adapter - base。

    min_delta 是判"有提升"的门槛，跑前固定不事后调；低于门槛记 NO_GAIN。
    """
    delta = round(adapter["accuracy"] - base["accuracy"], 4)
    if delta >= min_delta:
        label = "GAIN"
    elif delta <= -min_delta:
        label = "REGRESSION"
    else:
        label = "NO_GAIN"
    return {"base_accuracy": base["accuracy"], "adapter_accuracy": adapter["accuracy"],
            "delta": delta, "min_delta": min_delta, "label": label}


def run_generation(model, tok, prompts: list[str], max_new_tokens: int = 96) -> list[str]:
    """云端推理：给定已加载的 model/tok，逐 prompt 贪心生成（temperature 0）。

    model 调用方负责加载（base 或 base+adapter），本函数不碰权重。
    """
    import torch
    outs = []
    for p in prompts:
        enc = tok(p, return_tensors="pt").to(model.device)
        with torch.no_grad():
            gen = model.generate(**enc, max_new_tokens=max_new_tokens,
                                 do_sample=False, pad_token_id=tok.eos_token_id)
        text = tok.decode(gen[0][enc["input_ids"].shape[1]:], skip_special_tokens=True)
        outs.append(text)
    return outs
