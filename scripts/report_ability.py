"""本地判分 driver：把云端生成的两组 generation 按 heldout 对齐、评分、判决。

不碰模型权重、不做生成——生成已在云端 cloud_eval.py 完成。本脚本只读 json，
按 heldout 的 id 顺序对齐 text（缺 id fail-closed），调用 eval_ability 评分并 verdict。
min_delta 从 PREREG 跑前锁定（默认 0.05），不事后调。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_ability as ea  # noqa: E402


def _load_generations(path):
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("generations 必须是 list")
    by_id = {}
    for r in rows:
        if "id" not in r or "text" not in r:
            raise ValueError("generation 缺 id/text")
        by_id[r["id"]] = r["text"]
    return by_id


def _align(heldout, gen_by_id, arm):
    texts = []
    for row in heldout:
        if row["id"] not in gen_by_id:
            raise ValueError(f"{arm} 缺 heldout id: {row['id']}")
        texts.append(gen_by_id[row["id"]])
    return texts


def build_report(heldout_path, gen_sft_path, gen_dpo_path, min_delta=0.05):
    heldout = ea.load_heldout(heldout_path)
    sft = _align(heldout, _load_generations(gen_sft_path), "sft")
    dpo = _align(heldout, _load_generations(gen_dpo_path), "dpo")
    base = ea.score_generations(heldout, sft)
    adapter = ea.score_generations(heldout, dpo)
    base_summary = {k: base[k] for k in ("passed", "total", "accuracy")}
    adapter_summary = {k: adapter[k] for k in ("passed", "total", "accuracy")}
    v = ea.verdict(base_summary, adapter_summary, min_delta=min_delta)
    return {"base": base_summary, "adapter": adapter_summary, "verdict": v,
            "details": {"base": base["details"], "adapter": adapter["details"]},
            "min_delta": min_delta, "n_heldout": len(heldout)}


def render_md(rep):
    v = rep["verdict"]
    return (
        "# 合成能力任务评测（选项 B）\n\n"
        "诚实边界：本任务=(A*B+C) mod M 合成算术，≠GSM8K≠TMLR；"
        "结论只在本任务+本 verifier+本步数解释。\n\n"
        "| 组 | 通过/总数 | 准确率 |\n"
        "|---|---|---|\n"
        f"| base+SFT | {rep['base']['passed']}/{rep['base']['total']} | {rep['base']['accuracy']} |\n"
        f"| base+DPO | {rep['adapter']['passed']}/{rep['adapter']['total']} | {rep['adapter']['accuracy']} |\n\n"
        f"判据：min_delta={rep['min_delta']}（跑前锁定）；delta={v['delta']}；"
        f"verdict=**{v['label']}**\n"
    )


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="本地判分：合成能力任务 base+SFT vs base+DPO")
    ap.add_argument("--heldout", required=True)
    ap.add_argument("--gen-sft", required=True)
    ap.add_argument("--gen-dpo", required=True)
    ap.add_argument("--out-json", default=None)
    ap.add_argument("--min-delta", type=float, default=0.05)
    a = ap.parse_args()
    rep = build_report(a.heldout, a.gen_sft, a.gen_dpo, min_delta=a.min_delta)
    print(render_md(rep))
    if a.out_json:
        Path(a.out_json).write_text(json.dumps(rep, ensure_ascii=False, indent=1),
                                    encoding="utf-8")
        print(f"[done] -> {a.out_json}")
