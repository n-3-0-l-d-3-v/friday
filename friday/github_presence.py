"""GitHub presence: stats snapshot + profile README, via the authenticated `gh` CLI.

Uses `gh` (already logged in as the user) so no token is handled here. Public
data only; private repos are counted, never named.
"""
from __future__ import annotations

import json
import subprocess
from datetime import date
from pathlib import Path


def _gh(*args: str) -> str:
    r = subprocess.run(["gh", *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip() or "gh failed")
    return r.stdout


def fetch_snapshot(login: str | None = None) -> dict:
    user = json.loads(_gh("api", "user"))
    login = login or user["login"]
    repos = json.loads(_gh("repo", "list", login, "--limit", "200", "--json",
                           "name,description,stargazerCount,forkCount,isPrivate,pushedAt,primaryLanguage"))
    prs = json.loads(_gh("search", "prs", "--author", login, "--limit", "100", "--json", "state"))
    return {"login": login, "followers": user["followers"], "following": user["following"],
            "repos": repos, "prs_authored": len(prs), "prs_merged": sum(1 for p in prs if p["state"] == "merged")}


def summarize(snap: dict) -> dict:
    pub = [r for r in snap["repos"] if not r["isPrivate"]]
    return {
        "login": snap["login"], "followers": snap["followers"], "public_repos": len(pub),
        "private_repos": len(snap["repos"]) - len(pub),
        "stars": sum(r["stargazerCount"] for r in pub), "forks": sum(r["forkCount"] for r in pub),
        "prs_authored": snap["prs_authored"], "prs_merged": snap["prs_merged"],
        "top_repos": sorted(pub, key=lambda r: (r["stargazerCount"], r["pushedAt"]), reverse=True)[:6],
    }


def render_stats_note(s: dict, today: date | None = None) -> str:
    today = today or date.today()
    return (f"---\ntype: github-stats\ndate: {today.isoformat()}\nfollowers: {s['followers']}\n"
            f"stars: {s['stars']}\nforks: {s['forks']}\nprs_merged: {s['prs_merged']}\n---\n"
            f"# GitHub snapshot {today.isoformat()}\n\n"
            f"- Followers: {s['followers']}\n- Public repos: {s['public_repos']} (+{s['private_repos']} private)\n"
            f"- Stars: {s['stars']}  Forks: {s['forks']}\n- PRs authored: {s['prs_authored']} (merged {s['prs_merged']})\n")


def render_profile_readme(s: dict) -> str:
    lines = [f"# Hi, I'm {s['login']}", "", "CS student building a local-first, privacy-first multi-agent developer setup.", "",
             "## Featured projects", ""]
    for r in s["top_repos"]:
        desc = (r.get("description") or "").strip()
        lines.append(f"- [{r['name']}](https://github.com/{s['login']}/{r['name']})" + (f" - {desc}" if desc else ""))
    lines += ["", f"_{s['public_repos']} public repos, {s['stars']} stars, {s['prs_merged']} merged PRs._", ""]
    return "\n".join(lines)


def write_snapshot(vault_dir: Path, s: dict, today: date | None = None) -> Path:
    vault_dir.mkdir(parents=True, exist_ok=True)
    out = vault_dir / f"github-stats-{(today or date.today()).isoformat()}.md"
    out.write_text(render_stats_note(s, today), encoding="utf-8")
    return out
