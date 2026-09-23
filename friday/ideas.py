"""Weekly content ideas from the notes you captured this week.

The LOCAL model (127.0.0.1) only proposes; code grounds the result:
every idea must cite at least one real note from this week's list (ids
the model invents are dropped), platforms are schema-forced, and the
output is a `status: draft` ideas note in <vault>/Socials/ -- nothing is
posted. Optionally `friday ideas --draft N` turns the top N ideas into
full drafts through the existing `friday draft` pipeline.
"""
from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from friday.drafts import DEFAULT_MODEL, OLLAMA, STYLES, DraftError

SKIP_DIRS = {"agents", "Daily", "daily-logs", "System", "Socials", "wiki", "00-meta",
             "weekly-summaries", "templates", "Templates"}
MIN_TOTAL_CHARS = 400
EXCERPT_CHARS = 700
MAX_NOTES = 25

_DATE_RE = re.compile(r"^date:\s*[\"']?(\d{4}-\d{2}-\d{2})", re.MULTILINE)
_TITLE_RE = re.compile(r"^title:\s*[\"']?(.+?)[\"']?\s*$", re.MULTILINE)


class IdeasError(Exception):
    pass


@dataclass
class Note:
    id: str
    path: Path
    rel: str
    title: str
    when: date
    body: str


@dataclass
class Idea:
    title: str
    angle: str
    platform: str
    sources: list[Note] = field(default_factory=list)


def _split_frontmatter(text: str) -> tuple[str, str]:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[3:end], text[end + 4:]
    return "", text


def _note_date(front: str, path: Path) -> date:
    m = _DATE_RE.search(front)
    if m:
        try:
            return date.fromisoformat(m.group(1))
        except ValueError:
            pass
    return datetime.fromtimestamp(path.stat().st_mtime).date()


def recent_notes(vault: Path, days: int = 7, today: date | None = None) -> list[Note]:
    """Knowledge notes dated (frontmatter `date:`, else mtime) within the
    last `days` days. Agent output, daily logs, templates and socials are
    excluded; root-level files (Home.md, README) too."""
    today = today or date.today()
    since = today - timedelta(days=days - 1)
    notes: list[Note] = []
    for p in sorted(vault.rglob("*.md")):
        rel = p.relative_to(vault)
        parts = rel.parts
        if len(parts) < 2 or parts[0].startswith(".") or parts[0] in SKIP_DIRS:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        front, body = _split_frontmatter(text)
        when = _note_date(front, p)
        if not (since <= when <= today):
            continue
        m = _TITLE_RE.search(front)
        stem = p.parent.name if p.stem.lower() in ("readme", "index") else p.stem
        title = m.group(1).strip() if m else stem.replace("-", " ").title()
        notes.append(Note("", p, rel.as_posix(), title, when, body.strip()))
    notes.sort(key=lambda n: (n.when, n.rel), reverse=True)
    notes = notes[:MAX_NOTES]
    for i, n in enumerate(notes, 1):
        n.id = f"N{i}"
    return notes


def schema(count: int) -> dict:
    return {
        "type": "object",
        "properties": {"ideas": {"type": "array", "maxItems": count, "items": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "angle": {"type": "string"},
                "platform": {"type": "string", "enum": sorted(STYLES)},
                "sources": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["title", "angle", "platform", "sources"],
        }}},
        "required": ["ideas"],
    }


def build_prompt(notes: list[Note], count: int) -> str:
    if not notes:
        raise IdeasError("no notes captured in this window -- nothing to build ideas from")
    if sum(len(n.body) for n in notes) < MIN_TOTAL_CHARS:
        raise IdeasError(f"this window's notes are too thin (<{MIN_TOTAL_CHARS} chars total) to suggest ideas without inventing content")
    listing = "\n\n".join(f"[{n.id}] {n.title} ({n.rel})\n{n.body[:EXCERPT_CHARS]}" for n in notes)
    return (
        f"Suggest up to {count} post ideas for a developer who is learning in public, based ONLY on the notes below. "
        "Each idea: a specific title, a one-sentence angle (what the reader learns), the best platform "
        f"({', '.join(sorted(STYLES))}), and `sources`: the [N#] ids of the notes it draws on. "
        "Prefer ideas that combine related notes. Do not invent projects, results, numbers or experiences "
        "that are not in the notes. Skip notes that are not about something the author learned "
        "(e.g. music videos, placeholders).\n\nNOTES:\n" + listing
    )


def generate(prompt: str, count: int, model: str = DEFAULT_MODEL, host: str = OLLAMA, timeout: float = 300) -> dict:
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False,
                       "format": schema(count), "options": {"temperature": 0.4}}).encode()
    req = urllib.request.Request(f"{host}/api/chat", data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(json.loads(r.read())["message"]["content"])
    except Exception as exc:  # noqa: BLE001
        raise IdeasError(f"local model unavailable or returned invalid JSON: {exc}") from exc


def ground(raw: dict, notes: list[Note], count: int) -> list[Idea]:
    """Keep only well-formed ideas whose sources are real note ids."""
    by_id = {n.id: n for n in notes}
    ideas: list[Idea] = []
    seen: set[str] = set()
    used: set[str] = set()
    for item in (raw or {}).get("ideas", []) if isinstance(raw, dict) else []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        angle = str(item.get("angle", "")).strip()
        platform = str(item.get("platform", "")).strip().lower()
        ids = [str(s).strip().strip("[]") for s in item.get("sources", []) if isinstance(s, (str, int))]
        sources = [by_id[i] for i in dict.fromkeys(ids) if i in by_id]
        if not title or not sources or platform not in STYLES or title.lower() in seen:
            continue
        if all(n.id in used for n in sources):  # nothing new: a rehash of an earlier idea
            continue
        seen.add(title.lower())
        used.update(n.id for n in sources)
        ideas.append(Idea(title, angle, platform, sources))
        if len(ideas) >= count:
            break
    return ideas


def iso_week(d: date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def render(ideas: list[Idea], notes: list[Note], days: int, today: date) -> str:
    lines = ["---", "type: social-ideas", "status: draft", f"week: {iso_week(today)}",
             f"generated: {today.isoformat()}", f"window_days: {days}", "---",
             f"# Content ideas -- {iso_week(today)}", "",
             f"From {len(notes)} note(s) captured in the last {days} day(s). Suggestions only: pick, edit, or ignore.", ""]
    for i, idea in enumerate(ideas, 1):
        lines.append(f"## {i}. {idea.title}")
        lines.append(f"- Platform: {idea.platform}")
        if idea.angle:
            lines.append(f"- Angle: {idea.angle}")
        lines.append("- Sources: " + ", ".join(f"[[{n.rel[:-3]}|{n.title}]]" for n in idea.sources))
        lines.append(f'- Draft it: `friday draft {idea.platform} "{idea.sources[0].path}"`')
        lines.append("")
    return "\n".join(lines)


def write_ideas(vault: Path, content: str, today: date) -> Path:
    out = vault / "Socials"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"ideas-{iso_week(today)}.md"
    path.write_text(content, encoding="utf-8")
    return path


def draft_from_idea(vault: Path, idea: Idea, model: str, today: date) -> tuple[Path, list[str]]:
    """Full draft via the `friday draft` pipeline, sourced from the idea's notes."""
    from friday import drafts

    source = "\n\n".join(n.body for n in idea.sources)
    try:
        body = drafts.generate(drafts.build_prompt(idea.platform, f"Post idea: {idea.title}. {idea.angle}\n\n{source}"), model)
    except DraftError as exc:
        raise IdeasError(str(exc)) from exc
    flagged = drafts.ungrounded_numbers(source, body)
    if flagged:
        body += "\n\n> REVIEW: numbers not found in the source notes (verify or delete): " + ", ".join(flagged)
    src = ", ".join(n.path.name for n in idea.sources)
    return drafts.write_draft(vault, idea.platform, idea.title, body, src, today), flagged
