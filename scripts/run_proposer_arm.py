"""Round-5 Task 6 — OPTIONAL proposer-substitution arm (runner only).

What this arm is
----------------
`paper/PLAN-NOVELTY.md` Task 6 asks for the only new-generation experiment of
round 5: substitute the repository's own evolve-loop proposer with an
alternative, TEXT-CRITIQUE proposer (TextGrad / Reflexion style) and show that
the promotion gate is *decoupled* from whichever proposer produced the
candidate.  The alternative proposer is reused, never reinvented:

  * proposer      : `scripts/textgrad_rewrite.py` — TextGrad-style
                    (textual loss -> textual gradient -> instruction rewrite)
                    loop, train-40 only, `EVO_MODEL=qwen2.5:7b`, product frozen
                    to disk.
  * its product   : `examples/prompts/textgrad-prompt.txt` — the frozen rewritten
                    instruction (header: rewritten_from=step-calc,
                    oracle=train-only, frozen=true).
  * product arm   : evaluator policy `textgrad` (`examples/gsm8k_evaluator.py`
                    `textgrad` branch; prompt_file, ONE model call per question).
  * headline pair : the product (`textgrad`) vs `cot-zero`, evaluated here on
                    `examples/heldout40.json` with `qwen2.5:7b`.

The frozen product is consumed read-only (its SHA-256 is recorded in the output);
this runner never re-runs the proposer loop, because that would rewrite a
committed, frozen artefact.

Panel derivation (stated explicitly, not invented)
--------------------------------------------------
`PREREG-round5.md` §6 caps this optional arm at 400 calls written as
"`heldout40` × 5 policies × 2" but does NOT name the five policies.  Resolved
here as the most defensible reading, with the alternative disclosed in the task
report (`.superpowers/sdd/plan-novelty/task-6-report.md`):

  Track A's committed heldout40 panel on the pinned model (`qwen2.5:7b`) is
  exactly four policies — `results/rounds/round4/trackA-heldout40.json`
  meta.policies = [direct, step-calc, cot-zero, few-shot].  Adding the ONE
  substituted proposer product gives exactly five policies on the SAME model and
  the SAME dataset, so every arm is comparable with committed Track-A data:

      PANEL = (direct, step-calc, cot-zero, few-shot, textgrad)

  The product is last, so `run_paired_incremental`'s challenger-last convention
  keys the headline pair `cot-zero_vs_textgrad`, where y = challenger
  (`better` = challenger-only, `gain` = (total_challenger - total_incumbent)/n).
  An orientation-explicit `headline` block restates it in the §1.1 convention
  (`chal_policy` = textgrad, `inc_policy` = cot-zero) so no signed gain can be
  transcribed without its orientation.

  Alternative reading (disclosed, NOT implemented): Track C's five-policy panel
  (`qwen2:7b`, a different model tag) with the product substituted for the policy
  it was rewritten from (`step-calc`).  Both readings keep the headline pair
  (product vs cot-zero); the reading implemented here is the one whose four
  comparators all sit on the pinned model and dataset and already carry committed
  run data.

Budget guard (fail loudly, enforced in code)
--------------------------------------------
`CALL_CAP_PREREG = 400` (prereg §6).  `planned_calls = n_questions × n_policies
× repeats` is computed and PRINTED before any model call; if it exceeds the cap
the runner exits non-zero WITHOUT calling the model.  Every recorded cell is
exactly one evaluator call, so the cap is enforced over the same unit the budget
is stated in.  Evaluator policies with a variable per-question call count
(`reflect-retry` makes 2-3 calls) are refused by default: they would make the
400-call cap unverifiable against a fixed cell grid.

Resumability
------------
The output file is rewritten after EVERY single call (same discipline as
`scripts/run_paired_incremental.py`), so an interrupted long spend loses at most
one call and a re-run continues where it stopped.  A resumed file whose
dataset / model / policies no longer match the current invocation is refused
(configuration drift) rather than silently merged.

Output
------
`results/rounds/round5/proposer-arm-<model-slug>.json` — a superset of
`run_paired_incremental`'s shape (`meta` / `totals` / `pairs` / `details`, so the
existing summariser and analysis tools work on it) plus `repeats`
(replicate detail + per-policy agreement) and the orientation-explicit
`headline` block.

Usage
-----
  python3 scripts/run_proposer_arm.py                     # full 400-call arm
  python3 scripts/run_proposer_arm.py --dry-run           # print the plan only
  python3 scripts/run_proposer_arm.py --limit 2           # smoke test (20 calls)
  python3 scripts/run_proposer_arm.py --repeats 1         # 200-call variant

Transport (round-5 addition — the ONLY thing this runner gained)
----------------------------------------------------------------
The arm's panel, prompts, scoring, budget guard, incremental saving and output
shape are frozen.  What was added is a second model transport, selectable at the
launch:

  * default (unchanged): local ollama at ``EVO_OLLAMA_URL`` (``/api/generate``).
  * new: OpenAI-compatible server, selected with ``--openai-base URL`` or
    ``EVO_OPENAI_BASE`` — ``POST {base}/v1/chat/completions`` with
    ``{"model", "messages":[{"role":"user","content":…}], "max_tokens":N,
    "temperature":0}``; the answer is read from ``choices[0].message.content``
    and ``usage.completion_tokens``.

The new backend exists for the new-generation backbone ``Qwen3.8-27B-AWQ``,
served by vLLM under model id ``qwen3.8-27b`` (the default for this backend;
``--model`` overrides it).  A 27B at ~8 tokens/s needs minutes per call, so
``--request-timeout`` defaults to 900 s and transient failures (connection error
/ 5xx) are retried a bounded number of times (``--request-retries``, default 2)
with logged exponential backoff.  A retry is a transport event, not an arm call:
the budget is counted in completed cells, so a retry can never consume it.

Backend provenance (kind, base URL, served model id, timeout) is written into
``meta.backend``, and a resumed run refuses to continue when the backend, its
base URL or the served model id differs from the recorded one — the same
config-drift discipline already applied to dataset/model/policies/repeats.
"""
import argparse
import hashlib
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from evokit.stats import ledger_ok, mcnemar_two_sided  # noqa: E402
from llm_backends import (  # noqa: E402
    OLLAMA, OPENAI, OPENAI_BASE_ENV, REQUEST_TIMEOUT_ENV, BackendConfig,
    DEFAULT_MAX_TOKENS, DEFAULT_OLLAMA_REQUEST_TIMEOUT, DEFAULT_OPENAI_MODEL,
    DEFAULT_REQUEST_RETRIES, DEFAULT_REQUEST_TIMEOUT, DEFAULT_RETRY_BACKOFF,
    models_url, normalize_base,
    openai_chat,  # re-exported: tests drive the request/parse path through it
    preflight_openai,
    TransportError,  # re-exported: tests assert the timeout/no-retry contract
)
from run_round4 import run_one  # noqa: E402
from run_paired_incremental import compute  # noqa: E402

# --- prereg-pinned budget (PREREG-round5.md §6) -----------------------------
CALL_CAP_PREREG = 400

# --- arm definition ---------------------------------------------------------
DEFAULT_MODEL = os.environ.get("EVO_MODEL", "qwen2.5:7b")
# The new backend's default served model id (vLLM): Qwen3.8-27B-AWQ -> qwen3.8-27b.
NEW_BACKBONE_MODEL = DEFAULT_OPENAI_MODEL
DEFAULT_DATASET = ROOT / "examples" / "heldout40.json"
PROPOSER_SCRIPT = "scripts/textgrad_rewrite.py"
PROPOSER_PRODUCT_FILE = ROOT / "examples" / "prompts" / "textgrad-prompt.txt"
PRODUCT_POLICY = "textgrad"
HEADLINE_CHALLENGER = PRODUCT_POLICY
HEADLINE_INCUMBENT = "cot-zero"

# Track A's committed same-model heldout40 panel (4 policies) + the substituted
# text-critique proposer product = the prereg's 5 policies.
PANEL = ("direct", "step-calc", "cot-zero", "few-shot", PRODUCT_POLICY)

PANEL_DERIVATION = (
    "PREREG-round5.md §6 states the cap as 'heldout40 × 5 policies × 2' without "
    "naming the 5 policies. Resolved as: results/rounds/round4/trackA-heldout40.json "
    "meta.policies (=direct,step-calc,cot-zero,few-shot — the only committed "
    "4-policy heldout40 panel on the pinned model qwen2.5:7b) + the substituted "
    "text-critique proposer product ('textgrad') = 5 policies on the same model and "
    "dataset. Alternative reading (Track C's 5-policy panel on qwen2:7b with the "
    "product substituted for step-calc) is disclosed but not implemented. Headline "
    "pair = product (textgrad) vs cot-zero."
)

# Evaluator policies that spend more than one model call per question.
VARIABLE_CALL_POLICIES = {"reflect-retry"}


def die(code: int, msg: str) -> None:
    print("REFUSED: %s" % msg, file=sys.stderr, flush=True)
    sys.exit(code)


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def model_slug(model: str) -> str:
    """qwen2.5:7b -> qwen25-7b (matches results/rounds/round4/variance-qwen25-7b-*.json)."""
    return model.replace(":", "-").replace(".", "")


def resolve_ollama_url(explicit) -> str:
    raw = explicit or os.environ.get("EVO_OLLAMA_URL") or "http://127.0.0.1:11434/api/generate"
    if "/api/" not in raw:
        raw = raw.rstrip("/") + "/api/generate"
    return raw


def resolve_backend(a, model: str) -> BackendConfig:
    """Select the transport.  Ollama stays the default; an OpenAI-compatible base
    (``--openai-base`` or ``EVO_OPENAI_BASE``) selects the vLLM path.  Only the
    transport changes — the panel, prompts, scoring and budget guard are shared."""
    raw_base = a.openai_base or os.environ.get(OPENAI_BASE_ENV) or None
    backoff = float(DEFAULT_RETRY_BACKOFF if a.retry_backoff is None else a.retry_backoff)
    # --request-timeout wins; EVO_REQUEST_TIMEOUT (the evaluator's own knob, honoured
    # by the ollama path before this change) is the second source, then the default.
    env_timeout = os.environ.get(REQUEST_TIMEOUT_ENV)
    override = (float(a.request_timeout) if a.request_timeout is not None
                else (float(env_timeout) if env_timeout else None))
    if raw_base:
        return BackendConfig(
            kind=OPENAI, model=model,
            timeout=override if override is not None else float(DEFAULT_REQUEST_TIMEOUT),
            retries=int(DEFAULT_REQUEST_RETRIES if a.request_retries is None
                        else a.request_retries),
            max_tokens=int(DEFAULT_MAX_TOKENS if a.max_tokens is None else a.max_tokens),
            backoff_base=backoff,
            base_url=normalize_base(raw_base), base_arg=raw_base,
        )
    return BackendConfig(
        kind=OLLAMA, model=model, retries=0, max_tokens=0, backoff_base=backoff,
        # ollama keeps its frozen 90 s request default
        timeout=override if override is not None else float(DEFAULT_OLLAMA_REQUEST_TIMEOUT),
        ollama_url=resolve_ollama_url(a.ollama_url),
    )


def child_transport_env(cfg: BackendConfig) -> dict:
    """Transport for the evaluator subprocess (handed to run_one(env_extra=...)).

    Deliberately NOT ``os.environ``: the runner reads ``EVO_OPENAI_BASE``/``EVO_MODEL``
    from the operator, so writing them back would make a second invocation in the
    same process silently adopt the previous backend and defeat the resume guard.
    """
    return cfg.child_env()


def preflight_openai_or_die(cfg: BackendConfig) -> list:
    """Same job as the ollama preflight: protect the 400-call budget from a bad target."""
    probe = models_url(cfg.base_url)
    try:
        names = preflight_openai(cfg.base_url, timeout=30.0, retries=cfg.retries,
                                 backoff_base=cfg.backoff_base)
    except Exception as exc:  # noqa: BLE001 - preflight must report, not raise
        die(6, "openai-compatible server not reachable at %s (%s: %s); "
               "use --skip-preflight to bypass"
               % (probe, type(exc).__name__, exc))
    if cfg.model not in names:
        die(6, "model %r not served at %s; available: %s (use --skip-preflight to bypass)"
               % (cfg.model, probe, ", ".join(names) or "(none advertised)"))
    return names


def preflight(url: str, model: str) -> list:
    """Non-model reachability probe: protect the 400-call budget from a bad target."""
    tags_url = url.split("/api/")[0] + "/api/tags"
    try:
        with urllib.request.urlopen(tags_url, timeout=10) as resp:
            data = json.load(resp)
    except Exception as exc:  # noqa: BLE001 - preflight must report, not raise
        die(6, "ollama not reachable at %s (%s: %s); use --skip-preflight to bypass"
               % (tags_url, type(exc).__name__, exc))
    names = [m.get("name", "") for m in data.get("models", [])]
    if model not in names:
        die(6, "model %r not present at %s; available: %s (use --skip-preflight to bypass)"
               % (model, tags_url, ", ".join(names)))
    return names


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def proposer_provenance(url, cfg: BackendConfig) -> dict:
    if not PROPOSER_PRODUCT_FILE.exists():
        die(7, "proposer product %s missing; the frozen text-critique product must exist"
               % rel(PROPOSER_PRODUCT_FILE))
    raw = PROPOSER_PRODUCT_FILE.read_text(encoding="utf-8")
    header = raw.splitlines()[0] if raw.strip() else ""
    # The evaluator .format()s the file, so the stored header is brace-escaped.
    header_json = header.replace("{{", "{").replace("}}", "}")
    try:
        parsed = json.loads(header_json)
    except Exception:  # noqa: BLE001 - provenance is recorded, not fatal
        parsed = {"unparsed": header}
    return {
        "kind": "text-critique (TextGrad / Reflexion style)",
        "proposer_script": PROPOSER_SCRIPT,
        "product_policy": PRODUCT_POLICY,
        "product_file": rel(PROPOSER_PRODUCT_FILE),
        "product_sha256": sha256_file(PROPOSER_PRODUCT_FILE),
        "product_header": parsed,
        "product_file_stored_brace_escaped": "{{" in header,
        "evaluator": "examples/gsm8k_evaluator.py",
        # The frozen product was produced by the ollama proposer; the arm's own
        # evaluation transport is recorded separately in meta.backend.
        "ollama_url": url,
        "arm_backend": cfg.as_meta(),
        "regenerated_by_this_runner": False,
    }


def load_state(out: Path, args, policies, model, cfg: BackendConfig) -> dict:
    """Load a previous run's rows for resume; refuse configuration drift."""
    state = {r: {} for r in range(1, args.repeats + 1)}
    if not out.exists():
        return state
    try:
        doc = json.loads(out.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - corrupt file must not be silently merged
        die(8, "existing %s is not valid JSON (%s); move it aside to restart"
               % (out, type(exc).__name__))
    meta = doc.get("meta", {})
    stored_backend = meta.get("backend") or {}
    drift = {
        "dataset": (meta.get("dataset"), rel(args.dataset)),
        "model": (meta.get("model"), model),
        "policies": (meta.get("policies"), list(policies)),
        "repeats": (meta.get("repeats"), args.repeats),
        # Backend provenance drift (round-5 addition).  A file written before this
        # key existed has no meta.backend, so the check is skipped for it; the
        # ollama URL check below covers the legacy shape.
        "backend_kind": (stored_backend.get("kind"), cfg.kind),
        "backend_base_url": (stored_backend.get("base_url"), cfg.base_url),
        "backend_model_id": (stored_backend.get("served_model_id"), model),
        "ollama_url": ((meta.get("ollama_url"), cfg.ollama_url)
                       if cfg.kind == OLLAMA else (None, None)),
    }
    bad = {k: v for k, v in drift.items() if v[0] is not None and v[0] != v[1]}
    if bad:
        die(3, "configuration drift vs existing %s: %s" % (out, bad))
    state[1] = doc.get("details", {}) or {}
    reps = (doc.get("repeats", {}) or {}).get("replicates", {}) or {}
    for r in range(2, args.repeats + 1):
        block = reps.get(str(r), {}) or {}
        state[r] = block.get("details", {}) or {}
    return state


def agreement(d1: dict, d2: dict, policies) -> dict:
    common = [q for q in d1 if q in d2
              and all(p in d1[q] for p in policies) and all(p in d2[q] for p in policies)]
    out = {}
    for p in policies:
        agree = [q for q in common if d1[q][p]["passed"] == d2[q][p]["passed"]]
        disagree = [q for q in common if d1[q][p]["passed"] != d2[q][p]["passed"]]
        out[p] = {
            "n": len(common),
            "agree": len(agree),
            "disagree": len(disagree),
            "rep1_pass": sum(1 for q in common if d1[q][p]["passed"]),
            "rep2_pass": sum(1 for q in common if d2[q][p]["passed"]),
            "disagreements": disagree,
        }
    return out


def headline_block(rep1: dict, policies, pairs: dict) -> dict:
    """Orientation-explicit reading of 'the proposer's product vs cot-zero'."""
    assert HEADLINE_CHALLENGER in policies and HEADLINE_INCUMBENT in policies
    done = {q: r for q, r in rep1.items()
            if all(p in r for p in policies)}
    n = len(done)
    chal, inc = HEADLINE_CHALLENGER, HEADLINE_INCUMBENT
    tot_chal = sum(1 for r in done.values() if r[chal]["passed"])
    tot_inc = sum(1 for r in done.values() if r[inc]["passed"])
    b = sum(1 for r in done.values() if r[chal]["passed"] and not r[inc]["passed"])
    c = sum(1 for r in done.values() if r[inc]["passed"] and not r[chal]["passed"])
    assert ledger_ok(tot_inc, tot_chal, b, c), (tot_chal, tot_inc, b, c)
    key = "%s_vs_%s" % (inc, chal)  # incumbent first: run_round4/run_paired_incremental
    # put the CHALLENGER second (y), and store gain = (total_y - total_x)/n.
    entry = pairs.get(key)
    gain = ((tot_chal - tot_inc) / n) if n else 0.0
    same_orientation = (abs(entry["gain"] - gain) < 1e-9) if (entry and n) else None
    assert same_orientation is not False, (key, entry, gain)
    return {
        "pair": key,
        "chal_policy": chal,
        "inc_policy": inc,
        "orientation_note": ("PREREG-round5.md §1.1: chal = candidate being promoted, "
                             "inc = incumbent; b = chal-only, c = inc-only, "
                             "gain = (total_chal - total_inc) / n."),
        "n": n,
        "total_chal": tot_chal,
        "total_inc": tot_inc,
        "b_chal_only": b,
        "c_inc_only": c,
        "gain_chal_minus_inc": gain,
        "p": mcnemar_two_sided(b, c),
        "ledger_ok": True,
        "recomputable": True,
        "pairs_entry": entry,
        "pairs_entry_key": key,
        "pairs_entry_gain_equals_headline_gain": same_orientation,
        "pairs_entry_note": (
            "run_round4/run_paired_incremental key a pair 'x_vs_y' with y = challenger "
            "and store gain = (total_challenger - total_incumbent)/n, so this key "
            "(incumbent first) carries exactly 'gain_chal_minus_inc' — machine-checked "
            "above, not asserted in prose. Writing the key as 'textgrad_vs_cot-zero' "
            "instead would carry the sign-flipped reading."),
    }


def build_doc(args, cases, policies, model, state, url, provenance, cfg: BackendConfig) -> dict:
    rep1 = state[1]
    done1, totals1, pairs1 = compute(rep1, policies)
    grid = len(cases) * len(policies) * args.repeats
    used = sum(len(rows) for rows in state.values() for rows in rows.values())
    doc = {
        "meta": {
            "arm": "proposer-substitution",
            "plan": "paper/PLAN-NOVELTY.md Task 6",
            "prereg": ("results/rounds/round5/PREREG-round5.md §6 "
                       "(optional arm capped at 400 calls = heldout40 × 5 policies × 2; "
                       "recorded as 'not executed' if not run, never substituted)"),
            "dataset": rel(args.dataset),
            "policies": list(policies),
            "model": model,
            "ollama_url": url,
            "backend": cfg.as_meta(),
            "n": len(done1),
            "repeats": args.repeats,
            "calls_cap": args.cap,
            "planned_calls": grid,
            "calls_used": used,
            "headline_pair": "%s_vs_%s" % (HEADLINE_INCUMBENT, HEADLINE_CHALLENGER),
            "panel_derivation": PANEL_DERIVATION,
            "panel_is_default_derivation": list(policies) == list(PANEL),
            "proposer": provenance,
            "progress": {
                "calls_done": used,
                "calls_total": grid,
                "questions_done": len(done1),
                "questions_total": len(cases),
            },
        },
        "totals": totals1,
        "pairs": pairs1,
        "details": rep1,
    }
    if args.repeats > 1:
        reps = {}
        agree = {}
        for r in range(2, args.repeats + 1):
            _, totals_r, pairs_r = compute(state[r], policies)
            reps[str(r)] = {"totals": totals_r, "pairs": pairs_r, "details": state[r]}
            agree[str(r)] = agreement(state[1], state[r], policies)
        doc["repeats"] = {"n_repeats": args.repeats, "replicates": reps,
                          "agreement_vs_rep1": agree}
    doc["headline"] = headline_block(rep1, policies, pairs1)
    return doc


def save(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n",
                    encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dataset", default=str(DEFAULT_DATASET))
    ap.add_argument("--out", default=None)
    ap.add_argument("--policies", default=",".join(PANEL))
    ap.add_argument("--model", default=None,
                    help="served model id; ollama default qwen2.5:7b, "
                         "openai backend default %s" % NEW_BACKBONE_MODEL)
    ap.add_argument("--ollama-url", default=None)
    ap.add_argument("--openai-base", default=None,
                    help="OpenAI-compatible base URL (vLLM); also EVO_OPENAI_BASE. "
                         "Setting it switches the whole arm to that backend")
    ap.add_argument("--request-timeout", type=float, default=None,
                    help="per-request timeout in seconds (openai backend default %g; "
                         "ollama default %g, unchanged)"
                         % (DEFAULT_REQUEST_TIMEOUT, DEFAULT_OLLAMA_REQUEST_TIMEOUT))
    ap.add_argument("--request-retries", type=int, default=None,
                    help="bounded retries on connection error / 5xx (openai backend; "
                         "default %d)" % DEFAULT_REQUEST_RETRIES)
    ap.add_argument("--retry-backoff", type=float, default=None,
                    help="base seconds for exponential retry backoff (default %g)"
                         % DEFAULT_RETRY_BACKOFF)
    ap.add_argument("--max-tokens", type=int, default=None,
                    help="max_tokens sent to the openai backend (default %d)"
                         % DEFAULT_MAX_TOKENS)
    ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--limit", type=int, default=0,
                    help="use only the first N questions (smoke test)")
    ap.add_argument("--cap", type=int, default=CALL_CAP_PREREG)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-preflight", action="store_true")
    ap.add_argument("--allow-other-dataset", action="store_true")
    a = ap.parse_args()

    # Transport parameters (flags only; the EVO_* names are an operator input for the
    # backend choice and an OUTPUT to the evaluator subprocess, never a write-back).
    if a.request_timeout is not None and a.request_timeout <= 0:
        die(2, "--request-timeout must be > 0 seconds")
    if a.request_retries is not None and a.request_retries < 0:
        die(2, "--request-retries must be >= 0")

    if a.cap > CALL_CAP_PREREG:
        die(2, "--cap %d exceeds the preregistered cap of %d calls (PREREG-round5.md §6)"
               % (a.cap, CALL_CAP_PREREG))
    if a.repeats < 1:
        die(2, "--repeats must be >= 1")

    policies = [p.strip() for p in a.policies.split(",") if p.strip()]
    if len(set(policies)) != len(policies):
        die(4, "duplicate policy in --policies %s" % policies)
    for p in policies:
        if p in VARIABLE_CALL_POLICIES:
            die(4, "policy %r spends 2-3 model calls per question, so a fixed "
                   "cells × calls budget cannot be verified; excluded from this "
                   "fixed-budget arm (see module docstring)" % p)
    if not {HEADLINE_CHALLENGER, HEADLINE_INCUMBENT} <= set(policies):
        die(4, "headline policies missing: %s must contain both %r and %r"
               % (policies, HEADLINE_CHALLENGER, HEADLINE_INCUMBENT))

    dataset = Path(a.dataset)
    if not dataset.is_absolute():
        dataset = (ROOT / dataset).resolve()
    if dataset.name != "heldout40.json" and not a.allow_other_dataset:
        die(5, "the arm is pinned to examples/heldout40.json (got %s); "
               "--allow-other-dataset to override" % dataset)
    a.dataset = dataset
    if not dataset.exists():
        die(5, "dataset %s does not exist" % dataset)

    if a.model:
        model = a.model
    elif os.environ.get("EVO_MODEL"):
        model = os.environ["EVO_MODEL"]
    elif (a.openai_base or os.environ.get(OPENAI_BASE_ENV)):
        model = NEW_BACKBONE_MODEL          # new backend default: the served vLLM id
    else:
        model = DEFAULT_MODEL               # frozen arm default: qwen2.5:7b
    cfg = resolve_backend(a, model)
    url = cfg.ollama_url
    child_env = child_transport_env(cfg)
    # A remote 27B call may take minutes; the outer subprocess timeout must cover the
    # whole inner retry budget or a retried slow call would be killed as a failure.
    # For the ollama default (90 s, no retries) this is exactly the frozen 150 s.
    subprocess_timeout = cfg.timeout * (cfg.retries + 1) + 60
    out = Path(a.out) if a.out else (
        ROOT / "results" / "rounds" / "round5" / ("proposer-arm-%s.json" % model_slug(model)))
    if not out.is_absolute():
        out = (ROOT / out).resolve()

    cases = json.loads(dataset.read_text(encoding="utf-8"))["cases"]
    if a.limit:
        cases = cases[: a.limit]
    planned = len(cases) * len(policies) * a.repeats

    print("proposer-arm: model=%s dataset=%s(%d questions) policies=%s repeats=%d"
          % (model, rel(dataset), len(cases), policies, a.repeats), flush=True)
    print("PLANNED CALLS: %d  (cap %d; formula = %d questions × %d policies × %d repeats)"
          % (planned, a.cap, len(cases), len(policies), a.repeats), flush=True)
    print("headline pair: %s (chal) vs %s (inc)   out=%s"
          % (HEADLINE_CHALLENGER, HEADLINE_INCUMBENT, rel(out)), flush=True)
    print("transport: backend=%s model=%s endpoint=%s request_timeout=%gs "
          "retries=%d max_tokens=%s"
          % (cfg.kind, cfg.model, cfg.endpoint(), cfg.timeout, cfg.retries,
             cfg.max_tokens if cfg.kind == OPENAI else "n/a (not an ollama field)"),
          flush=True)
    if planned > a.cap:
        die(2, "planned %d calls exceed the cap of %d — refusing to start "
               "-- no model call was made" % (planned, a.cap))
    if cfg.kind == OPENAI:
        if model != NEW_BACKBONE_MODEL:
            print("WARNING: --model %s differs from the registered vLLM model id %s"
                  % (model, NEW_BACKBONE_MODEL), flush=True)
    elif model != "qwen2.5:7b":
        print("WARNING: --model %s differs from the pinned arm model qwen2.5:7b" % model,
              flush=True)

    if not a.skip_preflight:
        if cfg.kind == OPENAI:
            names = preflight_openai_or_die(cfg)
            print("preflight ok: %s reachable, %d models, %r present"
                  % (models_url(cfg.base_url), len(names), model), flush=True)
        else:
            names = preflight(url, model)
            print("preflight ok: %s reachable, %d models, %r present"
                  % (url.split("/api/")[0], len(names), model), flush=True)
    provenance = proposer_provenance(url, cfg)
    print("proposer product: %s sha256=%s"
          % (provenance["product_file"], provenance["product_sha256"][:16]), flush=True)

    if a.dry_run:
        print("dry-run: no model call made", flush=True)
        return

    state = load_state(out, a, policies, model, cfg)
    used = sum(len(rows) for rows in state.values() for rows in rows.values())
    print("resume: %d/%d calls already recorded in %s" % (used, planned, rel(out)), flush=True)

    for c in cases:
        qid = c["id"]
        for pol in policies:
            for r in range(1, a.repeats + 1):
                row = state[r].setdefault(qid, {})
                if pol in row:
                    continue
                if used >= a.cap:
                    die(2, "call cap %d reached mid-run — refusing call %d"
                           % (a.cap, used + 1))
                # One completed cell = one budgeted call; transport retries inside the
                # evaluator are not arm calls and never increment `used`.
                row[pol] = run_one(pol, None, c["input"], float(c["expected"]), model,
                                   subprocess_timeout=subprocess_timeout,
                                   env_extra=child_env)
                used += 1
                save(out, build_doc(a, cases, policies, model, state, url, provenance, cfg))
                print(json.dumps({"qid": qid, "policy": pol, "rep": r,
                                  "passed": row[pol]["passed"],
                                  "call": used, "of": planned}), flush=True)

    doc = build_doc(a, cases, policies, model, state, url, provenance, cfg)
    save(out, doc)
    print("FINAL model=%s n=%d totals=%s" % (model, doc["meta"]["n"], doc["totals"]),
          flush=True)
    print("FINAL headline %s: b=%s c=%s p=%.6g gain=%.6g"
          % (doc["headline"]["pair"], doc["headline"]["b_chal_only"],
             doc["headline"]["c_inc_only"], doc["headline"]["p"],
             doc["headline"]["gain_chal_minus_inc"]), flush=True)
    print("FINAL wrote %s (calls_used=%d/%d)"
          % (rel(out), doc["meta"]["calls_used"], doc["meta"]["calls_cap"]), flush=True)


if __name__ == "__main__":
    main()
