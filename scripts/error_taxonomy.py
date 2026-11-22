"""误差分型：把 explicit 口径判出的"错"分成真算术错与输出失败两类。

背景（本次深挖的结论）：
  ability-B 的 last_int 口径判 GAIN(+0.1333)、explicit 口径判 REGRESSION(-0.1667)。
  先前把 explicit 错当成"真算术能力错"（SFT 3 / DPO 16）。但这台尺子证明那个
  分母不干净：60 题里两组都有大量题在 max_new_tokens=96 上限被截断，或贪心解码退化，
  根本没产出规范 Answer 字段——它们被 explicit 口径一律记成"错"，却没测到算术能力。

诚实边界（必须写在产物里）：
  generations 只有 {id, answer, text}，没有 finish_reason。所以"截断/退化"只能
  靠文本形态启发式判断，不能客观归因于 token 上限。所有 NOANS_* 类 heuristic=True。

这是**诊断层**，不改 parser_sensitivity / ability_report / eval_ability 的任何口径
与数字（避免移动已发表读数）。只新增分型视图与有效测量规模两层口径。
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_ability as ea  # noqa: E402
from synth_ability import score_response  # noqa: E402

# 五类
ANSWER_CORRECT = "ANSWER_CORRECT"                       # 有 Answer 字段且数值正确
ANSWER_WRONG_TRUEARITH = "ANSWER_WRONG_TRUEARITH"       # 有 Answer 字段且数值错误
NOANS_TRUNCATED_MIDSTEP = "NOANS_TRUNCATED_MIDSTEP"     # 无 Answer，停在中途计算（启发式）
NOANS_DEGENERATE = "NOANS_DEGENERATE"                   # 无 Answer，解码退化/循环
NOANS_COMPUTED_BUT_UNFORMATTED = "NOANS_COMPUTED_BUT_UNFORMATTED"  # 算出正确值但没写 Answer
NOANS_OTHER = "NOANS_OTHER"

ALL_CATEGORIES = (
    ANSWER_CORRECT, ANSWER_WRONG_TRUEARITH, NOANS_TRUNCATED_MIDSTEP,
    NOANS_DEGENERATE, NOANS_COMPUTED_BUT_UNFORMATTED, NOANS_OTHER,
)
NOANS_CATEGORIES = (
    NOANS_TRUNCATED_MIDSTEP, NOANS_DEGENERATE,
    NOANS_COMPUTED_BUT_UNFORMATTED, NOANS_OTHER,
)

# 有 Answer 字段：与 parser_sensitivity.first_answer 同一正则，保证口径一致
_ANS = re.compile(r"Answer\s*[:：]?\s*(-?\d+)")
# 文本里已算出某值（"remainder 10" / "is 8" / "Final integer: 6"）——启发式证据
_COMPUTED = re.compile(
    r"(?:remainder|equals?|is|final(?:\s+integer)?|result)\s*[:：]?\s*(-?\d+)\s*[.!]?",
    re.I,
)
# 解码退化：下标/上标 Unicode 数字、或同一短 token 长串重复
_SUPERDIGIT = re.compile(r"[\u2070-\u209F\u2080-\u2089]")
_REPEAT_TOKEN = re.compile(r"(\d{1,3}(?:\.\d{1,3}){1,2})[.;]?\s*(?:\1[.;]?\s*){3,}")


def _looks_degenerate(text):
    if _SUPERDIGIT.search(text):
        return True
    if _REPEAT_TOKEN.search(text):
        return True
    # 单个字符/短串连续重复 ≥8 次（如 0.0.0.0... 已被上面覆盖，这里兜底）
    if re.search(r"(.{1,2})\1{7,}", text):
        return True
    return False


def _stops_midstep(text):
    """启发式：文本停在中途计算（末尾是运算符、=、除法片段、无终止标点）。"""
    t = text.rstrip()
    if not t:
        return True
    tail = t[-24:]
    if re.search(r"[=+\-*/÷:]\s*$", tail):
        return True
    if re.search(r"\d\s*$", tail) and not re.search(r"[.!:]\s*$", tail):
        # 以裸数字结束且无句号 —— 多数是被截断在中间步骤
        return True
    return False


def classify(text, expected):
    """把单条生成分型。返回 dict；NOANS_* 一律 heuristic=True。"""
    t = text or ""
    m = _ANS.search(t)
    if m is not None:
        value = int(m.group(1))
        cat = ANSWER_CORRECT if value == int(expected) else ANSWER_WRONG_TRUEARITH
        return {
            "category": cat, "has_answer_field": True, "answer_value": value,
            "expected": int(expected), "heuristic": False,
        }

    # 无 Answer 字段 —— 以下全为启发式
    if _looks_degenerate(t):
        cat = NOANS_DEGENERATE
    else:
        # 文本里是否已算出与 expected 相同的值（只差写进 Answer）
        computed = [int(x) for x in _COMPUTED.findall(t)]
        # 末尾 `=<expected>`（允许尾随标点）也算"算出正确值只差写 Answer"
        # 例 s100029 "... 2239-2232=7"。只在末尾匹配，避免把中间步骤的 =N 误计。
        if re.search(r"=\s*" + re.escape(str(int(expected))) + r"\s*[.!]?\s*$", t):
            computed.append(int(expected))
        if int(expected) in computed:
            cat = NOANS_COMPUTED_BUT_UNFORMATTED
        elif _stops_midstep(t):
            cat = NOANS_TRUNCATED_MIDSTEP
        else:
            cat = NOANS_OTHER
    return {
        "category": cat, "has_answer_field": False, "answer_value": None,
        "expected": int(expected), "heuristic": True,
    }


def effective_measurement(rows):
    """计算清单规模(L1) / 可评分规模(L2) / 启发式排除规模(L3) 与分型分布。"""
    cats = Counter()
    per_case = {}
    for row in rows:
        r = classify(row["text"], row["answer"])
        cats[r["category"]] += 1
        per_case[row["id"]] = r["category"]

    n = len(rows)
    l2 = cats[ANSWER_CORRECT] + cats[ANSWER_WRONG_TRUEARITH]
    l3 = sum(cats[c] for c in NOANS_CATEGORIES)
    assert l2 + l3 == n
    return {
        "L1_manifest": n,
        "L2_scorable": l2,          # 有规范 Answer 字段，可判对错
        "L3_heuristic_excluded": l3,  # 无 Answer，输出失败，未测到算术能力
        "categories": {c: cats[c] for c in ALL_CATEGORIES},
        "computed_but_unformatted": cats[NOANS_COMPUTED_BUT_UNFORMATTED],
        # 旧假设：所有 NOANS 都算算术错 —— 用于变异反证，证明确实夸大了
        "naive_arith_wrong_all_noans": cats[ANSWER_WRONG_TRUEARITH] + l3,
        "per_case": per_case,
    }


def render_md(sft, dpo):
    def block(name, a):
        c = a["categories"]
        lines = [
            f"### {name}", "",
            f"- L1 清单规模：{a['L1_manifest']}",
            f"- L2 可评分规模（有规范 Answer 字段）：{a['L2_scorable']}",
            f"- L3 启发式排除（输出失败，未测到算术能力）：{a['L3_heuristic_excluded']}",
            "", "| 分型 | 题数 |", "|---|---|",
        ]
        for cat in ALL_CATEGORIES:
            lines.append(f"| {cat} | {c[cat]} |")
        lines += [
            "",
            f"旧假设（NOANS 全算算术错）的真算术错 = {a['naive_arith_wrong_all_noans']}；"
            f"分型后 ANSWER_WRONG_TRUEARITH = {c[ANSWER_WRONG_TRUEARITH]}。",
            "",
        ]
        return lines

    lines = [
        "# 误差分型诊断：explicit 口径的\"错\"里有多少是算术错", "",
        "## 诚实边界", "",
        "- generations 只有 `{id, answer, text}`，**没有 finish_reason**。"
        "无法客观判定是否触到 `max_new_tokens=96` 上限。",
        "- 因此 NOANS_* 四类的\"截断/退化\"判断全部是**启发式**（文本形态），"
        "每条带 `heuristic=True`，不能当成客观归因。",
        "- 本尺子是诊断层，不改 parser_sensitivity / ability_report 的任何口径与数字。", "",
        "## 两层口径", "",
        "- L1 = 清单里 60 题（只能说\"清单 60 题\"）。",
        "- L2 = 真正产出了规范 Answer 字段、能判对错的题数（这才该引用为实测规模）。",
        "- L3 = 无 Answer 字段、根本没测到算术能力的题数（截断/退化/算出没写格式）。", "",
    ]
    lines += block("SFT (base)", sft)
    lines += block("DPO (adapter)", dpo)
    lines += [
        "## 结论", "",
        "- 两种口径各有污染源：last_int 被 Answer 后续写数字污染；"
        "explicit 被 token 截断/解码退化污染。",
        "- \"explicit = 真算术能力\"不成立：L3 题根本没测到算术能力却被记成\"错\"。",
        "- \"DPO 真算术错 16\" 的分母不干净；真问题是 max_new_tokens=96 太短 + 贪心退化，"
        "输出质量成了混淆变量。", "",
    ]
    return "\n".join(lines)


def main():
    root = Path(__file__).resolve().parents[1]
    base = root / "results/qlora-ability-b"
    gsft = json.loads((base / "generations/generations_sft.json").read_text(encoding="utf-8"))
    gdpo = json.loads((base / "generations/generations_dpo.json").read_text(encoding="utf-8"))
    sft = effective_measurement(gsft)
    dpo = effective_measurement(gdpo)
    out = {
        "source": "results/qlora-ability-b/generations/generations_{sft,dpo}.json",
        "max_new_tokens": 96,
        "finish_reason_available": False,
        "sft": sft, "dpo": dpo,
    }
    (base / "error_taxonomy.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (base / "error_taxonomy.md").write_text(
        render_md(sft, dpo) + "\n", encoding="utf-8")
    print(json.dumps({
        "sft_L2": sft["L2_scorable"], "dpo_L2": dpo["L2_scorable"],
        "sft_L3": sft["L3_heuristic_excluded"], "dpo_L3": dpo["L3_heuristic_excluded"],
    }))


if __name__ == "__main__":
    main()
