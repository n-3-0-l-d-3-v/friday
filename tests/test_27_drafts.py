import pytest

from friday import drafts


def test_prompt_includes_style_and_source_and_rejects_unknown():
    p = drafts.build_prompt("linkedin", "I built X " * 40)
    assert "LinkedIn" in p and "I built X" in p
    with pytest.raises(drafts.DraftError):
        drafts.build_prompt("myspace", "x" * 300)


def test_write_draft_is_draft_status(tmp_path):
    path = drafts.write_draft(tmp_path, "blog", "My Title", "body", "n.md")
    t = path.read_text(encoding="utf-8")
    assert "status: draft" in t and path.parent.name == "Socials" and "body" in t


def test_generate_wraps_connection_errors():
    with pytest.raises(drafts.DraftError):
        drafts.generate("hi", host="http://127.0.0.1:1", timeout=1)


def test_thin_source_refused():
    with pytest.raises(drafts.DraftError):
        drafts.build_prompt("linkedin", "tiny")


def test_ungrounded_numbers_flags_only_new_numbers():
    assert drafts.ungrounded_numbers("I fixed 3 bugs in 2 days", "Fixed 3 bugs, 15 people, 2 days") == ["15"]
