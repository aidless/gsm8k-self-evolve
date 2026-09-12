"""Verify the provenance of this repo's question sets against official GSM8K.

Answers two questions that the paper's Soundness depends on:

  1. Are `examples/{gsm8k40,heldout40,heldout-batch2-160}.json` drawn from the
     official GSM8K *test* split (i.e. standard items, not self-authored)?
  2. Do any of them overlap the GSM8K *train* split (contamination check: a
     model pretrained on GSM8K train must not be evaluated on train items)?

Fetches the two official jsonl files at runtime (never vendored), normalises
question text (whitespace-collapsed, trailing-space-stripped), and matches by
exact normalised string. Writes results/rounds/round4/QUESTION_PROVENANCE.json
with counts, per-set overlap ids, and the sha256 of each fetched file.

Stdlib only. Usage: python3 tools/verify_question_provenance.py
"""
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "rounds" / "round4" / "QUESTION_PROVENANCE.json"

SOURCES = {
    "gsm8k_test": "https://raw.githubusercontent.com/openai/grade-school-math/"
                  "master/grade_school_math/data/test.jsonl",
    "gsm8k_train": "https://raw.githubusercontent.com/openai/grade-school-math/"
                   "master/grade_school_math/data/train.jsonl",
}

OUR_SETS = [
    "examples/gsm8k40.json",
    "examples/heldout40.json",
    "examples/heldout-batch2-160.json",
]


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "gsm8k-self-evolve/verify"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read()


def norm(s: str) -> str:
    return " ".join(str(s).split()).strip()


def parse_jsonl(raw: bytes) -> list:
    return [json.loads(ln) for ln in raw.decode("utf-8").splitlines() if ln.strip()]


def main() -> None:
    fetched = {}
    for key, url in SOURCES.items():
        raw = get(url)
        rows = parse_jsonl(raw)
        fetched[key] = {
            "url": url,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "n": len(rows),
            "questions": {norm(r["question"]) for r in rows},
        }
        print("fetched %-12s n=%-5d sha256=%s…" % (key, len(rows), fetched[key]["sha256"][:12]))

    report = {"sources": {k: {kk: vv for kk, vv in v.items() if kk != "questions"}
                          for k, v in fetched.items()},
              "sets": {}}

    for rel in OUR_SETS:
        data = json.loads((ROOT / rel).read_text(encoding="utf-8"))
        cases = data["cases"]
        qs = {c["id"]: norm(c["input"]) for c in cases}
        in_test = [i for i, q in qs.items() if q in fetched["gsm8k_test"]["questions"]]
        in_train = [i for i, q in qs.items() if q in fetched["gsm8k_train"]["questions"]]
        report["sets"][rel] = {
            "n": len(cases),
            "in_gsm8k_test": len(in_test),
            "in_gsm8k_train": len(in_train),
            "unmatched": len(cases) - len(in_test) - len(in_train),
            "in_gsm8k_test_ids": sorted(in_test)[:10],
            "in_gsm8k_train_ids": sorted(in_train)[:10],
        }
        s = report["sets"][rel]
        print("%-34s n=%-4d in_test=%-4d in_train=%-3d unmatched=%-3d"
              % (rel, s["n"], s["in_gsm8k_test"], s["in_gsm8k_train"], s["unmatched"]))

    # ---- position distribution: is the subset spread or clustered? ----
    # A subset that clusters (e.g. "first N of the file") would indicate a
    # selection bias; a spread subset is consistent with uniform sampling.
    order = {q: i for i, q in enumerate(
        [norm(r["question"]) for r in parse_jsonl(
            get(SOURCES["gsm8k_test"]))])}
    n_official = len(order)
    positions = []
    for rel in OUR_SETS:
        for c in json.loads((ROOT / rel).read_text(encoding="utf-8"))["cases"]:
            positions.append(order[norm(c["input"])])
    positions.sort()
    half = n_official // 2
    report["position_check"] = {
        "n_official_test": n_official,
        "n_matched": len(positions),
        "min": positions[0], "max": positions[-1],
        "mean": sum(positions) / len(positions),
        "mean_if_uniform": (n_official - 1) / 2,
        "shifted_from_uniform": abs(sum(positions) / len(positions) - (n_official - 1) / 2),
        "quartiles": [positions[int(len(positions) * p)] for p in (0.25, 0.5, 0.75)],
        "in_first_half": sum(1 for p in positions if p < half),
        "in_second_half": sum(1 for p in positions if p >= half),
        "adjacent_gaps_gt_1": sum(1 for a, b in zip(positions, positions[1:]) if b - a > 1),
        "interpretation": ("spread across the split (no clustering bias)"
                           if abs(sum(positions) / len(positions) - (n_official - 1) / 2)
                           < 0.1 * n_official else "CLUSTERED - check selection"),
    }
    pc = report["position_check"]
    print("positions: min=%(min)d max=%(max)d mean=%(mean).1f (uniform %(mean_if_uniform).1f) "
          "quartiles=%(quartiles)s halves=%(in_first_half)d/%(in_second_half)d -> %(interpretation)s"
          % pc)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("\nwrote", OUT.relative_to(ROOT))

    # verdict
    total = sum(s["n"] for s in report["sets"].values())
    t_total = sum(s["in_gsm8k_test"] for s in report["sets"].values())
    tr_total = sum(s["in_gsm8k_train"] for s in report["sets"].values())
    print("\nVERDICT: %d/%d questions match official GSM8K test; %d match GSM8K train (contamination)."
          % (t_total, total, tr_total))
    if tr_total:
        print("WARNING: train-overlap detected -> contaminated items must be disclosed/excluded.")
        sys.exit(2)


if __name__ == "__main__":
    main()