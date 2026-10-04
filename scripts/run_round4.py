"""Generic paired runner for Round-4 (tracks A+C, reusable for transfer).

Usage: python3 scripts/run_round4.py --dataset <path.json> --policies a,b,c
  --out <path.json> [--limit N] [--resume]
Dataset schema: {"cases": [{"id","input","expected"}]}. Each (policy, case) runs
once via the evaluator subprocess (EVO_MODEL from env, default qwen2.5:7b).
Pairs: every unordered policy pair -> better/worse/mcnemar p/gain/latency ratio,
ledger asserted in code. --resume skips (policy,id) already in out file.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from evokit.stats import ledger_ok, mcnemar_two_sided


def _rel_to_repo(path: str) -> str:
    """Repo-relative dataset label for result metadata.

    Callers pass an absolute path (``run_transfer_cotzero.py`` builds
    ``ROOT / results / ...``), which would embed a personal home directory into a
    committed results file and trip tools/check_publish.py gate 5. Committed transfer
    files already store the relative form (``results/rounds/round4/inputs/svamp.json``),
    so this normalises to it and falls back to the basename when the path is outside
    the repo (no silent mangling).
    """
    try:
        return Path(path).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return Path(path).name


def run_one(policy: str, prompt_file: str | None, question: str, expected: float,
            model: str, subprocess_timeout: float = 150,
            env_extra: dict | None = None) -> dict:
    """One evaluator cell.  Both extra arguments are opt-in and transport-related:
    ``subprocess_timeout`` must cover the worst-case inner request budget of a remote
    27B backbone (or a retried slow call is guillotined as a failure), and
    ``env_extra`` carries the resolved transport to the child explicitly instead of
    mutating the parent's environment.  Defaults keep every existing caller identical."""

    cand = {"answer_policy": policy}
    if prompt_file:
        cand["prompt_file"] = prompt_file
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(cand, f)
        cand_path = f.name
    env = dict(os.environ, EVO_MODEL=model, EVO_CANDIDATE=cand_path,
               EVO_INPUT=json.dumps(question), EVO_EXPECTED=json.dumps(expected),
               **(env_extra or {}))
    try:
        p = subprocess.run(["python3", str(ROOT / "examples" / "gsm8k_evaluator.py")],
                           capture_output=True, text=True, env=env, cwd=str(ROOT),
                           timeout=subprocess_timeout)
        out = json.loads(p.stdout)
        details = out.get("details") or {}
        res = {"passed": bool(out["passed"]),
               "latency": float(out.get("latency_s", 0.0)),
               "parsed": details.get("parsed")}
        # Propagate the evaluator's transport error (details.error, e.g.
        # "TransportError") so callers can separate "the model answered wrong"
        # (data) from "the call never reached the model" (NOT data).  Additive
        # only: without details.error the returned keys/defaults are exactly the
        # pre-fix shape, so callers that ignore "error" are unaffected
        # (run_paired_incremental.compute and run_round4.main read only
        # passed/latency/parsed).
        err = details.get("error")
        if err:
            res["error"] = str(err)
        return res
    except Exception as exc:
        return {"passed": False, "latency": 0.0, "parsed": None,
                "error": type(exc).__name__}
    finally:
        Path(cand_path).unlink(missing_ok=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--policies", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--model", default=os.environ.get("EVO_MODEL", "qwen2.5:7b"))
    a = ap.parse_args()
    policies = a.policies.split(",")
    cases = json.load(Path(a.dataset).open(encoding="utf-8"))["cases"]
    if a.limit:
        cases = cases[: a.limit]
    out_path = Path(a.out)
    done: dict = {}
    if a.resume and out_path.exists():
        done = json.load(out_path.open(encoding="utf-8")).get("details", {})
    details: dict = {k: v for k, v in done.items()}
    for c in cases:
        qid = c["id"]
        row = details.get(qid, {})
        for pol in policies:
            if pol not in row:
                row[pol] = run_one(pol, None, c["input"], float(c["expected"]), a.model)
                print(json.dumps({"id": qid, "policy": pol, "passed": row[pol]["passed"]}),
                      flush=True)
        details[qid] = row
    # ---- fail-closed: transport failure is NOT data ------------------------------
    # run_one() records a transport failure as passed=False, which is the right shape
    # for the incremental consumer (it just skips that cell) but is WRONG for an
    # aggregate: a call that never reached the model is indistinguishable from a wrong
    # answer once passed=False, so a run where ollama dropped mid-stream silently
    # becomes "the policy is terrible". This exact failure invalidated the round-5
    # Qwen3.8-27B arm (see results/rounds/round5/proposer-arm-qwen38-27b.QUARANTINE.md)
    # and is registered in results/NONCITABLE.json.
    #
    # So: refuse to emit totals/pairs at all when any cell carries an error. The partial
    # details are still written, so --resume can retry just the failed cells.
    errors = {(qid, pol): row[pol]["error"] for qid, row in details.items()
              for pol in policies if pol in row and row[pol].get("error")}
    # meta.dataset must be repo-relative: a personal absolute path would fail
    # tools/check_publish.py gate 5 and must never be committed.
    ds_rel = _rel_to_repo(a.dataset)
    if errors:
        by_kind: dict[str, int] = {}
        for (_, _), e in errors.items():
            by_kind[e] = by_kind.get(e, 0) + 1
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps({
            "schema_version": 2, "INCOMPLETE": True,
            "why": "transport failures present; totals/pairs intentionally not computed",
            "error_counts": by_kind, "meta": {"dataset": ds_rel, "policies": policies,
                                              "model": a.model, "n": len(details)},
            "details": details}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        raise SystemExit(
            "REFUSING TO AGGREGATE: %d cell(s) carry a transport error %s.\n"
            "A call that never reached the model is not a wrong answer.\n"
            "Partial details were written to %s; re-run with --resume to retry them."
            % (len(errors), by_kind, out_path))
    totals = {pol: sum(1 for qid in details for _ in [details[qid][pol]]
                       if details[qid][pol]["passed"]) for pol in policies}
    n = len(details)
    lat = {pol: sum(details[q][pol]["latency"] for q in details) / max(n, 1)
           for pol in policies}
    pairs = {}
    for x, y in combinations(policies, 2):
        better = sum(1 for q in details
                     if details[q][y]["passed"] and not details[q][x]["passed"])
        worse = sum(1 for q in details
                    if details[q][x]["passed"] and not details[q][y]["passed"])
        assert ledger_ok(totals[x], totals[y], better, worse), (x, y)
        pairs["%s_vs_%s" % (x, y)] = {
            "better": better, "worse": worse,
            "p": mcnemar_two_sided(better, worse),
            "gain": (totals[y] - totals[x]) / n if n else 0.0,
            "ledger_ok": True, "lat_x": lat[x], "lat_y": lat[y],
            "lat_ratio": (lat[y] / lat[x]) if lat[x] else None}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({
        "meta": {"dataset": ds_rel, "policies": policies, "model": a.model, "n": n},
        "totals": totals, "pairs": pairs, "details": details},
        ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("wrote", out_path, totals)


if __name__ == "__main__":
    main()
