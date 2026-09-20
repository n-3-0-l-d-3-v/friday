"""Static, dependency-free portfolio page from GitHub data (host free on GitHub Pages)."""
from __future__ import annotations

import html
from datetime import date


def render(s: dict, name: str | None = None, tagline: str = "CS student building local-first, privacy-first developer tooling.") -> str:
    name = html.escape(name or s["login"])
    cards = "\n".join(
        f'<a class="card" href="https://github.com/{html.escape(s["login"])}/{html.escape(r["name"])}">'
        f'<h3>{html.escape(r["name"])}</h3><p>{html.escape((r.get("description") or "")[:160])}</p>'
        f'<span>{html.escape((r.get("primaryLanguage") or {}).get("name", ""))} &#9733; {r["stargazerCount"]}</span></a>'
        for r in s["top_repos"])
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{name}</title><style>
:root{{color-scheme:light dark;--bg:#fff;--fg:#1a1a1a;--mut:#666;--card:#f4f4f6}}
@media(prefers-color-scheme:dark){{:root{{--bg:#111;--fg:#eee;--mut:#999;--card:#1c1c20}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 system-ui,sans-serif}}
main{{max-width:860px;margin:auto;padding:48px 20px}}h1{{margin:0}}p.t{{color:var(--mut)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:14px}}
.card{{background:var(--card);border-radius:12px;padding:16px;text-decoration:none;color:inherit}}
.card h3{{margin:0 0 6px}}.card p{{margin:0 0 8px;color:var(--mut);font-size:14px}}.card span{{font-size:13px}}
footer{{margin-top:40px;color:var(--mut);font-size:13px}}</style></head><body><main>
<h1>{name}</h1><p class="t">{html.escape(tagline)}</p>
<p>{s["public_repos"]} public repos &middot; {s["stars"]} stars &middot; {s["prs_merged"]} merged PRs</p>
<h2>Projects</h2><div class="grid">{cards}</div>
<footer>Generated {date.today().isoformat()} from GitHub data.</footer></main></body></html>"""
