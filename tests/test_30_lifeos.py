from datetime import date

import pytest

from friday import lifeos

TPL = """---
type: daily
date: <% tp.date.now("YYYY-MM-DD") %>
deepwork: false
dsa: false
---
# <% tp.date.now("dddd, MMM D") %>
Week <% tp.date.now("YYYY-[W]WW") %>, yesterday <% tp.date.now("YYYY-MM-DD", -1) %>
<% tp.system.prompt("x") %>
"""
DAY = date(2026, 9, 7)  # a Monday


def _vault(tmp_path, tpl=TPL):
    (tmp_path / "System/Templates").mkdir(parents=True)
    (tmp_path / "System/Templates/daily.md").write_text(tpl, encoding="utf-8")
    return tmp_path


def test_moment_formats():
    assert lifeos.format_moment("YYYY-MM-DD", DAY) == "2026-09-07"
    assert lifeos.format_moment("dddd, MMM D", DAY) == "Monday, Sep 7"
    assert lifeos.format_moment("YYYY-[W]WW", DAY) == "2026-W37"


def test_template_rendered_and_unknown_calls_left_for_obsidian(tmp_path):
    path, created = lifeos.ensure_today(_vault(tmp_path), DAY)
    text = path.read_text(encoding="utf-8")
    assert created and path.name == "2026-09-07.md"
    assert "date: 2026-09-07" in text and "# Monday, Sep 7" in text and "yesterday 2026-09-06" in text
    assert '<% tp.system.prompt("x") %>' in text


def test_existing_note_is_not_overwritten(tmp_path):
    v = _vault(tmp_path)
    p, _ = lifeos.ensure_today(v, DAY)
    p.write_text(p.read_text() + "my writing", encoding="utf-8")
    assert lifeos.ensure_today(v, DAY) == (p, False) and "my writing" in p.read_text()


def test_habits_and_streaks(tmp_path):
    v = _vault(tmp_path)
    for d in (date(2026, 9, 5), date(2026, 9, 6), DAY):
        lifeos.set_habit(v, "dsa", True, d)
    lifeos.set_habit(v, "music", True, DAY)  # new key appended
    s = lifeos.streaks(v, habits=("dsa", "music", "deepwork"), today=DAY)
    assert s == {"dsa": 3, "music": 1, "deepwork": 0}
    assert "music: true" in lifeos.daily_path(v, DAY).read_text()


def test_streak_counts_from_yesterday_if_today_not_ticked(tmp_path):
    v = _vault(tmp_path)
    lifeos.set_habit(v, "dsa", True, date(2026, 9, 6))
    lifeos.ensure_today(v, DAY)
    assert lifeos.streaks(v, habits=("dsa",), today=DAY) == {"dsa": 1}


def test_bad_habit_name_rejected(tmp_path):
    with pytest.raises(lifeos.LifeOSError):
        lifeos.set_habit(_vault(tmp_path), "Rm -rf", True, DAY)


def test_no_template_falls_back_to_default(tmp_path):
    p, _ = lifeos.ensure_today(tmp_path, DAY)
    assert "deepwork: false" in p.read_text()
