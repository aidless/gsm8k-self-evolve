"""Report gains in the form arXiv 2609.39148 uses, and state what this repo cannot supply.

2609.39148 ("Do Self-Evolving Skills Generalize to Held-Out Tasks?", SANKEN / Osaka
University) defines, for a skill s on split q:

    G_q(s)   = 100 * [ a_q(s) - a_q(s_empty) ]        q in {train, test}
    Retention(s) = G_test(s) - G_train(s)

where a_empty is the NO-SKILL agent, i.e. the model answering without the artifact at
all. Retention 0 means the whole training gain carried over; negative retention with
positive G_test means skill overfitting; G_test <= 0 means the artifact is harmful.
The paper reports 21 skills with G_train > 0: 5 keep all of it, 13 part, 3 none
(2 harmful), retention from +3.4 to -15.0.

This repo can report the G_q(s) DENOMINATOR (a_q(s)) exactly, but it has no
NO-SKILL ARM anywhere: every round in this repository contrasts one artifact against
another artifact. `direct` (number-only, "return only the final number") is the
weakest arm present, and it is still an instruction-conditioned arm -- it is not
a_empty. Substituting direct for a_empty would silently redefine the quantity and
bias every G downward by a_q(direct), so this script refuses to do it.

What it does:
  1. Prints the measured a_q(s) for every arm, with the counts they came from.
  2. Prints what G_q(s) WOULD be under an assumed a_empty, as a function -- not a
     number -- so the dependency is explicit and auditable.
  3. Reports the one thing that IS measured and IS in the paper's language: the
     signed gain between artifacts, and the paired exact McNemar on it.

Zero model calls. Reads only committed result files.

Usage:
    python scripts/retention_report.py
    python scripts/retention_report.py --json
    python scripts/retention_report.py --empty 0.5     # what-if for a assumed no-skill rate
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def _betainc(a: float, b: float, x: float) -> float:
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    front = math.exp(math.log(x) * a + math.log(1 - x) * b - lbeta) / a
    f, c, d = 1.0, 1.0, 0.0
    for i in range(300):
        m = i // 2
        if i == 0:
            num = 1.0
        elif i % 2 == 0:
            num = (m * (b - m) * x) / ((a + 2 * m - 1) * (a + 2 * m))
        else:
            num = -((a + m) * (a + b + m) * x) / ((a + 2 * m) * (a + 2 * m + 1))
        d = 1.0 + num * d
        d = d if abs(d) > 1e-30 else 1e-30
        d = 1.0 / d
        c = 1.0 + num / c
        c = c if abs(c) > 1e-30 else 1e-30
        f *= c * d
        if abs(1.0 - c * d) < 1e-12:
            break
    return front * (f - 1.0)


def mcnemar_two_sided(b: int, c: int) -> float:
    """Exact two-sided binomial test, matching evokit.stats.mcnemar_two_sided."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return min(1.0, 2.0 * tail)


def load() -> dict:
    ta = json.loads((ROOT / "results/rounds/round4/trackA-merged.json").read_text(encoding="utf-8"))
    n = int(ta["meta"]["n"])
    arms = {}
    for k, v in ta["totals"].items():
        cnt = float(v)
        arms[k] = {"count": int(cnt), "rate": cnt / n if cnt > 1 else cnt, "n": n}
    r3 = json.loads((ROOT / "results/rounds/round3/heldout40-round3.json").read_text(encoding="utf-8"))
    n3 = int(r3["n"])
    r3arms = {}
    for k in ("step_calc", "reflect_retry", "textgrad"):
        v = r3[k]
        r3arms[k] = {"count": int(v["passed"]), "rate": float(v["score"]), "n": n3}
    out = {"trackA_merged_200": arms, "round3_heldout40": r3arms,
           "trackA_pairs": ta["pairs"]}
    out["no_skill"] = _load_no_skill()
    return out


def _load_no_skill() -> dict | None:
    """The measured a_empty, or None when no no-skill arm has been merged yet.

    Read from results/rounds/round4/no-skill-merged.json, which
    scripts/merge_no_skill_arm.py produces from the two per-set run files after
    re-deriving their totals from their own details. It is deliberately NOT read
    from the per-set files or recomputed here: a_empty enters every G, so the one
    number that shifts all of them deserves the same verification the other arms
    get, and that verification lives in the merge script.

    n must match trackA-merged: a_empty measured on a different question set is not
    the denominator of these G values, so a mismatch is an error rather than a
    warning. `direct` is never accepted as a stand-in here -- it is an
    instruction-conditioned arm, not an empty prompt.
    """
    path = ROOT / "results/rounds/round4/no-skill-merged.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if set(data) != {"meta", "totals", "pairs", "details"}:
        raise SystemExit("no-skill-merged.json: unexpected top-level keys %s"
                         % sorted(data))
    if data["meta"]["policies"] != ["no-skill"]:
        raise SystemExit("no-skill-merged.json: policies is %s, expected exactly "
                         "['no-skill']; another arm's file would redefine a_empty"
                         % data["meta"]["policies"])
    n = int(data["meta"]["n"])
    det = data["details"]
    if len(det) != n:
        raise SystemExit("no-skill-merged.json: meta.n is %d but details holds %d rows"
                         % (n, len(det)))
    bad = [q for q, row in det.items() if row["no-skill"].get("error")]
    if bad:
        raise SystemExit("no-skill-merged.json: %d cell(s) carry a transport error %s; "
                         "a call that never reached the model is not a wrong answer"
                         % (len(bad), bad[:5]))
    passed = sum(1 for row in det.values() if row["no-skill"]["passed"])
    if passed != data["totals"]["no-skill"]:
        raise SystemExit("no-skill-merged.json: totals claims %s but recomputing from "
                         "details gives %d" % (data["totals"]["no-skill"], passed))
    return {"count": passed, "rate": passed / n, "n": n,
            "sources": data["meta"].get("sources"),
            "model": data["meta"].get("model")}


def report(empty: float | None) -> dict:
    d = load()
    arms = d["trackA_merged_200"]
    inc = arms["step-calc"]["rate"]
    ns = d["no_skill"]
    if ns is not None and ns["n"] != arms["step-calc"]["n"]:
        raise SystemExit(
            "a_empty was measured on n=%d but the artifact arms on n=%d; retention "
            "subtracts one from the other, so the two must be the same question set"
            % (ns["n"], arms["step-calc"]["n"]))
    # With a measured a_empty, the G values stop being a function of an assumption
    # and become numbers. They are still G on the TEST side only: G_train needs the
    # training-split a_empty, which this repo never measures, so what follows is a
    # G_test column, NOT a retention.
    rows = []
    for name, a in sorted(arms.items(), key=lambda kv: -kv[1]["rate"]):
        if name == "step-calc":
            continue
        row = {
            "contrast": f"step-calc vs {name}",
            "a_step_calc": round(inc, 6),
            "a_challenger": round(a["rate"], 6),
            "signed_gain_vs_step_calc": round(a["rate"] - inc, 6),
            "n": a["n"],
        }
        if ns is not None:
            row["a_empty"] = round(ns["rate"], 6)
            row["G_test_100"] = round(100.0 * (a["rate"] - ns["rate"]), 4)
            row["G_step_calc_test_100"] = round(100.0 * (inc - ns["rate"]), 4)
        # The pairs block is keyed by orientation, and the direct-vs-step-calc pair is
        # stored the other way round. Look the pair up in whichever orientation exists,
        # then FLIP b/c when it is reversed so "better" always means "challenger better".
        pk, flipped = f"step-calc_vs_{name}", False
        if pk not in d["trackA_pairs"]:
            alt = f"{name}_vs_step-calc"
            if alt in d["trackA_pairs"]:
                pk, flipped = alt, True
        if pk in d["trackA_pairs"]:
            p = d["trackA_pairs"][pk]
            # In the stored orientation, better/worse are keyed "<A>_vs_<B>", meaning
            # "questions A got right that B got wrong". When the challenger is B rather
            # than A, the two counts swap: challenger-better = stored worse.
            b, c = (p["worse"], p["better"]) if flipped else (p["better"], p["worse"])
            row["pair_key_as_stored"] = pk
            row["orientation_flipped"] = flipped
            row["better"] = b
            row["worse"] = c
            row["mcnemar_p"] = p["p"]
            row["mcnemar_recomputed"] = mcnemar_two_sided(b, c)
            row["ledger_ok"] = p["ledger_ok"]
        rows.append(row)

    out = {
        "schema_version": 2,
        "zero_model_calls": True,
        "reference_paper": "arXiv:2609.39148 (Retention = G_test - G_train, G = 100*(a - a_noskill))",
        "measured": rows,
        "heldout_40_round3": d["round3_heldout40"],
        "no_skill_arm_present": ns is not None,
    }
    if ns is not None:
        out["a_empty_measured"] = ns
        out["retention_reported"] = False
        out["retention_why"] = (
            "a_empty is now MEASURED on the same %d-question blind set "
            "(%d/%d = %.6f, model %s, sources %s), so every G above is a measured "
            "quantity rather than a function of an assumption. But Retention is "
            "G_test - G_train, and G_train needs a_empty on the TRAINING split. This "
            "repo never measures the training split -- every round runs on the same "
            "held-out blind set, and the held-out files never feed back into "
            "challengers, lessons or prompts. So what is reported here is a G_test "
            "column, and calling it retention would be a category error."
            % (ns["n"], ns["count"], ns["n"], ns["rate"], ns["model"],
               ", ".join(ns["sources"] or [])))
    else:
        out["blocking_gap"] = (
            "a_empty is NOT measured in this repo. Every contrast here is artifact-vs-"
            "artifact. 'direct' (number-only) is not a no-skill arm; using it as one "
            "would subtract a_q(direct) from every G and bias all retention downward. "
            "Running a true no-skill arm (empty prompt) on the 200-question blind set is "
            "200 model calls and closes this: EVO_MODEL=qwen2.5:7b python3 "
            "scripts/run_no_skill_arm.py && python3 scripts/merge_no_skill_arm.py"
        )

    if empty is not None:
        hypothetical = {}
        for name, a in arms.items():
            hypothetical[name] = {
                "a_q": round(a["rate"], 6),
                "G_q_if_empty_%.2f" % empty: round(100.0 * (a["rate"] - empty), 4),
            }
        step_t = hypothetical["step-calc"]
        for name in arms:
            if name != "step-calc":
                g_t = hypothetical[name]["G_q_if_empty_%.2f" % empty]
                g_sc = step_t["G_q_if_empty_%.2f" % empty]
                hypothetical[name]["retention_if_this_were_test"] = round(g_t - g_sc, 4)
        out["hypothetical_at_assumed_empty"] = {"a_empty": empty, "arms": hypothetical,
                                                "warning": "ILLUSTRATIVE ONLY. The train-side "
                                                           "G_train is not measured on this "
                                                           "blind set, so these numbers are "
                                                           "not a retention."}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--empty", type=float, default=None,
                    help="what-if: assumed no-skill accuracy in [0,1]")
    a = ap.parse_args()
    res = report(a.empty)
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("Retention report (form of arXiv:2609.39148), zero model calls\n")
        print(f"{'contrast':28s} {'a(step-calc)':>13s} {'a(chal)':>9s} {'gain':>8s} "
              f"{'better:worse':>14s} {'McNemar p':>11s} {'recomputed':>11s}")
        for r in res["measured"]:
            bw = f"{r.get('better')}:{r.get('worse')}" if "better" in r else "-"
            p = f"{r['mcnemar_p']:.4g}" if "mcnemar_p" in r else "-"
            rc = f"{r['mcnemar_recomputed']:.4g}" if "mcnemar_recomputed" in r else "-"
            print(f"{r['contrast']:28s} {r['a_step_calc']:13.3f} {r['a_challenger']:9.3f} "
                  f"{r['signed_gain_vs_step_calc']:+8.3f} {bw:>14s} {p:>11s} {rc:>11s}")
        print(f"\nno_skill_arm_present = {res['no_skill_arm_present']}")
        if res["no_skill_arm_present"]:
            ns = res["a_empty_measured"]
            print(f"a_empty (MEASURED) = {ns['count']}/{ns['n']} = {ns['rate']:.6f}"
                  f"   [model {ns['model']}]")
            print("-" * 100)
            print(f"{'contrast':28s} {'a(chal)':>9s} {'G_test':>9s} {'G_step-calc':>13s} "
                  f"{'better:worse':>14s} {'McNemar p':>11s}")
            for r in res["measured"]:
                bw = f"{r.get('better')}:{r.get('worse')}" if "better" in r else "-"
                p = f"{r['mcnemar_p']:.4g}" if "mcnemar_p" in r else "-"
                print(f"{r['contrast']:28s} {r['a_challenger']:9.3f} "
                      f"{r['G_test_100']:+9.2f} {r['G_step_calc_test_100']:+13.2f} "
                      f"{bw:>14s} {p:>11s}")
            print(f"\nRETENTION IS NOT REPORTED. {res['retention_why']}")
        else:
            print(f"BLOCKING GAP: {res['blocking_gap']}")
        if a.empty is not None:
            print(f"\n--- ILLUSTRATIVE what-if at a_empty = {a.empty} ---")
            for k, v in sorted(res["hypothetical_at_assumed_empty"]["arms"].items()):
                extra = ""
                if "retention_if_this_were_test" in v:
                    extra = f"  retention={v['retention_if_this_were_test']:+.2f}"
                print(f"  {k:16s} a={v['a_q']:.3f}  G={list(v.values())[1]:+8.2f}{extra}")
    return 0


if __name__ == "__main__":
    sys.exit(main())