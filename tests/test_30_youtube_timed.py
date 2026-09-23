from friday import youtube_agent as Y

URL = "https://www.youtube.com/watch?v=abc"
SNIPS = [(0.0, "intro"), (30.5, "setup"), (61.0, "layers"), (3725.0, "wrap up")]
META = {"video_id": "abc", "title": "T", "channel": "C", "description": "", "published_at": "",
        "tags": [], "duration": "", "view_count": "", "url": URL, "thumbnail": ""}


def test_timed_transcript_groups_by_minute_with_clickable_stamps():
    md = Y.timed_transcript_md(SNIPS, URL)
    lines = md.splitlines()
    assert lines[0] == "> [!note]- Transcript (timestamped)"
    assert lines[1] == f"> - [00:00]({URL}&t=0s) intro setup"
    assert lines[2] == f"> - [01:01]({URL}&t=61s) layers"
    assert lines[3] == f"> - [1:02:05]({URL}&t=3725s) wrap up"
    assert Y.timed_transcript_md(SNIPS, "https://youtu.be/abc").splitlines()[1].startswith("> - [00:00](https://youtu.be/abc?t=0s)")
    assert Y.timed_transcript_md(None, URL) is None


def test_timed_transcript_truncates():
    many = [(i * 60.0, "word " * 50) for i in range(100)]
    md = Y.timed_transcript_md(many, URL, max_chars=2000)
    assert md.endswith("> - ... (truncated)") and len(md) < 2600


def test_transcript_text_joins_and_truncates():
    assert Y.transcript_text(SNIPS) == "intro setup layers wrap up"
    assert Y.transcript_text([(0, "x" * 50)], limit=10) == "x" * 10 + "..."
    assert Y.transcript_text(None) is None


def test_note_has_timed_transcript_and_leaves_my_notes_to_the_user():
    note = Y.build_video_note(META, Y.transcript_text(SNIPS), None, "2026-09-23T10:00:00", SNIPS)
    my_notes = note.split("## My Notes")[1].split("##")[0]
    assert "intro" not in my_notes
    assert "## Transcript\n> [!note]- Transcript (timestamped)" in note and "&t=61s" in note


def test_note_without_snippets_falls_back_to_excerpt_or_placeholder():
    assert "Transcript (excerpt)" in Y.build_video_note(META, "plain text", None, "2026-09-23T10:00:00")
    assert "No transcript available" in Y.build_video_note(META, None, None, "2026-09-23T10:00:00")
