"""
Single AI client for all of Friday — with model fallback and loud failures.

WHY THIS EXISTS
---------------
Model names were hardcoded in eight places (classifier, dsa_agent, youtube_agent,
article_fetcher, rss_processor, retrieval, review, wiki). When Google retired
`gemini-2.0-flash` and Groq retired `llama-3.3-70b-versatile`, every one of those
call sites started returning 404 — and because each had a `except: return None`
fallback, Friday silently degraded to the offline keyword classifier with no
error anywhere. Notes kept getting saved, just badly: truncated titles, near
duplicate pages, no summaries.

This module fixes the class of bug, not just the instance:

  * Model names live in ONE place and are lists, not strings.
  * A dead model is skipped and the next is tried; the first that works is
    cached for the process.
  * `gemini-flash-latest` is preferred precisely because it is a moving alias
    that survives deprecations.
  * `health()` reports what actually works, so `friday doctor` can surface a dead
    AI layer instead of hiding it.
  * `last_error()` keeps the real reason available for diagnostics.
"""

import json
import re
import threading
import time
import warnings

from friday.config import (
    AI_PRIMARY,
    GEMINI_API_KEY,
    GEMINI_MODELS,
    GROQ_API_KEY,
    GROQ_MODELS,
    OLLAMA_ENABLED,
    OLLAMA_HOST,
    OLLAMA_MODEL,
    WHISPER_MODEL,
)

_lock = threading.Lock()
_working = {"gemini": None, "groq": None, "ollama": None}  # cache first model that responds
_last_error = {"gemini": "", "groq": "", "ollama": ""}
OLLAMA_TIMEOUT = 180

GEMINI_TIMEOUT = 45
GROQ_TIMEOUT = 60
RETRY_BACKOFF = 2.0  # seconds, multiplied by the attempt number

# Errors that mean "this model will never work" — skip to the next candidate
# immediately instead of burning the timeout budget on it.
_FATAL_MODEL_ERRORS = ("not found", "404", "no longer available",
                       "does not exist", "not supported", "invalid model",
                       "permission", "unauthorized", "401", "403")


def _is_fatal(message):
    lowered = str(message).lower()
    return any(token in lowered for token in _FATAL_MODEL_ERRORS)


def last_error():
    return dict(_last_error)


def reset_cache():
    with _lock:
        _working["gemini"] = None
        _working["groq"] = None
        _working["ollama"] = None


# --------------------------------------------------------------------------- #
# Providers
# --------------------------------------------------------------------------- #
def _gemini_client():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        import google.generativeai as genai
    genai.configure(api_key=GEMINI_API_KEY)
    return genai


def _try_gemini(prompt, max_tokens, temperature):
    if not GEMINI_API_KEY:
        return None
    try:
        genai = _gemini_client()
    except Exception as exc:
        _last_error["gemini"] = f"sdk: {exc}"
        return None

    candidates = ([_working["gemini"]] if _working["gemini"]
                  else list(GEMINI_MODELS))
    for model_name in candidates:
        try:
            model = genai.GenerativeModel(model_name)
            resp = model.generate_content(
                prompt,
                generation_config={
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                },
                # Hard bound: without this the SDK retries a dead model with
                # exponential backoff and a 404 costs minutes instead of ms.
                request_options={"timeout": GEMINI_TIMEOUT},
            )
            text = (getattr(resp, "text", "") or "").strip()
            if text:
                with _lock:
                    _working["gemini"] = model_name
                return text
            _last_error["gemini"] = f"{model_name}: empty response"
        except Exception as exc:
            _last_error["gemini"] = f"{model_name}: {str(exc)[:160]}"
            # A cached model that just died — clear it and retry the full list.
            if _working["gemini"] == model_name:
                with _lock:
                    _working["gemini"] = None
                return _try_gemini(prompt, max_tokens, temperature)
            # Non-fatal (rate limit, transient): stop here rather than hammering
            # every remaining model with the same doomed request.
            if not _is_fatal(exc):
                break
    return None


def _try_groq(prompt, max_tokens, temperature):
    if not GROQ_API_KEY:
        return None
    import httpx

    candidates = ([_working["groq"]] if _working["groq"] else list(GROQ_MODELS))
    for model_name in candidates:
        try:
            resp = httpx.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                json={
                    "model": model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                timeout=GROQ_TIMEOUT,
            )
            if resp.status_code == 200:
                text = resp.json()["choices"][0]["message"]["content"].strip()
                if text:
                    with _lock:
                        _working["groq"] = model_name
                    return text
                _last_error["groq"] = f"{model_name}: empty response"
            else:
                _last_error["groq"] = f"{model_name}: HTTP {resp.status_code} {resp.text[:120]}"
                if _working["groq"] == model_name:
                    with _lock:
                        _working["groq"] = None
                    return _try_groq(prompt, max_tokens, temperature)
                # Rate limit / server error: trying other models won't help.
                if resp.status_code in (429, 500, 502, 503):
                    break
        except Exception as exc:
            _last_error["groq"] = f"{model_name}: {str(exc)[:160]}"
            break  # network-level failure — do not retry every model
    return None


def _try_ollama(prompt, max_tokens, temperature):
    """Local model via Ollama (stdlib HTTP, 127.0.0.1 only). Free and private."""
    if not OLLAMA_ENABLED:
        return None
    import urllib.request

    body = json.dumps({
        "model": OLLAMA_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }).encode("utf-8")
    req = urllib.request.Request(f"{OLLAMA_HOST}/api/chat", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT) as resp:
            text = (json.loads(resp.read())["message"]["content"] or "").strip()
        if text:
            with _lock:
                _working["ollama"] = OLLAMA_MODEL
            return text
        _last_error["ollama"] = f"{OLLAMA_MODEL}: empty response"
    except Exception as exc:
        _last_error["ollama"] = f"{OLLAMA_MODEL}: {str(exc)[:160]}"
    return None


_PROVIDERS = {"groq": "_try_groq", "gemini": "_try_gemini", "ollama": "_try_ollama"}


def provider_order(primary=None):
    """Primary first, then the other cloud provider, then the local model as the
    always-available free fallback (unless it is primary already)."""
    primary = (primary or AI_PRIMARY or "groq").lower()
    if primary not in _PROVIDERS:
        primary = "groq"
    rest = [p for p in ("groq", "gemini", "ollama") if p != primary]
    return [primary] + rest


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def complete(prompt, max_tokens=1200, temperature=0.2, prefer=None, retries=2):
    """Return model text, or None if every provider/model failed.

    prefer:  "groq" to try Groq first (faster for short structured jobs).
    retries: extra passes over the provider list when everything failed.

    The retry matters more than it looks. Free tiers rate-limit under bursts —
    synthesizing eight wiki pages back to back tripped it — and without a retry
    a momentary 429 silently produced a degraded, non-AI page with no error
    surfaced anywhere. Backoff is short because a genuinely dead model has
    already been ruled out by _is_fatal before we get here.
    """
    order = provider_order(prefer)

    for attempt in range(retries + 1):
        for provider in order:
            fn = globals()[_PROVIDERS[provider]]
            result = fn(prompt, max_tokens, temperature)
            if result:
                return result
        if attempt < retries:
            time.sleep(RETRY_BACKOFF * (attempt + 1))
    return None


def extract_json(text):
    """Parse JSON out of a model response tolerantly (fences, prose, arrays)."""
    if not text:
        return None
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    for opener, closer in (("{", "}"), ("[", "]")):
        start, end = cleaned.find(opener), cleaned.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(cleaned[start:end + 1])
            except Exception:
                continue
    return None


def complete_json(prompt, max_tokens=1200, temperature=0.1, prefer=None):
    """complete() + tolerant JSON parsing. Returns parsed object or None."""
    return extract_json(complete(prompt, max_tokens, temperature, prefer=prefer))


def _transcribe_local(audio_path):
    """Offline fallback: faster-whisper on CPU if installed. Returns text or None."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return None
    try:
        segments, _ = WhisperModel("base.en", device="cpu", compute_type="int8").transcribe(str(audio_path))
        return " ".join(s.text.strip() for s in segments).strip() or None
    except Exception as exc:
        _last_error["ollama"] = f"local whisper: {str(exc)[:160]}"
        return None


def transcribe(audio_path):
    """Transcribe audio via Groq Whisper (free tier), else locally (faster-whisper)."""
    if not GROQ_API_KEY:
        return _transcribe_local(audio_path)
    import httpx

    try:
        with open(audio_path, "rb") as handle:
            resp = httpx.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                files={"file": (str(audio_path), handle, "application/octet-stream")},
                data={"model": WHISPER_MODEL, "response_format": "json"},
                timeout=120.0,
            )
        if resp.status_code == 200:
            return (resp.json().get("text") or "").strip()
        _last_error["groq"] = f"whisper: HTTP {resp.status_code} {resp.text[:120]}"
    except Exception as exc:
        _last_error["groq"] = f"whisper: {str(exc)[:160]}"
    return _transcribe_local(audio_path)


HEALTH_PROBE_TIMEOUT = 5.0


def health():
    """Probe each provider with a trivial prompt (in parallel). Used by `friday doctor` and `--health`."""
    from concurrent.futures import ThreadPoolExecutor

    probe = "Reply with the single word: OK"

    def _probe(name, key, fn):
        if not key:
            return name, {"ok": False, "model": None, "error": "no API key"}
        text = fn(probe, 16, 0.0)
        return name, {"ok": bool(text), "model": _working[name], "error": "" if text else _last_error[name]}

    pool = ThreadPoolExecutor(max_workers=3)
    futures = {"gemini": pool.submit(_probe, "gemini", GEMINI_API_KEY, _try_gemini),
               "groq": pool.submit(_probe, "groq", GROQ_API_KEY, _try_groq)}
    if OLLAMA_ENABLED:
        futures["ollama"] = pool.submit(_probe, "ollama", True, _try_ollama)
    report = {}
    for name, fut in futures.items():
        try:
            report[name] = fut.result(timeout=HEALTH_PROBE_TIMEOUT)[1]
        except Exception:  # noqa: BLE001 - timeout or probe crash: report, never hang
            report[name] = {"ok": False, "model": None, "error": f"probe exceeded {HEALTH_PROBE_TIMEOUT}s"}
    pool.shutdown(wait=False)  # a slow provider must not block the health report

    report["any"] = any(v["ok"] for v in report.values())
    return report
