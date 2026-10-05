"""Statistical power for the Amendment-1 Track-B decision rule, computed not asserted.

Why this file exists. PREREG-round4.md Amendment 1 fixes a three-branch decision
rule on the `step-calc` vs `cot-zero` contrast:

  (i)   any set significant at p < 0.05  -> a new finding
  (ii)  no set significant               -> consistent with the Track A null
  (iii) mixed                            -> reported as-is

Branch (ii) is a claim of NO DIFFERENCE, so it silently assumes every set had the
power to detect a difference. The first run of the primary contrast falsified that
assumption on one of the three sets: on MultiArith (180 questions) both arms scored
180/180 and their correct-answer sets were IDENTICAL, so the McNemar discordant
count d = b + c is exactly 0.

At d = 0 no sample size repairs the test, because the statistic is computed from
the same zero pairs; a larger n can only enlarge the two identical sets. So that
set contributes ZERO evidence to branch (ii) -- which is not the same statement as
"the two arms agree", and the record must not blur the two.

This script recomputes, from the measured files only:

  * per-set d and the smallest imbalance that would reach p < 0.05 at that d,
    so a reader can see how far each set is from a detectable effect;
  * the smallest d at which even the most extreme imbalance (all one-sided)
    still fails, which is the floor below which no set can ever fire branch (i);
  * an ex-ante projection for the sets not yet measured, using the discordant
    RATE observed in the older `direct` vs `step-calc` contrast on the same
    questions, discounted because `cot-zero` is standard CoT and should sit
    closer to `step-calc` than the number-only `direct` does.

Every number printed is computed here from files in the repository. Nothing is
transcribed by hand.

Usage:
    python3 scripts/trackB_power.py
    python3 scripts/trackB_power.py --markdown   # the table in TRANSFER_RECORD.md
"""
from __future__ import annotations

import argparse
import json
from math import comb
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROUND = ROOT / "results" / "rounds" / "round4"
ALPHA = 0.05


def mcnemar_exact(b: float, c: float) -> float:
    """Two-sided exact McNemar, identical in shape to evokit.stats.mcnemar_two_sided.

    Accepts floats so the projection below can pass an estimated count without
    rounding first; both operands are rounded to whole cells here, which is what
    the binomial needs. Computed independently on purpose: this script must be able
    to disagree with the value the runner recorded, otherwise it cannot check
    anything.
    """
    b, c = int(round(b)), int(round(c))
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def cross_check(verbose: bool = True) -> bool:
    """The local McNemar must reproduce evokit.stats on real recorded cells."""
    if not (ROOT / "results" / "rounds" / "round4" / "transfer-cotzero-multiarith.json").exists():
        return False
    sys_path = str(ROOT)
    if sys_path not in __import__("sys").path:
        __import__("sys").path.insert(0, sys_path)
    from evokit.stats import mcnemar_two_sided

    src = ROUND / "transfer-cotzero-multiarith.json"
    data = json.loads(src.read_text(encoding="utf-8"))
    rec = data["pairs"]["step-calc_vs_cot-zero"]
    for b, c in [(rec["better"], rec["worse"]), (7, 2), (2, 7), (0, 0), (13, 4)]:
        assert abs(mcnemar_exact(b, c) - mcnemar_two_sided(b, c)) < 1e-12, (
            b, c, mcnemar_exact(b, c), mcnemar_two_sided(b, c))
    if verbose:
        print("cross-check: local McNemar agrees with evokit.stats on 5 (b, c) pairs")
    return True


def smallest_d_that_could_fire_branch_one() -> int:
    """Below this discordant count even a one-sided split cannot reach alpha."""
    for d in range(1, 200):
        if mcnemar_exact(d, 0) < ALPHA:
            return d
    return -1


def min_imbalance_to_fire(d: int) -> int | None:
    """Fewest b cells (c = d - b) that make the exact test significant."""
    for b in range(d // 2 + 1, d + 1):
        if mcnemar_exact(b, d - b) < ALPHA:
            return b - (d - b)
    return None


def measured_sets() -> list[dict]:
    """Only sets whose primary-contrast file exists AND passed the fail-closed gate."""
    rows = []
    for name in ("multiarith", "svamp", "asdiv"):
        path = ROUND / f"transfer-cotzero-{name}.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("INCOMPLETE"):
            print("skip %-11s: file is INCOMPLETE (fail-closed gate fired)" % name)
            continue
        rec = data["pairs"]["step-calc_vs_cot-zero"]
        d = rec["better"] + rec["worse"]
        rows.append({"name": name, "n": data["meta"]["n"],
                     "totals": data["totals"], "b": rec["better"], "c": rec["worse"],
                     "d": d, "p": rec["p"], "gain": rec["gain"],
                     "sat": rec["better"] == 0 and rec["worse"] == 0})
    return rows


def discordant_rate_from_direct_contrast() -> dict:
    """Observed discordant rate of the older direct vs step-calc contrast."""
    out = {}
    for name in ("svamp", "asdiv"):
        path = ROUND / f"transfer-{name}.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        rec = data["pairs"]["direct_vs_step-calc"]
        n = len(data["details"])
        out[name] = {"n": n, "d": rec["better"] + rec["worse"],
                     "rate": (rec["better"] + rec["worse"]) / n}
    return out


def project(name: str, rate: float, shrink: float, skew: float) -> dict:
    d = rate["n"] * rate["rate"] * shrink
    b = int(d * skew)
    c = d - b
    return {"set": name, "n": rate["n"], "rate": rate["rate"], "shrink": shrink,
            "skew": skew, "d_est": d, "b": b, "c": c,
            "p": mcnemar_exact(b, c), "fires": mcnemar_exact(b, c) < ALPHA}


def render(markdown: bool) -> str:
    lines = []
    rows = measured_sets()
    floor = smallest_d_that_could_fire_branch_one()
    rates = discordant_rate_from_direct_contrast()
    notes: list[str] = []

    if markdown:
        lines.append("### Track-B 主对照的检验力（由 `scripts/trackB_power.py` 复算）")
        lines.append("")
        lines.append("| 数据集 | n | step-calc | cot-zero | discordant d | McNemar p | 状态 |")
        lines.append("|---|---|---|---|---|---|---|")
        for r in rows:
            sc = r["totals"]["step-calc"]
            cz = r["totals"]["cot-zero"]
            status = "**饱和（无检验力）**" if r["sat"] else (
                "显著" if r["p"] < ALPHA else "未检出差异")
            lines.append("| %s | %d | %d | %d | %d | %.4f | %s |"
                         % (r["name"], r["n"], sc, cz, r["d"], r["p"], status))
    else:
        print("MEASURED (primary contrast, step-calc vs cot-zero)")
        print("%-11s %5s %11s %9s %6s %9s %s"
              % ("set", "n", "step-calc", "cot-zero", "d", "p", "status"))
        for r in rows:
            sc = r["totals"]["step-calc"]
            cz = r["totals"]["cot-zero"]
            status = "SATURATED (zero power)" if r["sat"] else (
                "significant" if r["p"] < ALPHA else "not detected")
            print("%-11s %5d %11d %9d %6d %9.4f %s"
                  % (r["name"], r["n"], sc, cz, r["d"], r["p"], status))

    lines.append("")
    if markdown:
        lines.append("- 最极端偏斜（全部 discordant 归一侧）时仍需 **d ≥ %d** 才可能达到 "
                     "`p < 0.05`；实测 MultiArith 的 d = 0，任何 n 都无法改变该统计量，"
                     "因为正确题集合完全相同。" % floor)
    else:
        print("\nSmallest d at which even a fully one-sided split reaches p<0.05: %d" % floor)
        print("  (measured MultiArith has d = 0, and no n repairs that: the statistic")
        print("   is computed from the same identical pair of answer sets.)")

    if markdown:
        verified = cross_check(verbose=False)
        if verified:
            notes.append("- 本节每个数字由 `python3 scripts/trackB_power.py` 从仓内文件复算；"
                         "其 McNemar 本地实现与 `evokit.stats.mcnemar_two_sided` 在 5 组 "
                         "(b, c) 上断言一致（abs 差 < 1e-12），未通过则脚本直接抛错。")
    else:
        print()
        cross_check()

    if rates:
        if not markdown:
            print("\nDISCORDANT RATE observed in the older direct vs step-calc contrast:")
            for name, r in rates.items():
                print("  %-7s n=%-5d d=%-4d rate=%.1f%%" % (name, r["n"], r["d"], 100 * r["rate"]))
            print("\nPROJECTION for the unmeasured contrast (cos assumption: cot-zero is")
            print("standard CoT, so it sits closer to step-calc than number-only direct,")
            print("hence FEWER discordant cells -- `shrink` discounts the observed rate):")
            print("%-7s %7s %7s %6s %7s %7s %8s %s"
                  % ("set", "shrink", "skew", "d_est", "b", "c", "p", "branch (i)?"))
        proj = []
        for name, r in rates.items():
            for shrink in (0.5, 0.3, 0.15):
                for skew in (0.7, 0.6):
                    p = project(name, r, shrink, skew)
                    if not markdown:
                        print("%-7s %7.2f %7.2f %6.0f %7d %7.0f %8.4f %s"
                              % (p["set"], shrink, skew, p["d_est"], p["b"], p["c"], p["p"],
                                 "FIRES" if p["fires"] else "-"))
                    proj.append(p)
        fires = [p for p in proj if p["fires"]]
        if markdown and fires:
            best = min(p["shrink"] for p in fires)
            names = sorted({p["set"] for p in fires if p["shrink"] == best})
            notes.append(
                "- 外推（乐观假设：discordant 仅为 `direct` 对照的 %.0f%%，且 70%% 的 "
                "discordant 偏斜给 step-calc），%s 仍会触发分支 (i)。因此 ASDiv 是该判定"
                "规则能否落地分支 (ii) 的承重墙，不是可选补充。"
                % (100 * best, " / ".join(names)))
            # the honest side: which assumptions fail before the projection stops firing
            misses = [p for p in proj if not p["fires"]]
            if misses:
                worst = max(misses, key=lambda p: p["p"])
                notes.append(
                    "- 反面：外推在「discordant 砍到 %.0f%% 且偏斜仅 60%%」时会失效"
                    "（%s 投影 p = %.3f）。所以「ASDiv 一定能显著」**不是**预注册的承诺，"
                    "只是当前先验下的期望；分支 (ii) 仍可能被触发。"
                    % (100 * worst["shrink"], worst["set"], worst["p"]))
    return "\n".join(lines + [""] + [n for n in notes if n]) if markdown \
        else "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--markdown", action="store_true",
                    help="emit the table for TRANSFER_RECORD.md instead of a console report")
    a = ap.parse_args()
    if a.markdown:
        print(render(markdown=True))
    else:
        render(markdown=False)


if __name__ == "__main__":
    main()