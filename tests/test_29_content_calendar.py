from datetime import date

from click.testing import CliRunner

from friday import content_calendar as cc

TODAY = date(2026, 9, 23)


def _post(vault, name, **fm):
    d = vault / "Socials"
    d.mkdir(exist_ok=True)
    head = "\n".join(f"{k}: {v}" for k, v in {"type": "social", **fm}.items())
    (d / f"{name}.md").write_text(f"---\n{head}\n---\n# {name}\n", encoding="utf-8")


def test_groups_scheduled_drafts_posted_and_flags_overdue(tmp_path):
    _post(tmp_path, "late", platform="blog", status="draft", publish_on="2026-09-20")
    _post(tmp_path, "soon", platform="linkedin", status="ready", publish_on="2026-09-30")
    _post(tmp_path, "undated", platform="thread", status="draft", publish_on="")
    _post(tmp_path, "done", platform="devto", status="posted", publish_on="2026-09-01")
    _post(tmp_path, "ideas-2026-W39", status="draft")  # not type: social -> ignored below
    (tmp_path / "Socials" / "ideas-2026-W39.md").write_text("---\ntype: social-ideas\n---\n", encoding="utf-8")
    text = cc.render(cc.load_posts(tmp_path), TODAY)
    assert text.index("[[late]]") < text.index("[[soon]]")
    assert "2026-09-20 **overdue** | blog | [[late]]" in text
    assert "2026-09-30 | linkedin | [[soon]] | ready" in text
    assert "## Drafts without a date (1)" in text and "[[undated]] (thread)" in text
    assert "## Posted (1)" in text and "[[done]]" in text
    assert "ideas-2026-W39" not in text


def test_empty_vault_and_own_output_is_skipped(tmp_path):
    assert cc.load_posts(tmp_path) == []
    assert "Nothing scheduled" in cc.render([], TODAY)
    _post(tmp_path, "a", platform="blog", status="draft")
    cc.write(tmp_path, cc.render(cc.load_posts(tmp_path), TODAY))
    assert [p.name for p in cc.load_posts(tmp_path)] == ["a"]


def test_draft_written_by_friday_draft_is_picked_up(tmp_path):
    from friday import drafts
    drafts.write_draft(tmp_path, "blog", "Hash Rings", "body", "n.md", TODAY)
    posts = cc.load_posts(tmp_path)
    assert [(p.platform, p.status, p.publish_on) for p in posts] == [("blog", "draft", None)]


def test_cli_calendar_write(tmp_path, monkeypatch):
    from friday.cli import cli
    monkeypatch.setenv("VAULT_PATH", str(tmp_path))
    _post(tmp_path, "a", platform="blog", status="draft", publish_on="2026-10-01")
    r = CliRunner().invoke(cli, ["calendar", "--write"])
    assert r.exit_code == 0 and "[[a]]" in r.output
    assert (tmp_path / "Socials" / "Calendar.md").exists()
