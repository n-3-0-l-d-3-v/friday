"""Content calendar: one view of every post in <vault>/Socials/.

Reads each post's frontmatter (`platform`, `status`, `publish_on`) and
groups it: scheduled (dated, oldest first, overdue flagged), unscheduled
drafts, and posted. Read-only unless written to `Socials/Calendar.md`,
which is generated (marked as such) and skipped when reading. Posting
stays manual -- set `status: posted` yourself after you publish.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

CALENDAR_FILE = "Calendar.md"
_FIELD = re.compile(r"^(\w+):[ \t]*(.*?)[ \t]*$", re.MULTILINE)


@dataclass
class Post:
    name: str
    platform: str
    status: str
    publish_on: date | None


def _frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    return {k.lower(): v.strip().strip("\"'") for k, v in _FIELD.findall(text[3:end])}


def load_posts(vault: Path) -> list[Post]:
    posts: list[Post] = []
    folder = vault / "Socials"
    if not folder.is_dir():
        return posts
    for p in sorted(folder.glob("*.md")):
        if p.name == CALENDAR_FILE:
            continue
        fm = _frontmatter(p.read_text(encoding="utf-8", errors="replace"))
        if fm.get("type") != "social":
            continue
        try:
            when = date.fromisoformat(fm.get("publish_on", "")[:10])
        except ValueError:
            when = None
        posts.append(Post(p.stem, fm.get("platform") or "?", (fm.get("status") or "draft").lower(), when))
    return posts


def render(posts: list[Post], today: date | None = None) -> str:
    today = today or date.today()
    scheduled = sorted((p for p in posts if p.publish_on and p.status != "posted"), key=lambda p: (p.publish_on, p.name))
    drafts = [p for p in posts if not p.publish_on and p.status != "posted"]
    posted = sorted((p for p in posts if p.status == "posted"), key=lambda p: (p.publish_on or date.min), reverse=True)
    out = ["---", "type: social-calendar", "generated: true", "---",
           f"# Content calendar (generated {today.isoformat()} by `friday calendar`)", ""]

    out += ["## Scheduled", ""]
    if scheduled:
        out += ["| Date | Platform | Post | Status |", "|---|---|---|---|"]
        for p in scheduled:
            flag = " **overdue**" if p.publish_on < today else ""
            out.append(f"| {p.publish_on.isoformat()}{flag} | {p.platform} | [[{p.name}]] | {p.status} |")
    else:
        out.append("_Nothing scheduled. Set `publish_on: YYYY-MM-DD` in a draft's frontmatter._")

    out += ["", f"## Drafts without a date ({len(drafts)})", ""]
    out += [f"- [[{p.name}]] ({p.platform})" for p in drafts] or ["_None._"]
    out += ["", f"## Posted ({len(posted)})", ""]
    out += [f"- {p.publish_on.isoformat() if p.publish_on else '?'} [[{p.name}]] ({p.platform})" for p in posted] or ["_None yet._"]
    return "\n".join(out) + "\n"


def write(vault: Path, content: str) -> Path:
    path = vault / "Socials" / CALENDAR_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path
