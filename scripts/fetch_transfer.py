"""Fetch transfer sets at runtime (never vendored: ASDiv is CC-BY-NC-4.0).

Writes results/rounds/round4/inputs/{svamp,multiarith,asdiv}.json in
{"cases": [{"id","input","expected"}]} schema + INPUTS.json with URLs, byte
sha256, and counts. Stdlib only.
"""
import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDIR = ROOT / "results" / "rounds" / "round4" / "inputs"

SOURCES = {
    "svamp": "https://raw.githubusercontent.com/arkilpatel/SVAMP/main/SVAMP.json",
    "multiarith": "https://huggingface.co/datasets/ChilleD/MultiArith/resolve/main/test.json",
}


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "gsm8k-self-evolve/round4"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def num_leading(s: str) -> float:
    import re
    m = re.search(r"-?[\d,]*\.?\d+", str(s).replace(",", ""))
    assert m, s
    return float(m.group(0))


def main() -> None:
    INDIR.mkdir(parents=True, exist_ok=True)
    meta = {}
    raw = get(SOURCES["svamp"])
    d = json.loads(raw)
    assert isinstance(d, list) and len(d) == 1000, len(d)
    cases = [{"id": r["ID"], "input": r["Body"].strip() + " " + r["Question"].strip(),
              "expected": float(r["Answer"])} for r in d]
    (INDIR / "svamp.json").write_text(json.dumps({"cases": cases}) + "\n", encoding="utf-8")
    meta["svamp"] = {"url": SOURCES["svamp"], "sha256": hashlib.sha256(raw).hexdigest(), "n": len(cases)}

    raw = get(SOURCES["multiarith"])
    d = json.loads(raw)
    assert isinstance(d, list) and len(d) == 180, len(d)
    cases = [{"id": "ma-%03d" % i, "input": r["question"].strip(),
              "expected": float(r["final_ans"])} for i, r in enumerate(d)]
    (INDIR / "multiarith.json").write_text(json.dumps({"cases": cases}) + "\n", encoding="utf-8")
    meta["multiarith"] = {"url": SOURCES["multiarith"], "sha256": hashlib.sha256(raw).hexdigest(), "n": len(cases)}

    rows = []
    offset, total = 0, None
    while True:
        u = ("https://datasets-server.huggingface.co/rows?dataset=EleutherAI/asdiv"
             "&config=asdiv&split=validation&offset=%d&length=100" % offset)
        d = json.loads(get(u))
        total = d["num_rows_total"]
        if not d["rows"]:
            break
        rows.extend(r["row"] for r in d["rows"])
        offset += 100
    assert total == 2305 and len(rows) == 2305, (total, len(rows))
    cases = [{"id": "asdiv-%04d" % i,
              "input": (r["body"].strip() + " " + r["question"].strip()),
              "expected": num_leading(r["answer"])} for i, r in enumerate(rows)]
    (INDIR / "asdiv.json").write_text(json.dumps({"cases": cases}) + "\n", encoding="utf-8")
    meta["asdiv"] = {"api": "datasets-server rows EleutherAI/asdiv asdiv/validation",
                     "n": len(cases),
                     "sha256": hashlib.sha256(
                         json.dumps(cases, sort_keys=True).encode()).hexdigest()}
    (INDIR / "INPUTS.json").write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
