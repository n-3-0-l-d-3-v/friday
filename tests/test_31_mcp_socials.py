import asyncio

from friday import ideas, mcp_server

BODY = "Consistent hashing maps keys and nodes onto a ring so adding a node only moves a slice of keys. " * 6


def _call(name, args):
    return asyncio.run(mcp_server.server.call_tool(name, args)).content[0].text


def _vault(tmp_path, monkeypatch):
    import friday.config
    monkeypatch.setattr(friday.config, "REPO_PATH", tmp_path)
    p = tmp_path / "09-system-design" / "ch.md"
    p.parent.mkdir(parents=True)
    from datetime import date
    p.write_text(f"---\ntitle: \"Consistent Hashing\"\ndate: {date.today()}\n---\n{BODY}\n", encoding="utf-8")


def test_tools_registered():
    names = {t.name for t in asyncio.run(mcp_server.server.list_tools())}
    assert {"content_ideas", "content_calendar"} <= names


def test_content_ideas_grounds_and_dry_run_writes_nothing(tmp_path, monkeypatch):
    _vault(tmp_path, monkeypatch)
    monkeypatch.setattr(ideas, "generate", lambda *a, **k: {"ideas": [
        {"title": "Hash rings", "angle": "why", "platform": "blog", "sources": ["N1"]},
        {"title": "Fake", "angle": "x", "platform": "blog", "sources": ["N9"]}]})
    out = _call("content_ideas", {"dry_run": True})
    assert "Hash rings" in out and "Fake" not in out and "Saved" not in out
    assert not (tmp_path / "Socials").exists()
    out = _call("content_ideas", {})
    assert "Saved (status: draft)" in out and list((tmp_path / "Socials").glob("ideas-*.md"))


def test_content_ideas_reports_thin_week(tmp_path, monkeypatch):
    import friday.config
    monkeypatch.setattr(friday.config, "REPO_PATH", tmp_path)
    assert _call("content_ideas", {}).startswith("Error:")


def test_content_calendar(tmp_path, monkeypatch):
    _vault(tmp_path, monkeypatch)
    (tmp_path / "Socials").mkdir()
    (tmp_path / "Socials" / "a.md").write_text("---\ntype: social\nplatform: blog\nstatus: draft\npublish_on: 2026-10-01\n---\n", encoding="utf-8")
    assert "[[a]]" in _call("content_calendar", {})
