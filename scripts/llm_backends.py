"""Model HTTP transports for the round-5 runners (stdlib only).

Scope discipline: this module moves bytes and nothing else.  It holds NO panel,
prompt, scoring or budget logic — those live in ``scripts/run_proposer_arm.py``
(arm definition + budget guard) and ``examples/gsm8k_evaluator.py`` (prompts +
answer extraction).  Adding a transport here cannot change a scientific result;
it can only change which server answers the same prompt.

Two backends
------------
``ollama``  ``POST {EVO_OLLAMA_URL}`` body ``{"model","prompt","stream":false,
            "options":{"temperature":0}}``  (unchanged legacy path, still the
            default; the ollama request is built by the evaluator as before).

``openai``  ``POST {base}/v1/chat/completions`` body ``{"model", "messages":
            [{"role":"user","content":...}], "max_tokens": N, "temperature": 0}``
            — the OpenAI-compatible surface served by vLLM.  The answer is read
            from ``choices[0].message.content``; token usage is read from
            ``usage.completion_tokens`` when present.

Timeout / retry contract (new backend)
--------------------------------------
A 27B AWQ backbone at ~8 tokens/s can take minutes per call, so the request
timeout is a parameter (arm default 900 s, evaluator default 90 s only when
``EVO_REQUEST_TIMEOUT`` is unset).  Transient failures — connection error or a
5xx status — are retried a bounded number of times with exponential backoff and
every retry is logged to **stderr** (stdout of the evaluator subprocess is
parsed as JSON by ``run_round4.run_one``, so a log line must never go there).
A retry is a transport event, not an arm call: the arm counts completed cells
(one ``run_one`` invocation per cell), so retries cannot consume the ≤400-call
budget.

``EVO_OPENAI_BASE`` (and the ``EVO_*`` tuning names) are an operator INPUT here;
the resolved transport is handed to the evaluator subprocess through
``BackendConfig.child_env()`` + ``run_one(env_extra=...)``, never by mutating
``os.environ`` — otherwise a second run in the same process would inherit the
first one's backend and the resume guard would be defeated.

Read/connection timeouts are deliberately *not* retried: a call that exceeded a
generous timeout is not a transient transport fault, and retrying it would spend
the same wall-clock twice.  Use a larger ``--request-timeout`` instead.
"""
import json
import socket
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

# --- env var names (the runner hands these to the evaluator subprocess) ------
BACKEND_ENV = "EVO_BACKEND"
OPENAI_BASE_ENV = "EVO_OPENAI_BASE"
REQUEST_TIMEOUT_ENV = "EVO_REQUEST_TIMEOUT"
REQUEST_RETRIES_ENV = "EVO_REQUEST_RETRIES"
RETRY_BACKOFF_ENV = "EVO_RETRY_BACKOFF"
MAX_TOKENS_ENV = "EVO_MAX_TOKENS"

# --- backend kinds ----------------------------------------------------------
OLLAMA = "ollama"
OPENAI = "openai"
BACKENDS = (OLLAMA, OPENAI)

DEFAULT_OPENAI_BASE = "http://127.0.0.1:8000"
DEFAULT_OPENAI_MODEL = "qwen3.8-27b"   # served model id of Qwen3.8-27B-AWQ (vLLM)
DEFAULT_REQUEST_TIMEOUT = 900.0        # seconds; a slow 27B call must not be cut off
# The evaluator's frozen ollama default (examples/gsm8k_evaluator.py call_model).
# The runner passes EVO_REQUEST_TIMEOUT explicitly for BOTH backends, so this
# constant only has to stay equal to that fallback for the recorded timeout to
# describe the call that was actually made.
DEFAULT_OLLAMA_REQUEST_TIMEOUT = 90.0
DEFAULT_REQUEST_RETRIES = 2            # bounded: 1 initial attempt + <=2 retries
DEFAULT_RETRY_BACKOFF = 2.0            # seconds, doubled per retry
DEFAULT_MAX_TOKENS = 4096
DEFAULT_TEMPERATURE = 0                # frozen scientific setting for this repo

RETRYABLE_STATUS = frozenset({500, 502, 503, 504})


class TransportError(RuntimeError):
    """A model call did not produce a response body (non-retryable or retries spent)."""


class BadResponseError(TransportError):
    """HTTP 200 whose body is not a usable chat completion."""


def _stderr_log(message: str) -> None:
    print("[transport] %s" % message, file=sys.stderr, flush=True)


def _log(log, message: str) -> None:
    (log or _stderr_log)(message)


def normalize_base(raw: str) -> str:
    """`http://host:8000/v1/` -> `http://host:8000` (accept the /v1 form too)."""
    base = (raw or "").strip().rstrip("/")
    if base.endswith("/v1"):
        base = base[: -len("/v1")]
    return base.rstrip("/")


def chat_completions_url(base: str) -> str:
    return normalize_base(base) + "/v1/chat/completions"


def models_url(base: str) -> str:
    return normalize_base(base) + "/v1/models"


def _retryable_connection_error(exc: BaseException) -> bool:
    """Connection faults are transient; a read/connect timeout is not retried."""
    reason = getattr(exc, "reason", exc)
    if isinstance(reason, (TimeoutError, socket.timeout)):
        return False
    return isinstance(reason, (ConnectionError, OSError))


def _snippet(exc: BaseException, limit: int = 200) -> str:
    try:
        return exc.read().decode("utf-8", "replace")[:limit]
    except Exception:  # noqa: BLE001 - diagnostics must never mask the real error
        return ""


def request_json(url: str, *, body: bytes | None = None, method: str = "POST",
                 timeout: float = DEFAULT_REQUEST_TIMEOUT,
                 retries: int = DEFAULT_REQUEST_RETRIES,
                 backoff_base: float = DEFAULT_RETRY_BACKOFF, log=None) -> dict:
    """One JSON request, retried on connection errors / 5xx only (bounded, logged)."""
    headers = {"Content-Type": "application/json"}
    attempt = 0
    while True:
        attempt += 1
        try:
            req = urllib.request.Request(url, data=body, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in RETRYABLE_STATUS and attempt <= retries:
                delay = backoff_base * (2 ** (attempt - 1))
                _log(log, "retry %d/%d after HTTP %d from %s (backoff %.1fs)"
                     % (attempt, retries, exc.code, url, delay))
                if delay:
                    time.sleep(delay)
                continue
            raise TransportError("HTTP %d from %s: %s"
                                 % (exc.code, url, _snippet(exc) or exc.reason)) from exc
        except (urllib.error.URLError, ConnectionError) as exc:
            if _retryable_connection_error(exc) and attempt <= retries:
                delay = backoff_base * (2 ** (attempt - 1))
                _log(log, "retry %d/%d after %s from %s (backoff %.1fs)"
                     % (attempt, retries, type(exc).__name__, url, delay))
                if delay:
                    time.sleep(delay)
                continue
            raise TransportError("%s from %s: %s"
                                 % (type(exc).__name__, url, getattr(exc, "reason", exc))) from exc
        except (TimeoutError, socket.timeout) as exc:
            # A read timeout is not a transport fault: retrying would spend the same
            # wall-clock twice.  Raise clearly and let the caller widen the timeout.
            raise TransportError("timeout after %.0fs from %s (not retried; widen "
                                 "--request-timeout if the backbone is slow)"
                                 % (timeout, url)) from exc


def openai_chat(prompt: str, *, model: str, base: str,
                max_tokens: int = DEFAULT_MAX_TOKENS,
                temperature: int = DEFAULT_TEMPERATURE,
                timeout: float = DEFAULT_REQUEST_TIMEOUT,
                retries: int = DEFAULT_REQUEST_RETRIES,
                backoff_base: float = DEFAULT_RETRY_BACKOFF, log=None) -> dict:
    """POST /v1/chat/completions and return the parsed answer + usage.

    Returns ``{"text", "completion_tokens", "usage", "latency_s", "served_model",
    "request_url", "request_body"}``.  ``request_body`` is echoed so callers can
    record exactly what was sent.
    """
    url = chat_completions_url(base)
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": int(max_tokens),
        "temperature": temperature,
    }
    body = json.dumps(payload).encode("utf-8")
    t0 = time.monotonic()
    data = request_json(url, body=body, method="POST", timeout=timeout,
                        retries=retries, backoff_base=backoff_base, log=log)
    latency = time.monotonic() - t0
    if not isinstance(data, dict):
        raise BadResponseError("non-object response from %s" % url)
    choices = data.get("choices") or []
    if not choices:
        raise BadResponseError("no choices in response from %s: %s"
                               % (url, json.dumps(data)[:200]))
    content = ((choices[0] or {}).get("message") or {}).get("content")
    if not isinstance(content, str):
        raise BadResponseError("choices[0].message.content missing from %s" % url)
    usage = data.get("usage") or {}
    completion_tokens = usage.get("completion_tokens")
    if isinstance(completion_tokens, bool) or not isinstance(completion_tokens, (int, float)):
        completion_tokens = None
    return {
        "text": content,
        "completion_tokens": None if completion_tokens is None else int(completion_tokens),
        "usage": usage,
        "latency_s": latency,
        "served_model": data.get("model"),
        "request_url": url,
        "request_body": payload,
    }


def preflight_openai(base: str, timeout: float = 30.0,
                     retries: int = DEFAULT_REQUEST_RETRIES,
                     backoff_base: float = DEFAULT_RETRY_BACKOFF, log=None) -> list:
    """GET /v1/models -> served model ids (a non-model probe, like the ollama tags probe)."""
    data = request_json(models_url(base), body=None, method="GET", timeout=timeout,
                        retries=retries, backoff_base=backoff_base, log=log)
    entries = (data or {}).get("data") or []
    return [str(m.get("id", "")) for m in entries if isinstance(m, dict)]


@dataclass(frozen=True)
class BackendConfig:
    """The transport actually used by an arm run; recorded verbatim in ``meta.backend``."""
    kind: str
    model: str
    timeout: float
    retries: int
    max_tokens: int
    backoff_base: float
    ollama_url: str | None = None
    base_url: str | None = None
    base_arg: str | None = None

    def endpoint(self) -> str | None:
        if self.kind == OPENAI:
            return chat_completions_url(self.base_url)
        return self.ollama_url

    def child_env(self) -> dict:
        """Environment for the evaluator subprocess.

        Passed explicitly (``run_one(..., env_extra=...)``) instead of mutating
        ``os.environ``: the runner must not overwrite the very variables an
        operator may have used to select the backend, or a second invocation in
        the same process would silently inherit the first one's transport.
        """
        env = {BACKEND_ENV: self.kind,
               REQUEST_TIMEOUT_ENV: str(int(self.timeout))}
        if self.kind == OPENAI:
            env.update({
                OPENAI_BASE_ENV: self.base_url,
                MAX_TOKENS_ENV: str(self.max_tokens),
                REQUEST_RETRIES_ENV: str(self.retries),
                RETRY_BACKOFF_ENV: repr(self.backoff_base),
            })
        else:
            env["EVO_OLLAMA_URL"] = self.ollama_url
        return env

    def as_meta(self) -> dict:
        return {
            "kind": self.kind,
            "protocol": ("openai /v1/chat/completions" if self.kind == OPENAI
                         else "ollama /api/generate"),
            "base_url": normalize_base(self.base_url) if self.base_url else None,
            "base_arg": self.base_arg,
            "chat_endpoint": self.endpoint(),
            "served_model_id": self.model,
            "request_timeout_s": self.timeout,
            "max_request_retries": self.retries,
            "retry_backoff_base_s": self.backoff_base,
            # max_tokens is an openai-only request field; recording the ollama value
            # would claim a parameter that the frozen ollama body does not carry.
            "max_tokens": self.max_tokens if self.kind == OPENAI else None,
            "temperature": DEFAULT_TEMPERATURE,
        }
