#!/usr/bin/env python3
"""Regenerate the held-out accuracy figure from the raw result files.

Every number in the figure is read from results/*.json in this repository; this
script performs no model calls and invents nothing. Run:

    python3 scripts/make_figures.py

Outputs:
    figures/heldout_accuracy.png   (stage-wise accuracy with 95% Wilson intervals)
    figures/HELDOUT.md             (the same numbers as a table, for the README)
"""
from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "figures"

# Every stage is a SUM of the two held-out batches that were actually run:
# batch 1 = 40 questions (results/heldout-round2-result.json), batch 2 = 160
# questions (results/heldout-batch2-result.json). The 40-question seed row comes
# from the earlier file, which scored only the seed and round-1 policies.
BATCHES = {
    "direct": [("results/heldout-result.json", "direct-baseline")],
    "concise-reason": [("results/heldout-round2-result.json", "concise_reason"),
                       ("results/heldout-batch2-result.json", "concise_reason")],
    "step-calc": [("results/heldout-round2-result.json", "step_calc"),
                  ("results/heldout-batch2-result.json", "step_calc")],
}
STAGES = [
    ("seed: direct", "direct"),
    ("round 1: concise-reason", "concise-reason"),
    ("round 2: step-calc (stable)", "step-calc"),
]


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval -- correct for proportions near 1.0."""
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, centre - half), min(1.0, centre + half)


def load(stage: tuple[str, str]) -> dict:
    label, policy = stage
    passed = total = 0
    sources = []
    for rel, key in BATCHES[policy]:
        cell = json.loads((ROOT / rel).read_text(encoding="utf-8"))[key]
        passed += int(cell["passed"])
        total += int(cell["total"])
        sources.append(f"{rel}#{key}")
    lo, hi = wilson(passed, total)
    return {"label": label, "policy": policy, "sources": sources,
            "passed": passed, "total": total, "score": passed / total,
            "lo": lo, "hi": hi}


def main() -> None:
    rows = [load(s) for s in STAGES]
    OUT.mkdir(exist_ok=True)

    json.dump(rows, (OUT / "heldout_numbers.json").open("w"), indent=1)

    lines = ["| stage | sources (raw files) | passed | n | score | 95% Wilson CI |",
             "|---|---|---|---|---|---|"]
    for r in rows:
        src = ", ".join(f"`{s}`" for s in r["sources"])
        lines.append(f"| {r['label']} | {src} | {r['passed']} | {r['total']} | "
                     f"{r['score']:.3f} | [{r['lo']:.3f}, {r['hi']:.3f}] |")
    (OUT / "HELDOUT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed; wrote figures/HELDOUT.md only")
        print("\n".join(lines))
        return

    fig, ax = plt.subplots(figsize=(8.2, 4.2), dpi=160)
    xs = list(range(len(rows)))
    ys = [r["score"] for r in rows]
    err = [[r["score"] - r["lo"] for r in rows], [r["hi"] - r["score"] for r in rows]]
    ax.errorbar(xs, ys, yerr=err, fmt="o", color="#1f6f5f", ecolor="#9ab5ae",
                capsize=4, markersize=6, linewidth=1.2, zorder=3)
    for x, r in zip(xs, rows):
        ax.annotate(f"{r['passed']}/{r['total']}", (x, r["score"]),
                    textcoords="offset points", xytext=(0, 9),
                    ha="center", fontsize=8, color="#33413d")
    ax.plot([1, 2], [rows[1]["score"], rows[2]["score"]], color="#c4552d", linewidth=1.0,
            linestyle="--", zorder=2)  # the one paired contrast that has a p-value
    ax.set_xticks(xs)
    ax.set_xticklabels([r["label"].replace(": ", ":\n") for r in rows], fontsize=7.5)
    ax.set_ylim(0, 1.02)
    ax.set_ylabel("held-out accuracy")
    ax.set_title("GSM8K self-evolve: each stage, with 95% Wilson intervals\n"
                 "(numbers read from results/*.json; dashed = round-2 paired contrast)",
                 fontsize=9)
    ax.grid(axis="y", color="#e3e8e6", linewidth=0.8)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "heldout_accuracy.png")
    print("wrote figures/heldout_accuracy.png and figures/HELDOUT.md")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
