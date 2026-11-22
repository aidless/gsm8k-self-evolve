"""token 上限假设的可证伪实测（96 → 256）：判定层。

这是 error_taxonomy / parser_sensitivity 之后的第三发。前两发把混淆变量定位到
"max_new_tokens=96 太短 + greedy 退化"，但那只是文本形态启发式推断。本尺子读
96（已落盘）与 256（云端重跑）两份 error_taxonomy 产物，按 PREREG-256.md:28-39
跑前锁死的判据机械判决三态，不事后调阈值。

判据（PREREG-256.md 跑前锁死）：
  H_token  = 256 下 SFT 的 NOANS_TRUNCATED_MIDSTEP 11→≤3 且 SFT L3 12→≤4
  H_greedy = 256 下 DPO 的 NOANS_DEGENERATE 仍 ≥2（不塌缩）
  三态（PREREG:37-39 形式定义）：
    TOKEN_LIMIT_DOMINANT = H_token 成立 且 H_greedy 不成立
    MIXED = H_token 成立 且 H_greedy 成立（两条都成立）
    NEITHER = H_token 不成立
  注：PREREG:37 括号内自然语言"退化不塌缩"与同句形式条件相反，是笔误；
  以形式定义为准（:35「由真假组合机械决定」），并在报告里如实记录该矛盾。

诚实边界：generations 无 finish_reason，截断/退化是启发式；本尺子是存在性 probe
不是能力结论；256 产物缺失记 INCOMPLETE 不外推；不改任何现有口径与数字。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import error_taxonomy as et  # noqa: E402

# 类别常量复用 error_taxonomy（同一套定义，避免两处漂移）
ANSWER_CORRECT = et.ANSWER_CORRECT
ANSWER_WRONG_TRUEARITH = et.ANSWER_WRONG_TRUEARITH
NOANS_TRUNCATED_MIDSTEP = et.NOANS_TRUNCATED_MIDSTEP
NOANS_DEGENERATE = et.NOANS_DEGENERATE
NOANS_COMPUTED_BUT_UNFORMATTED = et.NOANS_COMPUTED_BUT_UNFORMATTED
NOANS_OTHER = et.NOANS_OTHER

# 跑前锁死的阈值（PREREG-256.md:32-33）
SFT_TRUNC_96 = 11
SFT_TRUNC_256_MAX = 3
SFT_L3_96 = 12
SFT_L3_256_MAX = 4
DPO_DEGEN_96 = 3
DPO_DEGEN_256_MIN = 2


def _cat(arm, name):
    return arm["categories"][name]


def judge(b96, b256, sft_l3_256_max=SFT_L3_256_MAX):
    """按 PREREG 判据把 96/256 两份分型映射成三态；256 缺失记 INCOMPLETE。"""
    from_96 = {
        "sft_trunc": _cat(b96["sft"], NOANS_TRUNCATED_MIDSTEP),
        "sft_l3": b96["sft"]["L3_heuristic_excluded"],
        "dpo_degen": _cat(b96["dpo"], NOANS_DEGENERATE),
    }
    result = {
        "thresholds": {
            "sft_trunc_256_max": SFT_TRUNC_256_MAX,
            "sft_l3_256_max": sft_l3_256_max,
            "dpo_degen_256_min": DPO_DEGEN_256_MIN,
        },
        "baseline_96": from_96,
    }
    if not b256:
        result.update({"verdict": "INCOMPLETE", "reason": "no_256_artifacts",
                       "h_token": None, "h_greedy": None})
        return result

    sft_trunc_256 = _cat(b256["sft"], NOANS_TRUNCATED_MIDSTEP)
    l3_256 = b256["sft"]["L3_heuristic_excluded"]
    degen_256 = _cat(b256["dpo"], NOANS_DEGENERATE)

    h_token = sft_trunc_256 <= SFT_TRUNC_256_MAX and l3_256 <= sft_l3_256_max
    h_greedy = degen_256 >= DPO_DEGEN_256_MIN
    if not h_token:
        verdict = "NEITHER"
    elif h_greedy:
        verdict = "MIXED"
    else:
        verdict = "TOKEN_LIMIT_DOMINANT"

    result.update({
        "verdict": verdict, "h_token": h_token, "h_greedy": h_greedy,
        "sft_trunc": {"from": from_96["sft_trunc"], "to": sft_trunc_256,
                      "threshold": SFT_TRUNC_256_MAX},
        "sft_l3": {"from": from_96["sft_l3"], "to": l3_256,
                   "threshold": sft_l3_256_max},
        "dpo_degen": {"from": from_96["dpo_degen"], "to": degen_256,
                      "threshold": DPO_DEGEN_256_MIN},
        "probe_256": {
            "sft_trunc": sft_trunc_256, "sft_l3": l3_256, "dpo_degen": degen_256,
        },
    })
    return result


def symbol_verdict(rep):
    """从 parser_sensitivity 报告重算符号一致性（不看它自报的字段，防造纸面值）。"""
    labels = {v["label"] for v in rep["per_parser"].values()}
    return "STABLE" if len(labels) == 1 else "UNSTABLE"


def build_report(b96, b256, symbol_256, symbol_96):
    return {
        "intervention": "max_new_tokens 96 -> 256 (only change, PREREG-256.md frozen)",
        "prereg_locked_at": "2026-11-22T15:35:00Z",
        "judgement": judge(b96, b256),
        "symbol": {"96": symbol_96, "256": symbol_256},
        "honest_boundaries": [
            "generations 无 finish_reason，截断/退化为文本形态启发式，非客观归因",
            "存在性 probe，不是能力结论；不宣称 DPO/SFT 谁算术更强",
            "PREREG-256.md:37 括号内'退化不塌缩'与形式条件相反是笔误；按形式定义判，未改判据",
            "256 产物缺失记 INCOMPLETE，不外推；不改现有 96 口径与数字",
        ],
        "baseline_96": b96,
        "probe_256": b256,
    }


def render_md(rep):
    j = rep["judgement"]
    lines = [
        "# token 上限假设的可证伪实测（96 → 256）", "",
        f"**判决 = {j['verdict']}**",
        f"唯一干预：{rep['intervention']}；预注册锁死 {rep['prereg_locked_at']}，本表不事后调阈值。", "",
        "## 诚实边界", "",
    ]
    lines += [f"- {b}" for b in rep["honest_boundaries"]]
    lines += ["", "## 判据与读数", ""]
    if j["verdict"] == "INCOMPLETE":
        lines += [f"- 256 产物缺失（{j['reason']}），记 INCOMPLETE，不外推。"]
    else:
        lines += [
            f"- H_token（SFT 截断塌缩 + L3 塌缩）={'成立' if j['h_token'] else '不成立'}："
            f"NOANS_TRUNCATED_MIDSTEP {j['sft_trunc']['from']}→{j['sft_trunc']['to']}（≤{j['sft_trunc']['threshold']}），"
            f"L3 {j['sft_l3']['from']}→{j['sft_l3']['to']}（≤{j['sft_l3']['threshold']}）。",
            f"- H_greedy（DPO 退化不塌缩）={'成立' if j['h_greedy'] else '不成立'}："
            f"NOANS_DEGENERATE {j['dpo_degen']['from']}→{j['dpo_degen']['to']}（≥{j['dpo_degen']['threshold']}）。",
            f"- 三态（PREREG:37-39 形式定义）：**{j['verdict']}**。",
        ]
    lines += [
        "", "## 符号稳健性（独立记录，不并入三态）", "",
        f"- 96 口径符号一致性：{rep['symbol']['96']}；256：{rep['symbol']['256']}。",
        "- 符号若仍 UNSTABLE，无论三态为何都不宣称能力增益（last_int 的 GAIN 是格式伪影）。", "",
    ]
    return "\n".join(lines)


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main():
    root = Path(__file__).resolve().parents[1]
    base = root / "results/qlora-ability-b"
    # 96 基线
    p96 = base / "error_taxonomy.json"
    b96 = _load(p96)
    b96 = {"sft": b96["sft"], "dpo": b96["dpo"]}
    s96 = _load(base / "parser_sensitivity.json")
    symbol_96 = symbol_verdict(s96)
    # 256 产物（云端拉回后落在 eval-256/）
    d256 = base / "eval-256"
    gs = d256 / "generations_sft.json"
    gd = d256 / "generations_dpo.json"
    b256 = None
    symbol_256 = symbol_96
    if gs.exists() and gd.exists():
        b256 = {
            "sft": et.effective_measurement(_load(gs)),
            "dpo": et.effective_measurement(_load(gd)),
        }
        import parser_sensitivity as ps
        heldout = root / "examples" / "synth_heldout.jsonl"
        if not heldout.exists():
            heldout = base / "synth_heldout.jsonl"
        s256 = ps.run(str(heldout), str(gs), str(gd), min_delta=0.05)
        symbol_256 = symbol_verdict(s256)
    rep = build_report(b96, b256, symbol_256, symbol_96)
    (base / "token_budget_probe.json").write_text(
        json.dumps(rep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (base / "token_budget_probe.md").write_text(render_md(rep) + "\n", encoding="utf-8")
    print(f"verdict={rep['judgement']['verdict']} "
          f"symbol_96={symbol_96} symbol_256={symbol_256}")


if __name__ == "__main__":
    main()
