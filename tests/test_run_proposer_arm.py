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
    The ollama URL points at a closed port so this stays offline and instant."""
    out = tmp_path / "ollama-run.json"
    code = run_main(monkeypatch, "--limit", "1", "--repeats", "1", "--skip-preflight",
                    "--ollama-url", "http://127.0.0.1:1", "--out", str(out))
    assert code == 0
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
    assert doc["meta"]["calls_used"] == 5         # 1 question × 5 policies × 1 repeat
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

