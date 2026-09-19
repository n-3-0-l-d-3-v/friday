from datetime import date

from friday import github_presence as gp

SNAP = {"login": "me", "followers": 3, "following": 1, "prs_authored": 5, "prs_merged": 2,
        "repos": [
            {"name": "a", "description": "A tool", "stargazerCount": 4, "forkCount": 1, "isPrivate": False, "pushedAt": "2026-01-01"},
            {"name": "b", "description": "", "stargazerCount": 1, "forkCount": 0, "isPrivate": False, "pushedAt": "2026-02-01"},
            {"name": "secret", "description": "x", "stargazerCount": 9, "forkCount": 9, "isPrivate": True, "pushedAt": "2026-03-01"}]}


def test_summary_excludes_private_from_counts_and_names():
    s = gp.summarize(SNAP)
    assert (s["public_repos"], s["private_repos"], s["stars"], s["forks"]) == (2, 1, 5, 1)
    assert "secret" not in [r["name"] for r in s["top_repos"]]


def test_readme_lists_top_repo_first_and_never_private():
    md = gp.render_profile_readme(gp.summarize(SNAP))
    assert md.index("[a]") < md.index("[b]") and "secret" not in md


def test_write_snapshot(tmp_path):
    p = gp.write_snapshot(tmp_path / "v", gp.summarize(SNAP), date(2026, 9, 19))
    assert p.name == "github-stats-2026-09-19.md" and "stars: 5" in p.read_text()
