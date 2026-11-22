import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import report_ability as ra  # noqa: E402


def _write(p, rows):
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                 encoding="utf-8")


def _setup(tmp_path, heldout, sft, dpo):
    h = tmp_path / "heldout.jsonl"
    s = tmp_path / "gen_sft.json"
    d = tmp_path / "gen_dpo.json"
    _write(h, heldout)
    s.write_text(json.dumps(sft, ensure_ascii=False), encoding="utf-8")
    d.write_text(json.dumps(dpo, ensure_ascii=False), encoding="utf-8")
    return h, s, d


def test_report_scores_both_arms_and_labels_gain(tmp_path):
    heldout = [{"id": "s1", "prompt": "p1", "answer": 3},
               {"id": "s2", "prompt": "p2", "answer": 7}]
    sft = [{"id": "s1", "answer": 3, "text": "Answer: 3"},
           {"id": "s2", "answer": 7, "text": "Answer: 5"}]
    dpo = [{"id": "s1", "answer": 3, "text": "Answer: 3"},
           {"id": "s2", "answer": 7, "text": "Answer: 7"}]
    h, s, d = _setup(tmp_path, heldout, sft, dpo)
    rep = ra.build_report(str(h), str(s), str(d), min_delta=0.05)
    assert rep["base"]["passed"] == 1 and rep["adapter"]["passed"] == 2
    assert rep["base"]["accuracy"] == 0.5
    assert rep["adapter"]["accuracy"] == 1.0
    assert rep["verdict"]["delta"] == 0.5
    assert rep["verdict"]["label"] == "GAIN"


def test_missing_id_fails_closed(tmp_path):
    heldout = [{"id": "s1", "prompt": "p1", "answer": 3},
               {"id": "s2", "prompt": "p2", "answer": 7}]
    sft = [{"id": "s1", "answer": 3, "text": "Answer: 3"}]
    dpo = [{"id": "s1", "answer": 3, "text": "Answer: 3"},
           {"id": "s2", "answer": 7, "text": "Answer: 7"}]
    h, s, d = _setup(tmp_path, heldout, sft, dpo)
    with pytest.raises(ValueError):
        ra.build_report(str(h), str(s), str(d))


def test_no_gain_label_when_delta_below_threshold(tmp_path):
    heldout = [{"id": "s1", "prompt": "p1", "answer": 3},
               {"id": "s2", "prompt": "p2", "answer": 7}]
    sft = [{"id": "s1", "answer": 3, "text": "Answer: 3"},
           {"id": "s2", "answer": 7, "text": "Answer: 5"}]
    dpo = [{"id": "s1", "answer": 3, "text": "Answer: 3"},
           {"id": "s2", "answer": 7, "text": "Answer: 5"}]
    h, s, d = _setup(tmp_path, heldout, sft, dpo)
    rep = ra.build_report(str(h), str(s), str(d), min_delta=0.05)
    assert rep["verdict"]["label"] == "NO_GAIN"


def test_render_md_contains_verdict_and_counts(tmp_path):
    heldout = [{"id": "s1", "prompt": "p1", "answer": 3}]
    sft = [{"id": "s1", "answer": 3, "text": "Answer: 9"}]
    dpo = [{"id": "s1", "answer": 3, "text": "Answer: 3"}]
    h, s, d = _setup(tmp_path, heldout, sft, dpo)
    rep = ra.build_report(str(h), str(s), str(d), min_delta=0.05)
    md = ra.render_md(rep)
    assert "GAIN" in md
    assert "0.0" in md and "1.0" in md
