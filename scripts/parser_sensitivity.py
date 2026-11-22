"""解析器敏感性：同一批 generations 换解析口径，判决符号是否翻转。

为什么需要这台尺子（不是装饰）：
  PREREG 锁死的是 `_last_int`（取文本中最后一个整数）。但选项 B 的 prompt 要求
  "write the final integer alone on the last line prefixed with 'Answer:'"。
  真实生成里 SFT 组常在 Answer 之后继续写 Step 1...（把 last_int 抓成续写数字），
  DPO 组则更短更干净——两种口径会给出一升一降，符号相反。
  这台尺子的职责：把"判决依赖解析器"这件事变成可复算的读数，而不是一句判断。

只在本任务（(A*B+C) mod M 合成算术）内解释；不做跨任务外推。
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_ability as ea  # noqa: E402

_ANS = re.compile(r"Answer\s*[:：]?\s*(-?\d+)")


def last_int(text):
    """PREREG 锁死口径：取最后一个整数（逗号先去掉）。"""
    nums = re.findall(r"-?\d+", (text or "").strip().replace(",", ""))
    return int(nums[-1]) if nums else None


def first_answer(text):
    """第一个 'Answer:' 后的整数（尊重显式答案行）。"""
    m = _ANS.search(text or "")
    return int(m.group(1)) if m else None


def last_answer(text):
    """最后一个 'Answer:' 后的整数（复读时取末次声明）。"""
    ms = _ANS.findall(text or "")
    return int(ms[-1]) if ms else None


def upto_answer(text):
    """截到第一个 Answer 数字为止再取最后整数——Answer 之后的内容不计入。"""
    t = text or ""
    m = _ANS.search(t)
    if m:
        t = t[: m.end()]
    nums = re.findall(r"-?\d+", t.replace(",", ""))
    return int(nums[-1]) if nums else None


def strict_last_line(text):
    """严格按指令：最后一个非空行必须整行是 'Answer: <int>'。"""
    lines = [x for x in (text or "").splitlines() if x.strip()]
    if not lines:
        return None
    m = re.fullmatch(r"\s*Answer\s*[:：]?\s*(-?\d+)\s*", lines[-1])
    return int(m.group(1)) if m else None


def format_compliant(text):
    """格式遵从率读数：最后一行是否整行 'Answer: <int>'（不看答案对不对）。"""
    return strict_last_line(text) is not None


PARSERS = {
    "last_int": last_int,
    "first_answer": first_answer,
    "last_answer": last_answer,
    "upto_answer": upto_answer,
    "strict_last_line": strict_last_line,
}


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
    return [gen_by_id[r["id"]] if r["id"] in gen_by_id
            else (_ for _ in ()).throw(ValueError(f"{arm} 缺 heldout id: {r['id']}"))
            for r in heldout]


def score_arm(heldout, texts, parser):
    passed = sum(1 for row, t in zip(heldout, texts) if parser(t) == row["answer"])
    return passed


def run(heldout_path, gen_sft_path, gen_dpo_path, min_delta=0.05):
    heldout = ea.load_heldout(heldout_path)
    sft = _align(heldout, _load_generations(gen_sft_path), "sft")
    dpo = _align(heldout, _load_generations(gen_dpo_path), "dpo")
    n = len(heldout)

    per_parser = {}
    for name, fn in PARSERS.items():
        a, b = score_arm(heldout, sft, fn), score_arm(heldout, dpo, fn)
        delta = (b - a) / n
        label = ea.verdict({"passed": a, "total": n, "accuracy": a / n},
                           {"passed": b, "total": n, "accuracy": b / n},
                           min_delta=min_delta)["label"]
        per_parser[name] = {"sft_passed": a, "dpo_passed": b, "total": n,
                            "sft_accuracy": round(a / n, 4),
                            "dpo_accuracy": round(b / n, 4),
                            "delta": round(delta, 4), "label": label}

    labels = {v["label"] for v in per_parser.values()}
    return {"per_parser": per_parser, "n": n, "min_delta": min_delta,
            "labels": sorted(labels),
            "symbol_consistency": "STABLE" if len(labels) == 1 else "UNSTABLE",
            "format_compliance": {
                "sft": sum(1 for t in sft if format_compliant(t)),
                "dpo": sum(1 for t in dpo if format_compliant(t)),
                "total": n,
            }}


def render_md(rep):
    out = [
        "# 解析口径敏感性（同一批 generations，换解析器重判）",
        "",
        f"样本 n={rep['n']}；min_delta={rep['min_delta']}（PREREG 跑前锁定，本表不事后调）。",
        f"**符号一致性 = {rep['symbol_consistency']}**"
        + ("（全部口径同符号）" if rep["symbol_consistency"] == "STABLE"
           else "（判决随解析器翻转：GAIN↔REGRESSION，不能当能力结论）"),
        "",
        "| 解析口径 | base+SFT | base+DPO | delta | verdict |",
        "|---|---|---|---|---|",
    ]
    for name, v in rep["per_parser"].items():
        out.append(f"| {name} | {v['sft_passed']}/{v['total']} | "
                   f"{v['dpo_passed']}/{v['total']} | {v['delta']:+.4f} | {v['label']} |")
    fc = rep["format_compliance"]
    out += ["",
            f"格式遵从（最后一行整行 `Answer: <int>`）：base+SFT {fc['sft']}/{fc['total']}、"
            f"base+DPO {fc['dpo']}/{fc['total']}。",
            "",
            "诚实边界：合成分=(A*B+C) mod M ≠GSM8K≠TMLR；本表只说明判决对解析器敏感，"
            "不外推为模型能力结论。"]
    return "\n".join(out) + "\n"


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="解析口径敏感性：判决是否随解析器翻转")
    ap.add_argument("--heldout", required=True)
    ap.add_argument("--gen-sft", required=True)
    ap.add_argument("--gen-dpo", required=True)
    ap.add_argument("--out-json", default=None)
    ap.add_argument("--out-md", default=None)
    ap.add_argument("--min-delta", type=float, default=0.05)
    a = ap.parse_args(argv)
    rep = run(a.heldout, a.gen_sft, a.gen_dpo, min_delta=a.min_delta)
    print(render_md(rep))
    for path, text in ((a.out_json, json.dumps(rep, ensure_ascii=False, indent=1)),
                       (a.out_md, render_md(rep))):
        if path:
            Path(path).write_text(text, encoding="utf-8")
            print(f"[done] -> {path}")
    return rep


if __name__ == "__main__":
    main()