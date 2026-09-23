"""Local Ollama provider: ordering, fallback when cloud providers fail, and opt-out."""

import friday.ai as AI


def test_order_puts_local_model_last_by_default():
    assert AI.provider_order("groq") == ["groq", "gemini", "ollama"]
    assert AI.provider_order("gemini") == ["gemini", "groq", "ollama"]


def test_order_local_first_when_primary():
    assert AI.provider_order("ollama") == ["ollama", "groq", "gemini"]


def test_unknown_primary_falls_back_to_groq():
    assert AI.provider_order("skynet")[0] == "groq"


def test_cloud_failure_falls_through_to_local(monkeypatch):
    monkeypatch.setattr(AI, "_try_groq", lambda p, m, t: None)
    monkeypatch.setattr(AI, "_try_gemini", lambda p, m, t: None)
    monkeypatch.setattr(AI, "_try_ollama", lambda p, m, t: "local answer")
    assert AI.complete("hi", retries=0) == "local answer"


def test_disabled_local_model_is_skipped(monkeypatch):
    # conftest disables OLLAMA_ENABLED; the real function must return None without network
    assert AI._try_ollama("hi", 10, 0.0) is None


def test_local_provider_parses_ollama_response(monkeypatch):
    import io
    import json

    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(AI, "OLLAMA_ENABLED", True)
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda req, timeout=0: _Resp(json.dumps({"message": {"content": " ok "}}).encode()))
    assert AI._try_ollama("hi", 10, 0.0) == "ok"
    assert AI._working["ollama"] == AI.OLLAMA_MODEL
