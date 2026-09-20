"""Draft social/blog posts from a vault note with the LOCAL Ollama model.

Never publishes: output is a `status: draft` note in <vault>/Socials/ for the
user to review and post by hand. Local-only (127.0.0.1), so private notes
never leave the machine.
"""
from __future__ import annotations

import json
import re
import urllib.request
from datetime import date
from pathlib import Path

OLLAMA = "http://127.0.0.1:11434"
DEFAULT_MODEL = "qwen2.5:7b"
MIN_SOURCE_CHARS = 200

STYLES = {
    "linkedin": "a LinkedIn post: hook line, 3-5 short paragraphs, one concrete lesson, max 1300 characters, no hashtags spam (max 3).",
    "blog": "a developer blog post in Markdown: title, intro, 3 headed sections, short conclusion, ~500 words.",
    "devto": "a Dev.to article in Markdown: title, TL;DR, headed sections with code where relevant, ~600 words.",
    "thread": "a numbered X/Twitter thread of 5-7 posts, each under 270 characters.",
}


class DraftError(Exception):
    pass


def build_prompt(platform: str, source_text: str) -> str:
    if platform not in STYLES:
        raise DraftError(f"unknown platform {platform!r}; choose from {sorted(STYLES)}")
    if len(source_text.strip()) < MIN_SOURCE_CHARS:
        raise DraftError(f"source note too short (<{MIN_SOURCE_CHARS} chars) to draft from without inventing content")
    return (f"Write {STYLES[platform]}\nWrite it as an explainer/learning post about the TOPIC in the notes. NEVER invent personal anecdotes, projects, employers, teams, results or numbers; if the notes contain no personal story, write in an impersonal teaching voice like: Here is how X works. Use only facts present in the notes below; do not invent "
            f"achievements or numbers. First person, plain and specific, no buzzwords.\n\nSOURCE NOTES:\n{source_text[:6000]}")


def generate(prompt: str, model: str = DEFAULT_MODEL, host: str = OLLAMA, timeout: float = 300) -> str:
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False, "options": {"temperature": 0.3}}).encode()
    req = urllib.request.Request(f"{host}/api/chat", data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            text = json.loads(r.read())["message"]["content"]
    except Exception as exc:  # noqa: BLE001
        raise DraftError(f"local model unavailable: {exc}") from exc
    return text.strip()


def ungrounded_numbers(source: str, draft: str) -> list[str]:
    """Numbers in the draft that never appear in the source (likely invented)."""
    src = set(re.findall(r"\d+(?:\.\d+)?", source))
    return sorted({n for n in re.findall(r"\d+(?:\.\d+)?", draft) if n not in src})


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:50] or "post"


def write_draft(vault: Path, platform: str, title: str, body: str, source: str, today: date | None = None) -> Path:
    today = today or date.today()
    out_dir = vault / "Socials"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{today.isoformat()}-{platform}-{slug(title)}.md"
    path.write_text(f"---\ntype: social\nplatform: {platform}\nstatus: draft\npublish_on:\nsource: {source}\n---\n# {title}\n\n{body}\n", encoding="utf-8")
    return path
