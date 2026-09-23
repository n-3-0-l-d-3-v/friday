from datetime import date

import pytest
from click.testing import CliRunner

from friday import ideas

TODAY = date(2026, 9, 23)
_orig = ideas.recent_notes
BODY = "Consistent hashing maps keys and nodes onto a ring so adding a node only moves a slice of keys. " * 3


def _note(vault, rel, when, body=BODY, title=None):
    p = vault / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    fm = f"---\ntitle: \"{title or p.stem}\"\ndate: {when}\n---\n" if when else ""
    p.write_text(f"{fm}# {p.stem}\n\n{body}\n", encoding="utf-8")
    return p


@pytest.fixture
def vault(tmp_path):
    _note(tmp_path, "09-system-design/ch.md", "2026-09-20", title="Consistent Hashing")
    _note(tmp_path, "05-devops/docker.md", "2026-09-23")
    _note(tmp_path, "05-devops/old.md", "2026-09-01")               # outside window
    _note(tmp_path, "agents/Wall-E/report.md", "2026-09-22")        # agent output
    _note(tmp_path, "Socials/2026-09-22-blog-x.md", "2026-09-22")   # own output
    _note(tmp_path, "Home.md", "2026-09-22")                        # root file
    return tmp_path


def test_recent_notes_window_and_exclusions(vault):
    notes = ideas.recent_notes(vault, 7, TODAY)
    assert [n.rel for n in notes] == ["05-devops/docker.md", "09-system-design/ch.md"]
    assert [n.id for n in notes] == ["N1", "N2"]
    assert notes[1].title == "Consistent Hashing"


def test_readme_notes_are_titled_by_folder(tmp_path):
    p = tmp_path / "09-system-design" / "availability" / "README.md"
    p.parent.mkdir(parents=True)
    p.write_text("# x " + BODY, encoding="utf-8")
    assert ideas.recent_notes(tmp_path, 7)[0].title == "Availability"


def test_build_prompt_refuses_empty_and_thin_weeks(vault):
    with pytest.raises(ideas.IdeasError):
        ideas.build_prompt([], 5)
    thin = [ideas.Note("N1", vault / "a.md", "a.md", "a", TODAY, "tiny")]
    with pytest.raises(ideas.IdeasError):
        ideas.build_prompt(thin, 5)
    p = ideas.build_prompt(ideas.recent_notes(vault, 7, TODAY), 3)
    assert "[N2] Consistent Hashing" in p and "up to 3" in p


def test_prompt_stays_within_budget_for_a_full_week(tmp_path):
    notes = [ideas.Note(f"N{i}", tmp_path / "a.md", "a.md", "t", TODAY, "word " * 400) for i in range(ideas.MAX_NOTES)]
    assert len(ideas.build_prompt(notes, 5)) < ideas.LISTING_BUDGET + 2500


def test_ground_drops_invented_sources_bad_platforms_and_duplicates(vault):
    notes = ideas.recent_notes(vault, 7, TODAY)
    raw = {"ideas": [
        {"title": "Hash rings", "angle": "why", "platform": "blog", "sources": ["N2", "N9", "[N2]"]},
        {"title": "Invented", "angle": "x", "platform": "blog", "sources": ["N7"]},
        {"title": "Myspace", "angle": "x", "platform": "myspace", "sources": ["N1"]},
        {"title": "hash RINGS", "angle": "dup", "platform": "thread", "sources": ["N1"]},
        {"title": "Docker basics", "angle": "", "platform": "LinkedIn", "sources": ["N1"]},
        {"title": "Rehash", "angle": "", "platform": "blog", "sources": ["N1", "N2"]},
        "garbage",
    ]}
    got = ideas.ground(raw, notes, 5)
    assert [(i.title, i.platform, [s.id for s in i.sources]) for i in got] == [
        ("Hash rings", "blog", ["N2"]), ("Docker basics", "linkedin", ["N1"])]
    assert ideas.ground({"ideas": []}, notes, 5) == [] and ideas.ground(None, notes, 5) == []
    assert len(ideas.ground(raw, notes, 1)) == 1


def test_render_and_write_are_draft_with_real_wikilinks(vault):
    notes = ideas.recent_notes(vault, 7, TODAY)
    got = ideas.ground({"ideas": [{"title": "Hash rings", "angle": "a", "platform": "blog", "sources": ["N2"]}]}, notes, 5)
    path = ideas.write_ideas(vault, ideas.render(got, notes, 7, TODAY), TODAY)
    text = path.read_text(encoding="utf-8")
    assert path.name == "ideas-2026-W39.md" and path.parent.name == "Socials"
    assert "status: draft" in text and "[[09-system-design/ch|Consistent Hashing]]" in text
    assert "friday draft blog" in text


def test_generate_wraps_connection_errors():
    with pytest.raises(ideas.IdeasError):
        ideas.generate("hi", 3, host="http://127.0.0.1:1", timeout=1)


def test_cli_dry_run_and_grounded_write(vault, monkeypatch):
    from friday.cli import cli

    monkeypatch.setenv("VAULT_PATH", str(vault))
    monkeypatch.setattr(ideas, "recent_notes", lambda v, d, t: _orig(v, d, TODAY))
    r = CliRunner().invoke(cli, ["ideas", "--dry-run"])
    assert r.exit_code == 0 and "09-system-design/ch.md" in r.output

    monkeypatch.setattr(ideas, "generate", lambda *a, **k: {"ideas": [
        {"title": "Hash rings", "angle": "a", "platform": "thread", "sources": ["N2"]},
        {"title": "Fake", "angle": "a", "platform": "blog", "sources": ["N99"]}]})
    r = CliRunner().invoke(cli, ["ideas"])
    assert r.exit_code == 0, r.output
    assert "1 idea(s) saved" in r.output and "Fake" not in r.output
    assert list((vault / "Socials").glob("ideas-*.md"))

    monkeypatch.setattr(ideas, "generate", lambda *a, **k: {"ideas": [{"title": "Fake", "angle": "a", "platform": "blog", "sources": ["N99"]}]})
    r = CliRunner().invoke(cli, ["ideas"])
    assert r.exit_code != 0 and "nothing written" in r.output

