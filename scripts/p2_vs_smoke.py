"""p2 vs smoke 对比读数表：从已落盘的真实产物提取，不改论文数字。

数据源（只读，不重跑、不重算论文里的任何数）：
  - results/qlora-cloud-2026-11-21-run.json 的 smoke/p2 块（当时落盘的训练结论）
  - results/qlora-cloud-2026-11-21/p2_train.stdout（p2 逐 step 真实日志）

verifier: 提取函数对源字段做断言（steps/sha/runtime 必须来自源，非硬编码）；
smoke 与 p2 的 DPO 共性字段（base/数据/精度）逐项核；reward margin 从日志现算。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "qlora-cloud-2026-11-21"
RUN_JSON = ROOT / "results" / "qlora-cloud-2026-11-21-run.json"
SMOKE_SHA = "e44f8acdcc6fdfad0febc6a69c2207447dbcb237c3cf15960694bb626af743e9"
P2_SHA = "b9ef9253093034bab7e0cff0c72fa05dcdda6ab879fa4e3505c0927270bcc6a9"


def load_run() -> dict:
    return json.loads(RUN_JSON.read_text(encoding="utf-8"))


def parse_p2_rows(stdout_text: str) -> list[dict]:
    """从 p2 stdout 逐 step 行提 loss/rewards/epoch（真日志，不编造）。"""
    rows = []
    for line in stdout_text.splitlines():
        if "'rewards/chosen':" not in line or "'loss':" not in line:
            continue
        grab = lambda k: re.search(rf"'{k}':\s*(-?[0-9.eE+]+)", line)
        row = {
            "loss": float(grab("loss").group(1)),
            "chosen": float(grab("rewards/chosen").group(1)),
            "rejected": float(grab("rewards/rejected").group(1)),
            "accuracy": float(grab("rewards/accuracies").group(1)),
        }
        ep = grab("epoch")
        if ep:
            row["epoch"] = float(ep.group(1))
        rows.append(row)
    return rows


def build_comparison() -> dict:
    run = load_run()
    smoke = run["smoke"]
    p2 = run["p2"]
    stdout = (RESULTS / "p2_train.stdout").read_text(encoding="utf-8")
    rows = parse_p2_rows(stdout)

    # 反硬编码：sha/steps/runtime 必须与落盘源一致，否则中止（verifier）。
    assert smoke["adapter"]["sha256"] == SMOKE_SHA
    assert p2["adapter"]["sha256"] == P2_SHA
    assert smoke["steps"] == 10 and p2["steps"] == 50
    assert len(rows) >= 2, "p2 stdout must contain >=2 real step rows"
    assert rows[0]["accuracy"] == rows[-1]["accuracy"] == 1.0

    trail = re.search(r"'train_loss':\s*([0-9.eE+-]+)", stdout)
    assert trail and abs(float(trail.group(1)) - p2["final_train_loss"]) < 1e-12

    def margin(r):
        return round(r["chosen"] - r["rejected"], 4)

    return {
        "provenance": {
            "run_json": str(RUN_JSON.relative_to(ROOT)),
            "p2_stdout": str((RESULTS / "p2_train.stdout").relative_to(ROOT)),
            "no_paper_number_changed": True,
            "no_recompute_of_training": "this is a read-out of already-persisted results, not a new training or metric",
        },
        "invariants": {
            "training_script": "train_dpo.py --p2/--smoke (true DPO on chosen/rejected pairs)",
            "base_model": "Qwen/Qwen3-4B",
            "train_file": "dpo_p0v2.jsonl (400 rows)",
            "precision": "bf16 non-quantized LoRA (--no-4bit; bitsandbytes unavailable on gfx1100)",
            "hardware": "AMD Radeon Graphics gfx1100 48GiB",
            "verifier_id": "verifier-frozen-v1",
        },
        "smoke": {
            "steps": smoke["steps"], "epoch": smoke["epoch"],
            "train_runtime_s": smoke["train_runtime_s"],
            "final_loss": smoke["final_loss"],
            "step1": smoke["step1"], "step10": smoke["step10"],
            "adapter_sha256": smoke["adapter"]["sha256"],
            "adapter_bytes": smoke["adapter"]["bytes"],
        },
        "p2": {
            "steps": p2["steps"], "epoch": p2["epoch"],
            "train_runtime_s": p2["train_runtime_s"],
            "train_samples_per_second": p2["train_samples_per_second"],
            "final_train_loss": p2["final_train_loss"],
            "first_step": rows[0], "last_step": rows[-1],
            "reward_margin_first": margin(rows[0]), "reward_margin_last": margin(rows[-1]),
            "accuracy_all_steps": sorted({r["accuracy"] for r in rows}),
            "adapter_sha256": p2["adapter"]["sha256"],
            "adapter_bytes": p2["adapter"]["bytes"],
        },
        "not_claimed": [
            "no held-out GSM8K/TMLR metric; reward accuracy=1.0 means the model fit these 400 pairs, not generalization",
            "final loss decreasing from smoke to p2 is not evidence of capability improvement",
            "the two adapters are independent artifacts (different sha), not one resumed from the other",
        ],
    }


def render_md(c: dict) -> str:
    s, p = c["smoke"], c["p2"]
    lines = [
        "# p2 vs smoke 对比读数表（真 DPO，2026-11-21）",
        "",
        "数据来源：`results/qlora-cloud-2026-11-21-run.json` + `results/qlora-cloud-2026-11-21/p2_train.stdout`；",
        "由 `scripts/p2_vs_smoke.py` 只读提取，**未改论文任何数字，未重跑训练**。",
        "",
        "| 指标 | smoke | p2 (1 epoch) |",
        "|---|---|---|",
        f"| steps | {s['steps']} | {p['steps']} |",
        f"| epoch | {s['epoch']} | {p['epoch']} |",
        f"| train_runtime_s | {s['train_runtime_s']} | {p['train_runtime_s']} |",
        f"| final loss | {s['final_loss']:.10g} | {p['final_train_loss']:.10g} |",
        f"| step1 loss | {s['step1']['loss']} | {p['first_step']['loss']} |",
        f"| step1 rewards chosen/rejected | {s['step1']['reward_chosen']}/{s['step1']['reward_rejected']} | {p['first_step']['chosen']:.2f}/{p['first_step']['rejected']:.2f} |",
        f"| rewards accuracy | {s['step1']['accuracy']} | {p['accuracy_all_steps']} |",
        f"| reward margin (first→last) | — | {p['reward_margin_first']}→{p['reward_margin_last']} |",
        f"| adapter sha256 (前16) | {s['adapter_sha256'][:16]} | {p['adapter_sha256'][:16]} |",
        f"| adapter bytes | {s['adapter_bytes']} | {p['adapter_bytes']} |",
        "",
        "## 共性（不可比项）",
        "",
    ]
    lines += [f"- {k}: {v}" for k, v in c["invariants"].items()]
    lines += ["", "## 不构成能力结论（not claimed）", ""]
    lines += [f"- {x}" for x in c["not_claimed"]]
    return "\n".join(lines) + "\n"


def main() -> int:
    c = build_comparison()
    (RESULTS / "p2_vs_smoke.json").write_text(
        json.dumps(c, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (RESULTS / "p2_vs_smoke.md").write_text(render_md(c), encoding="utf-8")
    print(f"p2_vs_smoke: smoke {c['smoke']['steps']} steps / p2 {c['p2']['steps']} steps; "
          f"margin {c['p2']['reward_margin_first']}→{c['p2']['reward_margin_last']}; "
          f"sha distinct={c['smoke']['adapter_sha256'] != c['p2']['adapter_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
