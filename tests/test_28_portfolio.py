from friday import portfolio

S = {"login": "me", "public_repos": 2, "stars": 3, "prs_merged": 1,
     "top_repos": [{"name": "a<b>", "description": "x & y", "stargazerCount": 3, "primaryLanguage": {"name": "Python"}}]}


def test_render_escapes_and_lists_projects():
    h = portfolio.render(S)
    assert "a&lt;b&gt;" in h and "x &amp; y" in h and "2 public repos" in h and "<script" not in h
