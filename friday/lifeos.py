"""LifeOS daily notes from the terminal: create today's note from the vault's
Templater template and tick habits in its frontmatter (which drives the
streak table on Home.md).

Only the Templater calls the vault templates use are rendered here
(`tp.date.now(fmt[, offset_days])` and `tp.file.title`); anything else is
left untouched for Obsidian's Templater to handle when the note is opened.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

TEMPLATE = Path("System") / "Templates" / "daily.md"
DAILY_DIR = "Daily"
DEFAULT_HABITS = ("deepwork", "dsa", "workout", "music", "writing")

_TOKENS = [
    ("YYYY", lambda d: f"{d.year:04d}"),
    ("dddd", lambda d: d.strftime("%A")),
    ("ddd", lambda d: d.strftime("%a")),
    ("MMMM", lambda d: d.strftime("%B")),
    ("MMM", lambda d: d.strftime("%b")),
    ("MM", lambda d: f"{d.month:02d}"),
    ("DD", lambda d: f"{d.day:02d}"),
    ("WW", lambda d: f"{d.isocalendar()[1]:02d}"),
    ("D", lambda d: str(d.day)),
    ("M", lambda d: str(d.month)),
]


class LifeOSError(Exception):
    pass


def format_moment(fmt: str, d: date) -> str:
    """Render the subset of moment.js tokens the templates use. [text] is literal."""
    out = []
    for part in re.split(r"(\[[^\]]*\])", fmt):
        if part.startswith("[") and part.endswith("]"):
            out.append(part[1:-1])
            continue
        i = 0
        while i < len(part):
            for tok, fn in _TOKENS:
                if part.startswith(tok, i):
                    out.append(fn(d))
                    i += len(tok)
                    break
            else:
                out.append(part[i])
                i += 1
    return "".join(out)


_CALL = re.compile(r"<%\s*(.*?)\s*%>", re.DOTALL)
_NOW = re.compile(r"""tp\.date\.now\(\s*["']([^"']*)["']\s*(?:,\s*(-?\d+)\s*)?\)$""")


def render_template(text: str, today: date, title: str) -> str:
    def repl(m: re.Match) -> str:
        expr = m.group(1)
        now = _NOW.match(expr)
        if now:
            return format_moment(now.group(1), today + timedelta(days=int(now.group(2) or 0)))
        if expr == "tp.file.title":
            return title
        return m.group(0)  # leave for Obsidian Templater

    return _CALL.sub(repl, text)


def daily_path(vault: Path, d: date) -> Path:
    return vault / DAILY_DIR / f"{d.isoformat()}.md"


def ensure_today(vault: Path, today: Optional[date] = None) -> tuple[Path, bool]:
    """Create today's daily note from the template if missing. Returns (path, created)."""
    today = today or date.today()
    path = daily_path(vault, today)
    if path.exists():
        return path, False
    tpl = vault / TEMPLATE
    if tpl.exists():
        body = render_template(tpl.read_text(encoding="utf-8"), today, today.isoformat())
    else:
        flags = "\n".join(f"{h}: false" for h in DEFAULT_HABITS)
        body = f"---\ntype: daily\ndate: {today.isoformat()}\n{flags}\n---\n# {today:%A, %b} {today.day}\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path, True


def set_habit(vault: Path, habit: str, value: bool = True, today: Optional[date] = None) -> Path:
    """Set `habit: true|false` in today's note frontmatter (creating the note if needed)."""
    if not re.fullmatch(r"[a-z][a-z0-9_-]{0,30}", habit):
        raise LifeOSError("habit names are lowercase words, e.g. deepwork")
    path, _ = ensure_today(vault, today)
    text = path.read_text(encoding="utf-8")
    m = re.match(r"\A---\r?\n(.*?)\r?\n---", text, re.DOTALL)
    if not m:
        raise LifeOSError(f"{path} has no frontmatter to record habits in")
    fm = m.group(1)
    line = f"{habit}: {'true' if value else 'false'}"
    if re.search(rf"^{re.escape(habit)}:", fm, re.MULTILINE):
        fm2 = re.sub(rf"^{re.escape(habit)}:.*$", line, fm, count=1, flags=re.MULTILINE)
    else:
        fm2 = fm + "\n" + line
    path.write_text(text[: m.start(1)] + fm2 + text[m.end(1):], encoding="utf-8")
    return path


def streaks(vault: Path, habits=DEFAULT_HABITS, today: Optional[date] = None) -> dict[str, int]:
    """Consecutive days (ending today, or yesterday if today isn't ticked yet) per habit."""
    today = today or date.today()
    out = {}
    for h in habits:
        d, n = today, 0
        if not _done(vault, d, h):
            d -= timedelta(days=1)
        while _done(vault, d, h):
            n += 1
            d -= timedelta(days=1)
        out[h] = n
    return out


def _done(vault: Path, d: date, habit: str) -> bool:
    p = daily_path(vault, d)
    if not p.exists():
        return False
    return bool(re.search(rf"^{re.escape(habit)}:\s*true\s*$", p.read_text(encoding="utf-8"), re.MULTILINE))
