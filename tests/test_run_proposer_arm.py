# tests/test_run_proposer_arm.py
"""Guard tests for the round-5 Task 6 proposer-substitution arm runner.

Frozen protocol (authoritative): ``results/rounds/round5/PREREG-round5.md`` §6 — the optional
proposer arm is capped at **400 calls** (``heldout40`` × 5 policies × 2) and must never be
substituted with other data.  ``paper/PLAN-NOVELTY.md`` Task 6 pins the model (``qwen2.5:7b``),
the dataset (``examples/heldout40.json``) and the headline comparison (the proposer's product vs
``cot-zero``).

These tests lock the **refusals**, i.e. the budget guard must be able to fail (workspace rule 7:
a gate with no negative test is decoration).  Every refusal asserted here happens BEFORE the
preflight probe and therefore before any model call, so this file is offline and spends no budget.
``--dry-run`` is passed as a second safety net: if a guard ever stopped firing, the invocation
would return after preflight instead of starting the arm.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.run_proposer_arm as arm  # noqa: E402


def run_main(monkeypatch, *argv):
    """Invoke the runner's main() with argv; return its exit code (0 when it returns normally)."""
    monkeypatch.setattr(sys, "argv", ["run_proposer_arm.py", *argv])
    try:
        arm.main()
    except SystemExit as exc:
        code = exc.code
        return 0 if code is None else code
    return 0


def test_prereg_budget_formula_matches_arm_panel():
    """400 = heldout40 × 5 policies × 2 repeats, with the panel actually implemented."""
    cases = json.loads((ROOT / "examples" / "heldout40.json").read_text(encoding="utf-8"))["cases"]
    assert len(cases) == 40
    assert len(arm.PANEL) == 5
    assert len(cases) * len(arm.PANEL) * 2 == arm.CALL_CAP_PREREG == 400


def test_headline_pair_is_product_vs_cotzero_and_panel_carries_both():
    assert arm.PRODUCT_POLICY == "textgrad"
    assert arm.HEADLINE_CHALLENGER == arm.PRODUCT_POLICY
    assert arm.HEADLINE_INCUMBENT == "cot-zero"
    assert arm.PRODUCT_POLICY in arm.PANEL and "cot-zero" in arm.PANEL


def test_budget_guard_refuses_cap_violation_before_any_call(monkeypatch, tmp_path):
    """40 × 5 × 3 = 600 > 400 must be refused (exit 2), not silently truncated."""
    code = run_main(monkeypatch, "--repeats", "3", "--dry-run",
                    "--skip-preflight", "--out", str(tmp_path / "a.json"))
    assert code == 2


def test_cap_cannot_be_raised_above_the_preregistered_cap(monkeypatch, tmp_path):
    code = run_main(monkeypatch, "--cap", "500", "--dry-run",
                    "--skip-preflight", "--out", str(tmp_path / "b.json"))
    assert code == 2


def test_variable_call_policy_is_refused(monkeypatch, tmp_path):
    """reflect-retry spends 2-3 calls/question, so a fixed cell grid cannot bound the budget."""
    assert "reflect-retry" in arm.VARIABLE_CALL_POLICIES
    code = run_main(monkeypatch, "--limit", "1", "--dry-run", "--skip-preflight",
                    "--policies", "direct,step-calc,cot-zero,few-shot,textgrad,reflect-retry",
                    "--out", str(tmp_path / "c.json"))
    assert code == 4


def test_missing_headline_policy_is_refused(monkeypatch, tmp_path):
    code = run_main(monkeypatch, "--limit", "1", "--dry-run", "--skip-preflight",
                    "--policies", "direct,step-calc,few-shot",
                    "--out", str(tmp_path / "d.json"))
    assert code == 4


def test_non_heldout_dataset_is_refused(monkeypatch, tmp_path):
    code = run_main(monkeypatch, "--dataset", "examples/gsm8k40.json", "--limit", "1",
                    "--dry-run", "--skip-preflight", "--out", str(tmp_path / "e.json"))
    assert code == 5


def test_planned_call_count_printed_matches_grid(monkeypatch, tmp_path, capsys):
    """The plan (and therefore the cap arithmetic) is printed before any model call."""
    code = run_main(monkeypatch, "--limit", "2", "--dry-run", "--skip-preflight",
                    "--out", str(tmp_path / "f.json"))
    assert code == 0
    out = capsys.readouterr().out
    assert "PLANNED CALLS: 20" in out
    assert "2 questions × 5 policies × 2 repeats" in out


# ---------------------------------------------------------------------------
# Round-5 transport addition: OpenAI-compatible (vLLM) backend.
#
# Nothing here touches the panel, the prompts, the scoring or the output shape:
# these tests only pin WHICH SERVER the same arm talks to and HOW.  Every test is
# offline: the "remote" server is an in-process http.server bound to 127.0.0.1:0,
# so no test can reach the network (and none may depend on it).
# ---------------------------------------------------------------------------
import http.server  # noqa: E402 - test-local transport stub
import threading  # noqa: E402
import time  # noqa: E402

import pytest  # noqa: E402

STUB_MODEL = "qwen3.8-27b"   # the served model id of Qwen3.8-27B-AWQ under vLLM


class _StubHandler(http.server.BaseHTTPRequestHandler):
    """Minimal vLLM stand-in: GET /v1/models + POST /v1/chat/completions."""

    def log_message(self, *args):  # keep pytest output clean
        pass

    def _send(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.server.requests.append({"method": "GET", "path": self.path})
        if self.path == "/v1/models":
            self._send(200, {"object": "list",
                             "data": [{"id": m, "object": "model"} for m in self.server.model_ids]})
        else:
            self._send(404, {"error": {"message": "not found"}})

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length)
        self.server.requests.append({
            "method": "POST", "path": self.path,
            "body": json.loads(raw.decode("utf-8")),
            "content_type": self.headers.get("Content-Type"),
        })
        if self.path != "/v1/chat/completions":
            self._send(404, {"error": {"message": "not found"}})
            return
        if self.server.slow_s:                 # simulate a very slow backbone
            time.sleep(self.server.slow_s)
        if self.server.fail_after is not None:  # persistent outage: every POST
            posts = sum(1 for r in self.server.requests if r["method"] == "POST")
            if posts > self.server.fail_after:  # beyond the first N gets a 503
                self._send(503, {"error": {"message": "engine down (stub)"}})
                return
        if self.server.fail_next > 0:          # inject a transient 5xx on demand
            self.server.fail_next -= 1
            self._send(503, {"error": {"message": "engine busy"}})
            return
        self._send(200, {
            "id": "chatcmpl-stub", "object": "chat.completion",
            "model": self.server.model_ids[0],
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": self.server.answer}}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
        })


@pytest.fixture()
def stub_vllm():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _StubHandler)
    srv.requests = []
    srv.answer = "Answer: 42"
    srv.fail_next = 0
    srv.fail_after = None   # int N => every POST after the first N answers 503
    srv.slow_s = 0.0
    srv.model_ids = [STUB_MODEL]
    # the slow-response test disconnects a still-sleeping handler: keep that quiet
    srv.handle_error = lambda *args, **kwargs: None
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        yield srv
    finally:
        srv.shutdown()
        srv.server_close()
        thread.join(timeout=5)


@pytest.fixture(autouse=True)
def _isolate_transport_env(monkeypatch):
    """main() exports transport state through os.environ (as it already did for
    EVO_OLLAMA_URL); keep every test hermetic by restoring it afterwards."""
    for key in ("EVO_BACKEND", "EVO_OPENAI_BASE", "EVO_REQUEST_TIMEOUT",
                "EVO_REQUEST_RETRIES", "EVO_RETRY_BACKOFF", "EVO_MAX_TOKENS",
                "EVO_OLLAMA_URL", "EVO_MODEL"):
        monkeypatch.delenv(key, raising=False)


def stub_base(srv) -> str:
    return "http://127.0.0.1:%d" % srv.server_address[1]


def first_case_expected() -> float:
    cases = json.loads((ROOT / "examples" / "heldout40.json").read_text(encoding="utf-8"))["cases"]
    return float(cases[0]["expected"])


def openai_smoke_argv(srv, out, *extra):
    """A 5-call (1 question × 5 policies × 1 repeat) offline run on the new backend."""
    return ["--limit", "1", "--repeats", "1", "--skip-preflight",
            "--openai-base", stub_base(srv), "--out", str(out), *extra]


def post_count(srv) -> int:
    return sum(1 for r in srv.requests if r["method"] == "POST")


def test_ollama_backend_remains_the_default_transport(monkeypatch, tmp_path, capsys):
    """No --openai-base and no EVO_OPENAI_BASE -> the frozen ollama path, unchanged."""
    code = run_main(monkeypatch, "--limit", "1", "--dry-run", "--skip-preflight",
                    "--out", str(tmp_path / "g.json"))
    assert code == 0
    out = capsys.readouterr().out
    assert "transport: backend=ollama model=qwen2.5:7b" in out
    assert "endpoint=http://127.0.0.1:11434/api/generate" in out


def test_ollama_backend_meta_records_the_timeout_that_was_actually_used(
        monkeypatch, tmp_path):
    """Frozen default path (no openai base): the recorded provenance must describe
    the call really made — 90 s request timeout, no retries, no max_tokens field.
    The ollama URL points at a closed port so this stays offline and instant.

    Updated by the transport-failure validity fix (2026-09-14 incident): a closed
    port now yields 5 CONSECUTIVE transport failures, which trip the circuit
    breaker (exit 4) instead of silently "completing" 5 garbage cells; the failed
    cells are recorded call_failed and consume ZERO valid-cell budget."""
    out = tmp_path / "ollama-run.json"
    code = run_main(monkeypatch, "--limit", "1", "--repeats", "1", "--skip-preflight",
                    "--ollama-url", "http://127.0.0.1:1", "--out", str(out))
    assert code == 4                           # circuit breaker: 5 consecutive failures
    doc = json.loads(out.read_text(encoding="utf-8"))
    backend = doc["meta"]["backend"]
    assert backend["kind"] == "ollama"
    assert backend["protocol"] == "ollama /api/generate"
    assert backend["request_timeout_s"] == arm.DEFAULT_OLLAMA_REQUEST_TIMEOUT == 90.0
    assert backend["max_request_retries"] == 0
    assert backend["max_tokens"] is None          # not part of the ollama body
    assert backend["base_url"] is None
    assert doc["meta"]["ollama_url"] == "http://127.0.0.1:1/api/generate"
    assert doc["meta"]["model"] == "qwen2.5:7b"   # pinned arm model, unchanged
    assert doc["meta"]["calls_used"] == 0         # budget counts VALID cells only
    prog = doc["meta"]["progress"]
    assert (prog["valid_cells"], prog["failed_cells"], prog["attempts_total"]) == (0, 5, 5)
    cells = [doc["details"]["held-01"][p] for p in arm.PANEL]
    assert all(c["call_failed"] is True and c["error"] for c in cells)
    assert all(doc["totals"][p] == 0 for p in arm.PANEL)   # nothing answered, no crash


def test_child_env_carries_the_selected_transport():
    """The evaluator subprocess gets exactly one backend, via env_extra (not os.environ)."""
    ollama = arm.BackendConfig(kind=arm.OLLAMA, model="qwen2.5:7b", timeout=900,
                               retries=0, max_tokens=4096, backoff_base=2.0,
                               ollama_url="http://127.0.0.1:11434/api/generate")
    env = ollama.child_env()
    assert env["EVO_BACKEND"] == "ollama"
    assert env["EVO_OLLAMA_URL"].endswith("/api/generate")
    assert "EVO_OPENAI_BASE" not in env

    openai = arm.BackendConfig(kind=arm.OPENAI, model=STUB_MODEL, timeout=123.0,
                               retries=2, max_tokens=4096, backoff_base=2.0,
                               base_url="http://127.0.0.1:9")
    env2 = openai.child_env()
    assert env2["EVO_BACKEND"] == "openai"
    assert env2["EVO_OPENAI_BASE"] == "http://127.0.0.1:9"
    assert env2["EVO_REQUEST_TIMEOUT"] == "123"
    assert env2["EVO_REQUEST_RETRIES"] == "2"


def test_run_one_hands_the_transport_env_and_timeout_to_the_evaluator(monkeypatch):
    """One budgeted cell = one evaluator subprocess, whose transport comes from
    env_extra.  Defaults (no env_extra) stay exactly as before: timeout 150 s."""
    import scripts.run_round4 as rr  # noqa: PLC0415 - patched subprocess boundary

    seen = {}

    class _Done:
        stdout = json.dumps({"passed": True, "latency_s": 0.1,
                             "details": {"parsed": 18.0}})

    def fake_run(cmd, **kwargs):
        seen.update(kwargs)
        return _Done()

    monkeypatch.setattr(rr.subprocess, "run", fake_run)
    res = rr.run_one("direct", None, "q", 18.0, "qwen3.8-27b", subprocess_timeout=777,
                     env_extra={"EVO_BACKEND": "openai",
                                "EVO_OPENAI_BASE": "http://127.0.0.1:1"})
    assert res["passed"] is True
    assert seen["timeout"] == 777
    assert seen["env"]["EVO_BACKEND"] == "openai"
    assert seen["env"]["EVO_OPENAI_BASE"] == "http://127.0.0.1:1"
    assert seen["env"]["EVO_MODEL"] == "qwen3.8-27b"

    seen.clear()
    rr.run_one("direct", None, "q", 18.0, "qwen2.5:7b")
    assert seen["timeout"] == 150                 # unchanged default
    assert "EVO_BACKEND" not in seen["env"]       # ollama callers untouched


# (a) request body + parse path -------------------------------------------------

def test_openai_chat_sends_exact_body_and_parses_answer(stub_vllm):
    prompt = "Q: Jimmy has $2 more than twice the money Ethel has."
    res = arm.openai_chat(prompt, model=STUB_MODEL, base=stub_base(stub_vllm),
                          max_tokens=128, timeout=10, retries=0, backoff_base=0)
    assert res["text"] == "Answer: 42"          # choices[0].message.content
    assert res["completion_tokens"] == 7        # usage.completion_tokens
    assert res["served_model"] == STUB_MODEL
    sent = stub_vllm.requests[-1]
    assert (sent["method"], sent["path"]) == ("POST", "/v1/chat/completions")
    assert sent["content_type"] == "application/json"
    assert sent["body"] == {
        "model": STUB_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 128,
        "temperature": 0,
    }


def test_openai_chat_accepts_a_base_url_that_already_carries_v1(stub_vllm):
    res = arm.openai_chat("q", model=STUB_MODEL, base=stub_base(stub_vllm) + "/v1/",
                          max_tokens=16, timeout=10, retries=0, backoff_base=0)
    assert res["text"] == "Answer: 42"
    assert res["request_url"] == stub_base(stub_vllm) + "/v1/chat/completions"
    assert stub_vllm.requests[-1]["path"] == "/v1/chat/completions"


def test_openai_backend_runs_the_frozen_arm_end_to_end(stub_vllm, monkeypatch, tmp_path):
    """The arm, the evaluator and the parsing path all run against the stub server."""
    stub_vllm.answer = "Answer: %g" % first_case_expected()
    out = tmp_path / "openai.json"
    assert run_main(monkeypatch, *openai_smoke_argv(stub_vllm, out)) == 0
    doc = json.loads(out.read_text(encoding="utf-8"))

    # panel / scoring / budget untouched: 5 cells, one per policy, all parsed
    assert doc["meta"]["policies"] == list(arm.PANEL) == [
        "direct", "step-calc", "cot-zero", "few-shot", "textgrad"]
    assert doc["meta"]["planned_calls"] == doc["meta"]["calls_used"] == 5
    assert doc["meta"]["calls_cap"] == arm.CALL_CAP_PREREG == 400
    assert len(doc["details"]) == 1
    assert all(len(rows) == 5 for rows in doc["details"].values())
    assert all(doc["totals"][p] == 1 for p in arm.PANEL)
    assert set(doc) == {"meta", "totals", "pairs", "details", "headline"}
    assert doc["headline"]["pair"] == "cot-zero_vs_textgrad"

    # provenance of the transport (task 3)
    backend = doc["meta"]["backend"]
    assert backend["kind"] == "openai"
    assert backend["base_url"] == stub_base(stub_vllm)
    assert backend["chat_endpoint"] == stub_base(stub_vllm) + "/v1/chat/completions"
    assert backend["served_model_id"] == arm.NEW_BACKBONE_MODEL == "qwen3.8-27b"
    assert doc["meta"]["model"] == "qwen3.8-27b"
    assert backend["request_timeout_s"] == arm.DEFAULT_REQUEST_TIMEOUT == 900.0
    assert backend["temperature"] == 0
    assert doc["meta"]["ollama_url"] is None
    assert post_count(stub_vllm) == 5           # exactly one call per cell


# (b) budget guard ---------------------------------------------------------------

def test_openai_backend_budget_guard_refuses_over_cap_without_any_request(
        stub_vllm, monkeypatch, tmp_path):
    """40 × 5 × 3 = 600 > 400 must still exit 2, with zero HTTP requests made."""
    code = run_main(monkeypatch, "--repeats", "3", "--dry-run", "--skip-preflight",
                    "--openai-base", stub_base(stub_vllm),
                    "--out", str(tmp_path / "cap.json"))
    assert code == 2
    assert stub_vllm.requests == []


def test_openai_backend_cap_cannot_be_raised_above_the_preregistered_cap(
        stub_vllm, monkeypatch, tmp_path):
    code = run_main(monkeypatch, "--cap", "500", "--dry-run", "--skip-preflight",
                    "--openai-base", stub_base(stub_vllm),
                    "--out", str(tmp_path / "cap2.json"))
    assert code == 2
    assert stub_vllm.requests == []


# (c) retry on 5xx ---------------------------------------------------------------

def test_a_read_timeout_is_not_retried(stub_vllm):
    """A call that blew its timeout is not a transient transport fault: it surfaces
    as TransportError after ONE attempt (the caller widens --request-timeout)."""
    stub_vllm.slow_s = 1.0
    with pytest.raises(arm.TransportError):
        arm.openai_chat("q", model=STUB_MODEL, base=stub_base(stub_vllm), max_tokens=16,
                        timeout=0.4, retries=2, backoff_base=0)
    assert post_count(stub_vllm) == 1            # no re-spend of the request


def test_retry_on_5xx_succeeds_without_consuming_extra_budget(
        stub_vllm, monkeypatch, tmp_path):
    stub_vllm.answer = "Answer: %g" % first_case_expected()
    stub_vllm.fail_next = 1                      # exactly one transient 503
    out = tmp_path / "retry.json"
    code = run_main(monkeypatch, *openai_smoke_argv(
        stub_vllm, out, "--request-retries", "2", "--retry-backoff", "0",
        "--request-timeout", "123"))
    assert code == 0
    doc = json.loads(out.read_text(encoding="utf-8"))

    assert post_count(stub_vllm) == 6            # 5 cells + the 1 retried request
    assert doc["meta"]["backend"]["max_request_retries"] == 2
    assert doc["meta"]["backend"]["request_timeout_s"] == 123.0   # --request-timeout honoured
    # a transport retry is not an arm call: the budget counts completed cells only
    assert doc["meta"]["calls_used"] == doc["meta"]["planned_calls"] == 5
    assert all(doc["totals"][p] == 1 for p in arm.PANEL)   # retried call still answered


# (d) resume / config drift ------------------------------------------------------

def test_resume_with_a_different_backend_or_model_is_refused(
        stub_vllm, monkeypatch, tmp_path, capsys):
    out = tmp_path / "drift.json"
    assert run_main(monkeypatch, *openai_smoke_argv(stub_vllm, out)) == 0
    baseline = len(stub_vllm.requests)

    # same base URL, different served model id
    code = run_main(monkeypatch, *openai_smoke_argv(stub_vllm, out, "--model", "qwen2.5:7b"))
    assert code == 3
    err = capsys.readouterr().err
    assert "configuration drift" in err and "backend_model_id" in err

    # different backend kind: ollama (no --openai-base) against an openai-written file
    code = run_main(monkeypatch, "--limit", "1", "--repeats", "1", "--skip-preflight",
                    "--out", str(out))
    assert code == 3
    err = capsys.readouterr().err
    assert "backend_kind" in err and "ollama" in err

    assert len(stub_vllm.requests) == baseline    # both refusals made no HTTP request


def test_resume_with_the_same_backend_continues_without_new_calls(
        stub_vllm, monkeypatch, tmp_path, capsys):
    """Positive control: the new drift check must not block a legitimate resume."""
    out = tmp_path / "resume.json"
    assert run_main(monkeypatch, *openai_smoke_argv(stub_vllm, out)) == 0
    assert post_count(stub_vllm) == 5
    assert run_main(monkeypatch, *openai_smoke_argv(stub_vllm, out)) == 0
    assert "resume: 5/5 calls already recorded" in capsys.readouterr().out
    assert post_count(stub_vllm) == 5            # nothing re-called
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["meta"]["calls_used"] == 5


# preflight (non-model probe) ----------------------------------------------------

def test_openai_preflight_probes_v1_models_and_makes_no_completion_call(
        stub_vllm, monkeypatch, tmp_path):
    code = run_main(monkeypatch, "--limit", "1", "--dry-run",
                    "--openai-base", stub_base(stub_vllm),
                    "--out", str(tmp_path / "preflight.json"))
    assert code == 0
    assert [r["path"] for r in stub_vllm.requests] == ["/v1/models"]


def test_openai_preflight_refuses_a_model_the_server_does_not_serve(
        stub_vllm, monkeypatch, tmp_path, capsys):
    code = run_main(monkeypatch, "--limit", "1", "--dry-run",
                    "--openai-base", stub_base(stub_vllm), "--model", "not-served",
                    "--out", str(tmp_path / "preflight2.json"))
    assert code == 6
    assert "not-served" in capsys.readouterr().err
    assert [r["path"] for r in stub_vllm.requests] == ["/v1/models"]   # refused before any call


# ---------------------------------------------------------------------------
# Round-5 T6 validity fix: TRANSPORT FAILURES ARE NOT DATA.
#
# Incident (2026-09-14, forensics in
# results/rounds/round5/proposer-arm-qwen38-27b.QUARANTINE.md): the vLLM server
# was SIGTERMed at call 140/400; the runner recorded the remaining 260 transport
# failures as valid `passed=false` data, burned the whole 400-call budget, never
# retried them on resume and reported "completed 400/400" with no alarm.
#
# Validity rule locked by these tests:
#   a recorded cell is a TRANSPORT FAILURE (not data) iff it carries a non-empty
#   `error`, OR (migration signature for cells recorded before the fix)
#   `latency == 0 AND parsed is None AND passed is False`;
#   a genuine wrong answer (latency > 0, any parsed, passed False) is VALID.
# Failed cells are stored `{"call_failed": true, "error": ...}`, excluded from
# totals/pairs/headline/agreement/questions_done (which all carry `n_valid`),
# retried on resume, bounded by --attempts-cap, and 5 consecutive failures trip
# the circuit breaker (exit 4, state saved).
#
# All tests here are offline: the "remote" server is the in-process stub above.
# ---------------------------------------------------------------------------
import argparse  # noqa: E402 - test-local

POLICIES2 = "cot-zero,textgrad"   # the minimal panel that still carries the headline pair


def case_ids(n: int) -> list:
    cases = json.loads((ROOT / "examples" / "heldout40.json").read_text(encoding="utf-8"))["cases"]
    return [c["id"] for c in cases[:n]]


def case_expected(i: int) -> float:
    cases = json.loads((ROOT / "examples" / "heldout40.json").read_text(encoding="utf-8"))["cases"]
    return float(cases[i]["expected"])


def progress_of(doc: dict) -> dict:
    return doc["meta"]["progress"]


# --- fix 1: run_one propagates the evaluator's details.error -----------------

def test_run_one_propagates_evaluator_details_error(monkeypatch):
    """The evaluator reports a transport failure as details.error; run_one's
    success path must surface it as "error" instead of dropping it."""
    import scripts.run_round4 as rr  # noqa: PLC0415 - patched subprocess boundary

    class _Done:
        stdout = json.dumps({"passed": False, "score": 0.0, "cost": 0.0, "latency_s": 0.0,
                             "details": {"policy": "direct", "error": "TransportError"}})

    monkeypatch.setattr(rr.subprocess, "run", lambda cmd, **kw: _Done())
    res = rr.run_one("direct", None, "q", 18.0, "m")
    assert res == {"passed": False, "latency": 0.0, "parsed": None,
                   "error": "TransportError"}


def test_run_one_success_path_stays_byte_compatible_without_error(monkeypatch):
    """No details.error => exactly the pre-fix keys (passed/latency/parsed), so
    every existing caller that ignores the extra key is unaffected."""
    import scripts.run_round4 as rr  # noqa: PLC0415 - patched subprocess boundary

    class _Done:
        stdout = json.dumps({"passed": True, "score": 1.0, "cost": 0.0,
                             "latency_s": 1.5, "details": {"parsed": 18.0}})

    monkeypatch.setattr(rr.subprocess, "run", lambda cmd, **kw: _Done())
    res = rr.run_one("direct", None, "q", 18.0, "m")
    assert res == {"passed": True, "latency": 1.5, "parsed": 18.0}
    assert "error" not in res


def test_paired_compute_tolerates_the_extra_error_key():
    """run_paired_incremental.compute (shared with the arm) must not choke on
    cells carrying the new additive "error" key."""
    from scripts.run_paired_incremental import compute
    details = {"q1": {"a": {"passed": True, "latency": 1.0, "parsed": 1.0,
                            "error": "TransportError"},
                      "b": {"passed": False, "latency": 2.0, "parsed": None}}}
    done, totals, pairs = compute(details, ["a", "b"])
    assert len(done) == 1
    assert totals == {"a": 1, "b": 0}
    assert pairs["a_vs_b"]["ledger_ok"]


# --- fix 2: the validity rule itself ------------------------------------------

def test_validity_rule_separates_wrong_answers_from_transport_failures():
    # genuine wrong answers (latency > 0) are VALID data, whatever parsed is
    assert not arm.is_failed_cell({"passed": False, "latency": 0.812, "parsed": 7.0})
    assert not arm.is_failed_cell({"passed": False, "latency": 1.3, "parsed": None})
    assert not arm.is_failed_cell({"passed": True, "latency": 2.0, "parsed": 18.0})
    # latency 0 but an answer was parsed: something really came back => valid
    assert not arm.is_failed_cell({"passed": False, "latency": 0.0, "parsed": 5.0})
    # new-format transport failure: non-empty error (propagated details.error)
    assert arm.is_failed_cell({"passed": False, "latency": 0.0, "parsed": None,
                               "error": "TransportError"})
    # legacy migration signature: latency == 0 AND parsed is None AND passed False
    assert arm.is_failed_cell({"passed": False, "latency": 0.0, "parsed": None})
    # already-marked cells stay failed
    assert arm.is_failed_cell({"passed": False, "latency": 0.0, "parsed": None,
                               "call_failed": True, "error": "legacy-signature"})


def test_circuit_breaker_threshold_is_five():
    assert arm.CIRCUIT_BREAKER_LIMIT == 5


# --- (a) a 503 run records call_failed cells, excluded from every datum -------

def test_503_run_records_call_failed_cells_excluded_from_all_data(
        stub_vllm, monkeypatch, tmp_path):
    stub_vllm.fail_after = 0                     # every POST gets a 503
    out = tmp_path / "all-failed.json"
    code = run_main(monkeypatch, "--limit", "1", "--repeats", "1", "--skip-preflight",
                    "--openai-base", stub_base(stub_vllm), "--out", str(out),
                    "--policies", POLICIES2,
                    "--request-retries", "0", "--retry-backoff", "0")
    assert code == 0                             # 2 failures < breaker threshold
    assert post_count(stub_vllm) == 2            # one attempt per cell, retries 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    for p in ("cot-zero", "textgrad"):
        cell = doc["details"]["held-01"][p]
        assert cell["call_failed"] is True
        assert cell["error"]                     # non-empty, from the evaluator
        assert cell["passed"] is False
    # excluded from totals / pairs / headline
    assert all(doc["totals"][p] == 0 for p in ("cot-zero", "textgrad"))
    assert doc["totals"]["n_valid"] == 0
    assert doc["pairs"]["cot-zero_vs_textgrad"]["n_valid"] == 0
    assert doc["headline"]["n_valid"] == 0 and doc["headline"]["n"] == 0
    prog = progress_of(doc)
    assert prog["valid_cells"] == 0
    assert prog["failed_cells"] == 2
    assert prog["attempts_total"] == 2
    assert prog["questions_done"] == 0
    assert doc["meta"]["calls_used"] == 0        # failed cells consume no valid budget
    assert doc["meta"]["attempts_cap"] == arm.DEFAULT_ATTEMPTS_CAP == 800


# --- (b) resume retries failed cells and never re-calls valid ones ------------

def test_resume_retries_failed_cells_and_never_recalls_valid_ones(
        stub_vllm, monkeypatch, tmp_path):
    stub_vllm.answer = "Answer: %g" % first_case_expected()
    stub_vllm.fail_after = 1                     # POST #1 ok, POST #2 dies
    out = tmp_path / "mixed.json"
    argv = ("--limit", "1", "--repeats", "1", "--skip-preflight",
            "--openai-base", stub_base(stub_vllm), "--out", str(out),
            "--policies", POLICIES2, "--request-retries", "0", "--retry-backoff", "0")
    assert run_main(monkeypatch, *argv) == 0
    doc1 = json.loads(out.read_text(encoding="utf-8"))
    good_before = doc1["details"]["held-01"]["cot-zero"]
    assert "call_failed" not in good_before and good_before["passed"] is True
    assert doc1["details"]["held-01"]["textgrad"]["call_failed"] is True
    assert post_count(stub_vllm) == 2

    stub_vllm.fail_after = None                  # service restored
    assert run_main(monkeypatch, *argv) == 0
    assert post_count(stub_vllm) == 3            # ONLY the failed cell was retried
    doc2 = json.loads(out.read_text(encoding="utf-8"))
    assert doc2["details"]["held-01"]["cot-zero"] == good_before   # untouched
    retried = doc2["details"]["held-01"]["textgrad"]
    assert "call_failed" not in retried and retried["passed"] is True
    prog = progress_of(doc2)
    assert (prog["valid_cells"], prog["failed_cells"]) == (2, 0)
    assert prog["attempts_total"] == 3           # the retry counted as a new attempt
    assert doc2["totals"]["n_valid"] == 1 and doc2["headline"]["n_valid"] == 1


# --- (c) circuit breaker -------------------------------------------------------

def test_circuit_breaker_trips_at_five_consecutive_failures_with_state_saved(
        stub_vllm, monkeypatch, tmp_path, capsys):
    stub_vllm.fail_after = 0
    out = tmp_path / "breaker.json"
    code = run_main(monkeypatch, "--limit", "1", "--repeats", "1", "--skip-preflight",
                    "--openai-base", stub_base(stub_vllm), "--out", str(out),
                    "--request-retries", "0", "--retry-backoff", "0")
    assert code == 4
    err = capsys.readouterr().err
    assert "circuit breaker: 5 consecutive transport failures" in err
    assert "server likely down" in err and "state saved" in err
    assert post_count(stub_vllm) == 5            # no POST after the breaker tripped
    doc = json.loads(out.read_text(encoding="utf-8"))   # state saved BEFORE die
    prog = progress_of(doc)
    assert (prog["valid_cells"], prog["failed_cells"], prog["attempts_total"]) == (0, 5, 5)
    cells = [doc["details"]["held-01"][p] for p in arm.PANEL]
    assert len(cells) == 5 and all(c["call_failed"] is True for c in cells)


# --- (d) a genuine wrong answer is valid data, never retried -------------------

def test_genuine_wrong_answer_is_valid_and_never_retried(
        stub_vllm, monkeypatch, tmp_path):
    stub_vllm.answer = "Answer: -12345"          # parses cleanly, scores False
    stub_vllm.slow_s = 0.01                      # guarantee a measurable latency
    out = tmp_path / "wrong.json"
    argv = ("--limit", "1", "--repeats", "1", "--skip-preflight",
            "--openai-base", stub_base(stub_vllm), "--out", str(out),
            "--request-retries", "0", "--retry-backoff", "0")
    assert run_main(monkeypatch, *argv) == 0
    assert post_count(stub_vllm) == 5
    doc = json.loads(out.read_text(encoding="utf-8"))
    for p in arm.PANEL:
        cell = doc["details"]["held-01"][p]
        assert cell["passed"] is False           # wrong...
        assert cell["latency"] > 0               # ...but really answered => DATA
        assert cell["parsed"] == -12345.0
        assert "call_failed" not in cell and "error" not in cell
    prog = progress_of(doc)
    assert (prog["valid_cells"], prog["failed_cells"]) == (5, 0)
    assert prog["questions_done"] == 1
    assert doc["totals"]["n_valid"] == 1         # complete valid row, all answers wrong
    assert all(doc["totals"][p] == 0 for p in arm.PANEL)
    assert doc["headline"]["n_valid"] == 1
    # resume: a wrong answer is data — it is NEVER re-called
    assert run_main(monkeypatch, *argv) == 0
    assert post_count(stub_vllm) == 5


# --- (e) legacy polluted-file migration ----------------------------------------

def legacy_doc(base_url: str) -> dict:
    """A synthetic file of the EXACT quarantined artefact's shape (cells recorded
    before the fix): old 4-key meta.progress (no attempts_total), cells without
    call_failed/error keys, repeats.replicates, old totals/pairs/headline blocks.
    held-01 = good cells (latency > 0), held-02 = the transport-failure signature
    (latency 0.0 / parsed None / passed False).  The real quarantined JSON is
    never read, modified or copied."""
    qids = case_ids(2)
    good_q, bad_q = qids[0], qids[1]
    expected1 = case_expected(0)

    def rep_details(latency: float) -> dict:
        det = {good_q: {}, bad_q: {}}
        for p in arm.PANEL:
            det[good_q][p] = {"passed": p in ("cot-zero", "textgrad"),
                              "latency": latency, "parsed": expected1}
            det[bad_q][p] = {"passed": False, "latency": 0.0, "parsed": None}
        return det

    return {
        "meta": {
            "arm": "proposer-substitution",
            "plan": "paper/PLAN-NOVELTY.md Task 6",
            "dataset": "examples/heldout40.json",
            "policies": list(arm.PANEL),
            "model": "qwen3.8-27b",
            "ollama_url": None,
            "backend": {"kind": "openai", "base_url": base_url,
                        "served_model_id": "qwen3.8-27b"},
            "n": 2, "repeats": 2, "calls_cap": 400,
            "planned_calls": 20, "calls_used": 20,
            "progress": {"calls_done": 20, "calls_total": 20,
                         "questions_done": 2, "questions_total": 2},
        },
        "totals": {p: 2 for p in arm.PANEL},
        "pairs": {},
        "details": rep_details(6.5),
        "repeats": {"n_repeats": 2,
                    "replicates": {"2": {"totals": {p: 2 for p in arm.PANEL},
                                         "pairs": {},
                                         "details": rep_details(7.25)}},
                    "agreement_vs_rep1": {}},
        "headline": {"pair": "cot-zero_vs_textgrad", "n": 2},
    }


def test_legacy_polluted_file_loads_with_bad_cells_marked_failed(
        stub_vllm, tmp_path):
    out = tmp_path / "legacy.json"
    out.write_text(json.dumps(legacy_doc(stub_base(stub_vllm))), encoding="utf-8")
    args = argparse.Namespace(repeats=2, dataset=ROOT / "examples" / "heldout40.json")
    cfg = arm.BackendConfig(kind=arm.OPENAI, model="qwen3.8-27b", timeout=900.0,
                            retries=0, max_tokens=4096, backoff_base=0.0,
                            base_url=stub_base(stub_vllm))
    state, attempts = arm.load_state(out, args, list(arm.PANEL), "qwen3.8-27b", cfg)
    # no attempts_total in the legacy meta => derived from recorded cell count
    assert attempts == 20
    qids = case_ids(2)
    good = state[1][qids[0]]["direct"]
    assert "call_failed" not in good                     # latency > 0 => VALID
    for r in (1, 2):
        for p in arm.PANEL:
            bad = state[r][qids[1]][p]
            assert bad["call_failed"] is True
            assert bad["error"] == "legacy-signature"


def test_legacy_polluted_file_resumes_by_retrying_only_bad_cells(
        stub_vllm, monkeypatch, tmp_path):
    out = tmp_path / "legacy-resume.json"
    out.write_text(json.dumps(legacy_doc(stub_base(stub_vllm))), encoding="utf-8")
    stub_vllm.answer = "Answer: %g" % case_expected(1)   # retried cells become valid
    code = run_main(monkeypatch, "--limit", "2", "--skip-preflight",
                    "--openai-base", stub_base(stub_vllm), "--out", str(out),
                    "--request-retries", "0", "--retry-backoff", "0")
    assert code == 0
    qids = case_ids(2)
    assert post_count(stub_vllm) == 10     # ONLY held-02's 5 policies × 2 reps retried
    doc = json.loads(out.read_text(encoding="utf-8"))
    prog = progress_of(doc)
    assert (prog["valid_cells"], prog["failed_cells"]) == (20, 0)
    assert prog["attempts_total"] == 30    # 20 legacy attempts + 10 retries
    assert prog["questions_done"] == 2
    assert doc["headline"]["n_valid"] == 2
    assert doc["totals"]["n_valid"] == 2
    good = doc["details"][qids[0]]["direct"]
    assert "call_failed" not in good and good["latency"] == 6.5   # never re-called
    assert doc["repeats"]["replicates"]["2"]["totals"]["n_valid"] == 2


# --- (f) n_valid reflects only valid cells --------------------------------------

def test_n_valid_counts_only_valid_cells(stub_vllm, monkeypatch, tmp_path):
    stub_vllm.answer = "Answer: %g" % first_case_expected()
    stub_vllm.fail_after = 2       # q1's 2 POSTs ok; q2+q3's 4 POSTs all 503
    out = tmp_path / "shrunk.json"
    code = run_main(monkeypatch, "--limit", "3", "--repeats", "1", "--skip-preflight",
                    "--openai-base", stub_base(stub_vllm), "--out", str(out),
                    "--policies", POLICIES2,
                    "--request-retries", "0", "--retry-backoff", "0")
    assert code == 0               # 4 consecutive failures < breaker threshold 5
    assert post_count(stub_vllm) == 6
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["meta"]["n"] == 1
    assert doc["totals"]["n_valid"] == 1
    assert doc["pairs"]["cot-zero_vs_textgrad"]["n_valid"] == 1
    assert doc["headline"]["n_valid"] == 1 and doc["headline"]["n"] == 1
    prog = progress_of(doc)
    assert (prog["valid_cells"], prog["failed_cells"], prog["attempts_total"]) == (2, 4, 6)
    assert prog["questions_done"] == 1
    assert prog["calls_total"] == doc["meta"]["planned_calls"] == 6
    assert doc["meta"]["calls_used"] == 2


# --- (g) attempts cap -----------------------------------------------------------

def test_attempts_cap_refuses_further_calls_with_zero_requests(
        stub_vllm, monkeypatch, tmp_path, capsys):
    stub_vllm.fail_after = 0
    out = tmp_path / "attcap.json"
    argv = ("--limit", "1", "--repeats", "1", "--skip-preflight",
            "--openai-base", stub_base(stub_vllm), "--out", str(out),
            "--policies", POLICIES2, "--request-retries", "0", "--retry-backoff", "0",
            "--attempts-cap", "2")
    assert run_main(monkeypatch, *argv) == 0     # grid exhausted: 2 attempts, 2 failed
    baseline = post_count(stub_vllm)
    assert baseline == 2
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["meta"]["attempts_cap"] == 2
    assert progress_of(doc)["attempts_total"] == 2

    code = run_main(monkeypatch, *argv)          # resume => refused BEFORE any HTTP
    assert code == 2
    assert post_count(stub_vllm) == baseline     # zero new HTTP requests
    assert "attempts cap" in capsys.readouterr().err


def test_planned_beyond_attempts_cap_is_refused_before_any_request(
        stub_vllm, monkeypatch, tmp_path):
    code = run_main(monkeypatch, "--limit", "1", "--repeats", "1", "--dry-run",
                    "--skip-preflight", "--attempts-cap", "1",
                    "--openai-base", stub_base(stub_vllm),
                    "--policies", POLICIES2,
                    "--out", str(tmp_path / "x.json"))
    assert code == 2                             # planned 2 > attempts cap 1
    assert stub_vllm.requests == []

