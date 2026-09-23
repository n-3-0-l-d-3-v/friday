from pathlib import Path
import os
import warnings
from dotenv import load_dotenv

# Load .env from project root (one level above this file)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# --------------------------------------------------------------------------- #
# Backward compatibility: this project was renamed from "Jarvis" to "Friday"
# (avoiding a name collision with a separate, unrelated orchestrator agent
# planned for the wider agent ecosystem). Every env var is now FRIDAY_*, but
# anyone with an existing .env still has the old JARVIS_* names configured —
# silently breaking their setup on an internal rename is worse than reading
# both. The old names are read as a fallback and will be removed eventually.
# --------------------------------------------------------------------------- #
def _env(new_key, old_key, default=""):
    if new_key in os.environ:
        return os.environ[new_key]
    if old_key in os.environ:
        warnings.warn(
            f"{old_key} is deprecated, use {new_key} instead (Jarvis was "
            f"renamed to Friday). Support for {old_key} will be removed in "
            f"a future version.",
            DeprecationWarning,
            stacklevel=2,
        )
        return os.environ[old_key]
    return default


REPO_PATH = Path(_env("FRIDAY_REPO_PATH", "JARVIS_REPO_PATH", r"C:\Users\neilt\devNote"))

INBOX_RAW = REPO_PATH / "inbox" / "raw"
INBOX_PROCESSED = REPO_PATH / "inbox" / "processed"
INBOX_FAILED = REPO_PATH / "inbox" / "failed"
META_PATH = REPO_PATH / "00-meta"
INDEX_PATH = META_PATH / "index.json"
DAILY_LOGS_PATH = REPO_PATH / "daily-logs"

# API keys (empty by default)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROK_API_KEY = os.getenv("GROK_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
DISCORD_GUILD_ID = os.getenv("DISCORD_GUILD_ID", "")
DISCORD_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID", "")

# --------------------------------------------------------------------------- #
# AI models — the ONLY place model names live.
#
# These are lists, tried in order, because providers retire models without
# warning: `gemini-2.0-flash` and `llama-3.3-70b-versatile` both started
# returning 404 mid-2026 and silently killed the whole AI layer. The first
# entries are moving aliases that survive deprecation; the rest are pinned
# fallbacks. Override with FRIDAY_GEMINI_MODELS / FRIDAY_GROQ_MODELS (CSV).
# --------------------------------------------------------------------------- #
def _model_list(env_key, old_env_key, defaults):
    raw = _env(env_key, old_env_key, "").strip()
    if raw:
        return [m.strip() for m in raw.split(",") if m.strip()]
    return defaults


GEMINI_MODELS = _model_list("FRIDAY_GEMINI_MODELS", "JARVIS_GEMINI_MODELS", [
    "gemini-2.5-flash",        # pinned + stable; the -latest alias was slow
    "gemini-flash-latest",     # moving alias — survives deprecations
    "gemini-3-flash-preview",
    "gemini-flash-lite-latest",
])

GROQ_MODELS = _model_list("FRIDAY_GROQ_MODELS", "JARVIS_GROQ_MODELS", [
    "qwen/qwen3.8-27b",        # verified fast (~2s) on the free tier
    "qwen/qwen3.6-27b",
    "openai/gpt-oss-20b",
    "groq/compound",
])

# Which provider to try first. Groq is the default because it answered in ~2s
# in testing while the Gemini alias hit a 45s deadline. Set to "gemini" to flip.
AI_PRIMARY = _env("FRIDAY_AI_PRIMARY", "JARVIS_AI_PRIMARY", "groq").strip().lower()

# Free speech-to-text on Groq — powers `friday listen`.
# Local model (free, private, works offline and when cloud quotas are exhausted).
# Always tried as the last-resort provider unless FRIDAY_OLLAMA=false; set
# FRIDAY_AI_PRIMARY=ollama to use it first.
OLLAMA_ENABLED = os.getenv("FRIDAY_OLLAMA", "true").strip().lower() not in {"false", "0", "no"}
OLLAMA_HOST = os.getenv("FRIDAY_OLLAMA_HOST", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("FRIDAY_OLLAMA_MODEL", "qwen2.5:7b")

WHISPER_MODEL = _env("FRIDAY_WHISPER_MODEL", "JARVIS_WHISPER_MODEL", "whisper-large-v3-turbo")

# Note style. Lean notes keep only the sections that actually carry content,
# instead of a 10-section scaffold that is mostly empty placeholders.
# Set FRIDAY_LEAN_NOTES=false (or pass `friday note --full`) for the rich template.
LEAN_NOTES = _env("FRIDAY_LEAN_NOTES", "JARVIS_LEAN_NOTES", "true").strip().lower() not in {"false", "0", "no"}

# --------------------------------------------------------------------------- #
# personal-token tier guarantee (see agent.yaml, README "Agent contract").
#
# Friday is a personal-token-tier agent: it authenticates to AI providers with
# the user's OWN Groq/Gemini keys, never a shared/free-tier credential pool
# meant for generic work-tier tasks. There is exactly one place credentials
# enter the process (the two GROQ_API_KEY / GEMINI_API_KEY reads below), and
# this assertion is the guarantee that nothing has been swapped in a shared
# pool's name (e.g. "GROQ_SHARED_POOL_KEY", "WORK_TIER_API_KEY") instead.
# --------------------------------------------------------------------------- #
_SHARED_POOL_MARKERS = ("SHARED_POOL", "WORK_TIER", "FLEET_KEY", "POOL_TOKEN")


def assert_personal_token_tier():
    """Raise if any provider credential env var looks like a shared/fleet pool key.

    This does not (and cannot) prove a key is personal — it can only catch the
    obvious failure mode of someone wiring a shared-pool variable in by name.
    Called from `friday --health` and available for callers/tests that want a
    hard guarantee before making a provider call.
    """
    offenders = [k for k in os.environ if any(m in k.upper() for m in _SHARED_POOL_MARKERS)
                 and ("GROQ" in k.upper() or "GEMINI" in k.upper() or "FRIDAY" in k.upper())]
    if offenders:
        raise RuntimeError(
            "personal-token tier violation: Friday must authenticate with the "
            f"user's own provider keys, not a shared pool. Suspicious env var(s): "
            f"{', '.join(offenders)}"
        )
    return True

# Ensure directories exist
for p in (INBOX_RAW, INBOX_PROCESSED, INBOX_FAILED, META_PATH, DAILY_LOGS_PATH):
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
