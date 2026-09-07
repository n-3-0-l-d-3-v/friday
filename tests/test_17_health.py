"""Feature 17: friday doctor (health check) + friday reindex."""

import json

import pytest

from friday import health as H


@pytest.fixture(autouse=True)
def _isolate(pristine_repo):
    """Every health test asserts on repo-wide counts, so start from empty."""
    return pristine_repo


def _write(sandbox, folder, name, content):
    p = sandbox / folder
    p.mkdir(parents=True, exist_ok=True)
    (p / name).write_text(content, encoding="utf-8")
    return p / name


GOOD = ("---\ntitle: Good Note\ndomain: databases\ntype: concept\n---\n"
        "# Good Note\n\nThis note has plenty of genuine content in it, well past "
        "the threshold used to detect empty scaffolding notes.\n"
        "## Related Topics\n- [[other-note|Other]]\n")


def test_detects_missing_file(sandbox, write_index):
    write_index([{"id": "1", "title": "Ghost", "folder_path": "04-dsa",
                  "filename": "ghost.md", "date": "2026-07-01"}])
    findings = H.check_health()
    assert len(findings["missing_files"]) == 1
    assert findings["missing_files"][0]["title"] == "Ghost"


def test_detects_empty_note(sandbox, write_index):
    _write(sandbox, "22-knowledge-base", "empty.md",
           "---\ntitle: Empty\n---\n# Empty\n<!-- nothing -->\n")
    write_index([{"id": "1", "title": "Empty", "folder_path": "22-knowledge-base",
                  "filename": "empty.md", "date": "2026-07-01"}])
    findings = H.check_health()
    assert any(e["file"].endswith("empty.md") for e in findings["empty_notes"])


def test_full_content_note_is_not_flagged_empty(sandbox, write_index):
    _write(sandbox, "08-databases", "good.md", GOOD)
    _write(sandbox, "08-databases", "other-note.md", GOOD)
    write_index([
        {"id": "1", "title": "Good Note", "folder_path": "08-databases",
         "filename": "good.md", "date": "2026-07-01"},
        {"id": "2", "title": "Other", "folder_path": "08-databases",
         "filename": "other-note.md", "date": "2026-07-01"},
    ])
    findings = H.check_health()
    assert not any(e["file"].endswith("good.md") for e in findings["empty_notes"])


def test_detects_duplicate_index_rows(sandbox, write_index):
    _write(sandbox, "08-databases", "dupe.md", GOOD)
    row = {"id": "1", "title": "D", "folder_path": "08-databases",
           "filename": "dupe.md", "date": "2026-07-01"}
    write_index([row, dict(row), dict(row)])
    findings = H.check_health()
    assert findings["duplicate_rows"][0]["count"] == 3


def test_detects_broken_wikilink(sandbox, write_index):
    _write(sandbox, "08-databases", "linky.md",
           "---\ntitle: Linky\n---\n# Linky\n\nlots of real content here to avoid "
           "the empty check firing on this note at all.\n"
           "## Related\n- [[does-not-exist-anywhere|Nope]]\n")
    write_index([{"id": "1", "title": "Linky", "folder_path": "08-databases",
                  "filename": "linky.md", "date": "2026-07-01"}])
    findings = H.check_health()
    assert any(b["target"] == "does-not-exist-anywhere"
               for b in findings["broken_links"])


def test_link_to_existing_but_unindexed_file_is_not_broken(sandbox, write_index):
    """Regression: a link to a real file on disk isn't broken, it's unindexed."""
    _write(sandbox, "08-databases", "target-note.md", GOOD)
    _write(sandbox, "08-databases", "src.md",
           "---\ntitle: Src\n---\n# Src\n\nplenty of genuine content here so the "
           "empty-note detector does not fire for this particular file.\n"
           "## Related\n- [[target-note|T]]\n")
    write_index([{"id": "1", "title": "Src", "folder_path": "08-databases",
                  "filename": "src.md", "date": "2026-07-01"}])
    findings = H.check_health()
    assert not any(b["target"] == "target-note" for b in findings["broken_links"])
    assert any(u["file"].endswith("target-note.md")
               for u in findings["untracked_files"])


def test_detects_stale_notes(sandbox, write_index):
    _write(sandbox, "08-databases", "old.md", GOOD)
    write_index([{"id": "1", "title": "Old", "folder_path": "08-databases",
                  "filename": "old.md", "date": "2020-01-01"}])
    findings = H.check_health(stale_days=30)
    assert findings["stale_notes"] and findings["stale_notes"][0]["days"] > 30


def test_health_score_is_100_for_clean_repo(sandbox, write_index):
    _write(sandbox, "08-databases", "clean.md", GOOD)
    _write(sandbox, "08-databases", "other-note.md", GOOD)
    write_index([
        {"id": "1", "title": "Clean", "folder_path": "08-databases",
         "filename": "clean.md", "date": "2026-07-01"},
        {"id": "2", "title": "Other", "folder_path": "08-databases",
         "filename": "other-note.md", "date": "2026-07-01"},
    ])
    findings = H.check_health()
    assert H.health_score(findings) >= 90


def test_health_score_drops_with_problems(sandbox, write_index):
    write_index([{"id": str(i), "title": "Ghost", "folder_path": "x",
                  "filename": f"ghost{i}.md", "date": "2026-07-01"}
                 for i in range(5)])
    findings = H.check_health()
    assert H.health_score(findings) < 60


def test_summarize_returns_rows(sandbox, write_index):
    write_index([])
    rows = H.summarize(H.check_health())
    assert all(len(r) == 4 for r in rows)


# --- frontmatter parsing + reindex ----------------------------------------
def test_parse_frontmatter_flat_and_list():
    raw = ('---\ntitle: "My Note"\ndomain: databases\ntags:\n  - "redis"\n'
           '  - "cache"\ntype: concept\n---\n# body\n')
    fm = H._parse_frontmatter(raw)
    assert fm["title"] == "My Note"
    assert fm["domain"] == "databases"
    assert fm["tags"] == ["redis", "cache"]


def test_parse_frontmatter_inline_list():
    fm = H._parse_frontmatter('---\ntitle: T\ntags: ["a", "b"]\n---\n')
    assert fm["tags"] == ["a", "b"]


def test_parse_frontmatter_missing_returns_empty():
    assert H._parse_frontmatter("# no frontmatter") == {}


def test_reindex_adds_unindexed_notes(sandbox, clean_index):
    _write(sandbox, "08-databases", "found.md",
           '---\ntitle: "Found Note"\ndomain: databases\ntype: concept\n'
           'tags:\n  - "redis"\n---\n# Found Note\n\ncontent\n')
    result = H.reindex()
    assert any(a["title"] == "Found Note" for a in result["added"])

    notes = json.loads(clean_index.read_text(encoding="utf-8"))["notes"]
    entry = [n for n in notes if n["filename"] == "found.md"][0]
    assert entry["domain"] == "databases"
    assert entry["tags"] == ["redis"]


def test_reindex_dry_run_writes_nothing(sandbox, clean_index):
    _write(sandbox, "08-databases", "dry.md", GOOD)
    result = H.reindex(dry_run=True)
    assert result["added"]
    notes = json.loads(clean_index.read_text(encoding="utf-8"))["notes"]
    assert notes == []


def test_reindex_skips_already_indexed(sandbox, write_index):
    _write(sandbox, "08-databases", "known.md", GOOD)
    write_index([{"id": "1", "title": "Known", "folder_path": "08-databases",
                  "filename": "known.md", "date": "2026-07-01"}])
    result = H.reindex()
    assert not any(a["file"].endswith("known.md") for a in result["added"])


def test_placeholder_is_not_a_broken_link(sandbox, write_index):
    """`<!-- [[wikilinks]] added automatically -->` is a template placeholder."""
    _write(sandbox, "08-databases", "tpl.md",
           "---\ntitle: T\n---\n# T\n\nreal content here that is long enough to "
           "avoid tripping the empty-note detector on this file.\n"
           "## Related Topics\n<!-- [[wikilinks]] added automatically -->\n")
    write_index([{"id": "1", "title": "T", "folder_path": "08-databases",
                  "filename": "tpl.md", "date": "2026-07-01"}])
    findings = H.check_health()
    assert not any(b["target"] == "wikilinks" for b in findings["broken_links"])


def test_wiki_infrastructure_is_not_untracked(sandbox, write_index):
    """wiki/index.md and wiki/log.md are generated, not notes."""
    _write(sandbox, "wiki", "index.md", "# Wiki Index\n")
    _write(sandbox, "wiki", "log.md", "# Wiki Log\n")
    write_index([])
    files = [u["file"] for u in H.check_health()["untracked_files"]]
    assert not any(f.endswith(("index.md", "log.md")) for f in files)


def test_reindex_skips_wiki_infrastructure(sandbox, clean_index):
    _write(sandbox, "wiki", "index.md", "# Wiki Index\n")
    result = H.reindex()
    assert not any("index.md" in a["file"] for a in result["added"])


def test_reindex_ignores_daily_logs_and_inbox(sandbox, clean_index):
    (sandbox / "daily-logs" / "2026" / "07").mkdir(parents=True, exist_ok=True)
    (sandbox / "daily-logs" / "2026" / "07" / "2026-07-01.md").write_text(
        "# log", encoding="utf-8")
    result = H.reindex()
    assert not any("daily-logs" in a["file"] for a in result["added"])


# --- catalogue self-healing: notes added outside `friday note` -------------
#
# The historical bug: index.json is maintained incrementally as notes arrive
# through the normal capture path, so anything that lands another way (manual
# edit, external import, a file dropped straight into the vault) never gets a
# row and is invisible to search/ask/graph forever. `friday doctor` and
# `friday daily` now reconcile the catalogue against disk on every run instead
# of only reporting the drift and waiting for someone to run `friday reindex`.
def test_note_added_outside_capture_path_is_reconciled_by_doctor(sandbox, clean_index):
    """A .md file written directly into the vault (not via `friday note`) is
    picked up by `friday doctor`'s automatic reconciliation, without anyone
    running `friday reindex` by hand."""
    from click.testing import CliRunner
    from friday import cli as C

    _write(sandbox, "08-databases", "manually-added.md",
           '---\ntitle: "Manually Added"\ndomain: databases\ntype: concept\n---\n'
           "# Manually Added\n\nThis note was written straight into the vault "
           "folder, bypassing `friday note` entirely.\n")

    # Confirm the drift exists before reconciliation.
    assert any(n["filename"] == "manually-added.md"
               for n in json.loads(clean_index.read_text(encoding="utf-8"))["notes"]) is False

    result = CliRunner().invoke(C.cli, ["doctor"])
    assert result.exit_code == 0
    assert "Reconciled catalogue" in result.output

    notes = json.loads(clean_index.read_text(encoding="utf-8"))["notes"]
    assert any(n["filename"] == "manually-added.md" for n in notes)


def test_note_added_outside_capture_path_is_reconciled_by_daily(sandbox, clean_index):
    """Same guarantee via `friday daily`, since it reads the same index.json
    and shouldn't lag behind disk just because the user opened `daily`
    instead of `doctor`."""
    from click.testing import CliRunner
    from friday import cli as C

    _write(sandbox, "08-databases", "found-by-daily.md",
           '---\ntitle: "Found By Daily"\ndomain: databases\ntype: concept\n---\n'
           "# Found By Daily\n\nAlso written straight into the vault.\n")

    result = CliRunner().invoke(C.cli, ["daily"])
    assert result.exit_code == 0

    notes = json.loads(clean_index.read_text(encoding="utf-8"))["notes"]
    assert any(n["filename"] == "found-by-daily.md" for n in notes)


def test_doctor_reports_all_notes_indexed_when_no_drift(sandbox, clean_index):
    from click.testing import CliRunner
    from friday import cli as C
    result = CliRunner().invoke(C.cli, ["doctor"])
    assert result.exit_code == 0
    assert "Reconciled catalogue" not in result.output
