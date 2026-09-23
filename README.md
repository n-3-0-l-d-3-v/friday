# Friday — Personal Engineering Knowledge OS

Friday is a CLI tool (`friday`) that captures, classifies, and stores engineering
knowledge automatically into a private GitHub repo, using **free cloud AI APIs
only** (no local LLMs). Notes are plain Markdown, cross-linked with `[[wikilinks]]`,
and every capture is auto-committed and pushed.

```
capture ──▶ classify ──▶ format ──▶ save ──▶ push ──▶ link
           (Gemini →     (6 note      (Markdown  (git)   (wikilinks)
            Groq →        templates)   in devNote)
            keywords)
```

## Install

```bash
pip install -e .          # or: pip install -r requirements.txt
```

Then copy `.env.example` to `.env` and fill in your values:

| Variable | Purpose |
|----------|---------|
| `FRIDAY_REPO_PATH` | Absolute path to your `devNote` knowledge repo |
| `GEMINI_API_KEY` | AI provider (fallback; model list in `config.py`) |
| `GROQ_API_KEY` | Primary AI provider + Whisper voice transcription |
| `YOUTUBE_API_KEY` | Richer YouTube metadata (optional; falls back to oEmbed) |
| `DISCORD_BOT_TOKEN` / `DISCORD_GUILD_ID` / `DISCORD_CHANNEL_ID` | Mobile capture via Discord (optional) |

The AI layer degrades gracefully: **Groq → Gemini → offline keywords**, so
Friday still works with no keys (lower quality classification).

Model names live only in `friday/config.py`, as ordered *lists*. Providers
retire models without warning — `gemini-2.0-flash` and `llama-3.3-70b-versatile`
both started 404ing mid-2026 — so a dead model is skipped rather than silently
killing the whole AI layer. `friday doctor` reports which providers actually work.

## Commands

### Capture
| Command | Description |
|---------|-------------|
| `friday note "..."` | Capture → classify → format → save → push → link |
| `friday note "..." --source leetcode` | Activate the DSA pipeline |
| `friday note "..." --force` | Overwrite an existing note |
| `friday note "..." --no-push` | Instant capture — commit locally, skip the GitHub push |
| `friday youtube URL` | Capture a YouTube video as a structured note |
| `friday article URL` | Fetch an article (Jina Reader) and save as a note |
| `friday rss` | Fetch dev RSS feeds and save relevant items as notes |
| `friday push` | Push any locally-committed notes to GitHub (after `--no-push`) |

### Socials & LifeOS (local model, draft-only: nothing is ever posted)
| Command | Description |
|---------|-------------|
| `friday ideas [--days 7] [--count 5] [--draft N] [--dry-run]` | Weekly post ideas from recently captured notes → `Socials/ideas-<week>.md`; every idea cites real notes (invented sources dropped), thin weeks refused; `--draft N` also drafts the top N |
| `friday calendar [--write]` | Content calendar of `Socials/`: scheduled by `publish_on` (overdue flagged), undated drafts, posted; `--write` saves `Socials/Calendar.md` |
| `friday draft <linkedin\|blog\|devto\|thread> <note>` | Draft one post from a note → `Socials/` (`status: draft`, invented numbers flagged) |
| `friday github [--readme]` | GitHub stats snapshot (+ profile README) |
| `friday portfolio` | Static portfolio page from public repos |
| `friday lifeos` / `friday habit <name> [--undo]` | Today's daily note from the vault template + habit streaks |

## Talk to your knowledge base (MCP)

The most capable way to use Friday is **not the CLI** — register it as an MCP
server and talk to Claude, which can then search, read, write and reason over
your whole vault:

```bash
claude mcp add --transport stdio -s user friday -- python -m friday.mcp_server
```

Then: *"What do I know about Redis persistence?"* · *"Save this: Postgres MVCC
keeps old row versions for concurrent reads"* · *"Build me a DSA handbook."*

Eighteen tools are exposed, covering retrieval (`search_notes`, `read_note`,
`ask_knowledge_base`, `find_related`), capture (`capture_note`, `capture_url`),
overview (`knowledge_stats`, `list_recent`, `get_daily_log`, `daily_briefing`,
`learning_analytics`), and maintenance (`notes_due_for_review`,
`knowledge_health`, `export_document`, `suggest_wiki_topics`,
`synthesize_topic`, `find_duplicates`, `curate_knowledge_base`).

Because the Claude mobile app does speech-to-text, this also gives you voice
capture on your phone for free.

### Start here each morning
| Command | Description |
|---------|-------------|
| `friday daily` | Yesterday's captures, what's due for review, your streak, and one next action |

### Voice
| Command | Description |
|---------|-------------|
| `friday listen` | Speak a note — records, transcribes (Groq Whisper), captures |
| `friday listen --ask` | Speak a question, get an answer from your own notes |
| `friday listen --file memo.m4a` | Transcribe a phone voice memo |

### Synthesis — make knowledge compound
| Command | Description |
|---------|-------------|
| `friday wiki` | List note clusters worth synthesizing |
| `friday wiki "redis"` | Merge every scattered Redis note into ONE authoritative page |
| `friday wiki --all` | Synthesize every suggested cluster |

Implements the [LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f):
raw captures stay immutable, and the AI maintains a separate `wiki/topics/`
layer that gets richer as related notes arrive. On the live repo this merged 13
overlapping Redis notes into one page — and flagged a dead doc link in the
process.

### Recall — get knowledge back out
| Command | Description |
|---------|-------------|
| `friday search "term"` | Instant offline full-text search across note contents, ranked with snippets |
| `friday ask "question"` | Answer synthesized from your own notes, with cited sources (Gemini→Groq; degrades to search offline) |
| `friday open "term"` | Open the best-matching note in your editor |

### Retention — actually remember what you captured
| Command | Description |
|---------|-------------|
| `friday review` | Spaced-repetition session over notes that are due (1→3→7→16→35→75 day ladder) |
| `friday review --list` | Just show what's due, don't run the session |
| `friday quiz` | Quiz yourself on your own notes; `--domain dsa` to focus. Great before interviews |

### Documentation — turn notes into a document
| Command | Description |
|---------|-------------|
| `friday export --domain databases` | Compile a domain into ONE Markdown handbook with a table of contents |
| `friday export --tag redis --title "Redis Notes"` | Export by tag, type (`--type dsa`), or search (`--query "..."`) |

### Let it maintain itself
| Command | Description |
|---------|-------------|
| `friday curate` | One autonomous cycle: observe → plan → act → journal (dry run) |
| `friday curate --apply` | Perform the **safe** actions: relink, reindex, repair the index, synthesize topic pages |
| `friday schedule --curate` | Run a cycle nightly at 03:00, unattended |

The curator has two tiers and the distinction is deliberate:

- **SAFE** — additive or repairing. Runs unattended.
- **REVIEW** — destructive or judgement-heavy. **Never** auto-runs; it is
  proposed in the report and written to `00-meta/curator-log.md` for you.

Deleting notes is permanently REVIEW. An unattended loop that can silently
delete your knowledge is a liability, not a feature.

Each cycle appends to an append-only journal and records the next directive, so
the loop picks up where the last one stopped.

### Maintenance
| Command | Description |
|---------|-------------|
| `friday dedupe` | Find near-identical notes by content (dry run; `--apply` merges, archiving originals) |
| `friday doctor` | Health-check the repo: empty notes, broken links, duplicates, stale notes, untracked files. Gives a 0-100 score |
| `friday doctor --details` | List the actual offending files |
| `friday reindex` | Re-add notes that exist on disk but fell out of `index.json` (they're invisible to search until you do) |

The catalogue is **self-healing**: `index.json` is maintained incrementally as
notes arrive through `friday note`, so anything that lands another way (manual
edit, external import, a file dropped straight into the vault folder) never
gets a row on its own. Rather than trust the incremental updates alone, both
`friday doctor` and `friday daily` run the same reconciliation as `friday
reindex` automatically on every invocation — scanning the vault on disk and
adding whatever's missing — so the catalogue never drifts far from reality
even if you never run `reindex` by hand.

`friday note` auto-detects YouTube and article URLs and routes them accordingly.

### Daily logs & reviews
| Command | Description |
|---------|-------------|
| `friday today` | Show today's daily log |
| `friday log [--date YYYY-MM-DD]` | Show a specific daily log |
| `friday finalize` | AI-generate the day's narrative summary |
| `friday weekly` | AI-generate a weekly review from the last 7 logs |
| `friday logs` | List all logs grouped by month |
| `friday schedule [--rss] [--curate]` | Set up Windows midnight finalize, daily RSS, nightly curator |

### Knowledge base
| Command | Description |
|---------|-------------|
| `friday status` | Repo stats and git info |
| `friday inbox` | Show pending notes |
| `friday process` | Manually process the inbox |
| `friday dsa [--pattern X]` | DSA notes grouped by pattern |
| `friday lc NUMBER` | Preview a LeetCode problem |
| `friday link [--domain X]` | Run the cross-linker over notes |
| `friday graph "term"` | Show related notes with match scores |
| `friday cleanup` | Reclassify unsorted notes |
| `friday index-clean` | Remove stale index.json entries |
| `friday index-clean --fix-domains` | Also repair domains containing leaked AI prompt text |
| `friday sync` | Manual git push |

### Web dashboard & bookmarklet
| Command | Description |
|---------|-------------|
| `friday serve [--host H] [--port P]` | Start the local dashboard + capture API (default `127.0.0.1:7823`) |
| `friday discord` | Start the Discord bot for mobile capture |

Open `http://localhost:7823/dashboard`, then **drag the “⚡ Save to Friday”
button to your bookmarks bar**. Click it on any web page or YouTube video to
capture straight into Friday — works in Zen, Firefox, Chrome, and mobile.

Use `friday serve --host 0.0.0.0` to reach the dashboard/bookmarklet from your
phone on the same network.

#### API endpoints
| Method | Path | Body | Purpose |
|--------|------|------|---------|
| GET | `/health` | — | Liveness + repo/version |
| GET | `/status` | — | `total_notes`, `today` |
| GET | `/api/stats` | — | Full dashboard stats (JSON) |
| GET | `/dashboard` | — | Dark-themed HTML dashboard |
| POST | `/capture/note` | `{text, source?, url?}` | Capture a quick note |
| POST | `/capture/article` | `{url, note?}` | Capture an article |
| POST | `/capture/youtube` | `{url, note?}` | Capture a YouTube video |

## Package layout (`friday/`)

| Module | Responsibility |
|--------|----------------|
| `config.py` | Paths + API keys from `.env` |
| `capture.py` | Write raw capture JSON to the inbox |
| `classifier.py` | 3-tier classifier: Gemini → Groq → keywords |
| `formatter.py` | 6 note templates (concept, dsa, bug, snippet, video, article) |
| `orchestrator.py` | Parallel processing engine (single source of truth for daily-log writes) |
| `processor.py` | Thin delegate to the orchestrator |
| `dsa_agent.py` / `leetcode_fetcher.py` | DSA specialist + LeetCode GraphQL data |
| `youtube_agent.py` / `article_fetcher.py` | Content capture agents |
| `rss_processor.py` | RSS feed processor (stdlib parser, Groq/keyword filter) |
| `index_store.py` | Single source of truth for `index.json` — upsert-by-file so re-captures never duplicate rows |
| `retrieval.py` | Full-text search + AI answers over your own notes (`friday search` / `friday ask`) |
| `ai.py` | Central AI client — model fallback lists, timeouts, health probe |
| `mcp_server.py` | Exposes Friday as MCP tools for Claude and other agents |
| `wiki.py` | Synthesizes note clusters into authoritative topic pages |
| `briefing.py` | Daily briefing: streak, due reviews, next action |
| `analytics.py` | Capture timeline, domain and DSA-pattern coverage |
| `graph_view.py` | Knowledge-graph nodes/edges for the dashboard |
| `voice.py` | Recording + Whisper transcription for `friday listen` |
| `curator.py` | Autonomous observe/plan/act/journal maintenance loop |
| `dedupe.py` | Content-based near-duplicate detection and merging |
| `health.py` | Repo health checks + `reindex` recovery of unindexed notes |
| `review.py` | Spaced repetition + quiz generation |
| `exporter.py` | Compiles notes into a single shareable document |
| `daily_log.py` | Daily journal + AI summaries |
| `linker.py` | `[[wikilink]]` cross-linker |
| `git_sync.py` | Stage / commit / push |
| `scheduler.py` / `tasks.py` | Windows Task Scheduler jobs (finalize, rss) |
| `api_server.py` | FastAPI dashboard + capture API + bookmarklet |
| `index_cleaner.py` | Prune stale `index.json` entries |
| `cli.py` | All `friday` commands |

## Ecosystem agent contract

Friday is one specialist agent in a wider personal multi-agent ecosystem
(knowledge capture / docs / writing), alongside other agents with their own
names and roles — including a separate orchestrator called Jarvis, planned
independently, which is why this project renamed away from its original name
to avoid colliding with it. The contract other tooling in that ecosystem
reads:

- **`agent.yaml`** at the repo root — name, role, sensitivity tier,
  entrypoint, health check command, vault write path.
- **`friday --health`** — a JSON report: version, which AI providers are
  reachable right now, catalogue health (notes on disk vs. notes in
  `index.json`, via the same reconciliation `reindex`/`doctor`/`daily` run,
  without mutating anything itself), the personal-token tier guarantee below,
  and the most recent capture timestamp.

### personal-token tier guarantee

Friday's `default_sensitivity_tier` is `personal-token`: it authenticates to
Groq and Gemini with **your own** API keys (`GROQ_API_KEY` / `GEMINI_API_KEY`
in `.env`), never a shared or free-tier credential pool meant for generic
`work`-tier ecosystem tasks. This is a hard requirement, not a default that
happens to be true today — Friday reads and writes your personal knowledge
base, so its provider calls must stay attributable to you alone.

`friday.config.assert_personal_token_tier()` is the guarantee's enforcement
point: it scans the environment for any credential-shaped variable that looks
like it belongs to a shared pool (matching `SHARED_POOL`, `WORK_TIER`,
`FLEET_KEY`, or `POOL_TOKEN` in the name, alongside `GROQ`/`GEMINI`/`FRIDAY`)
and raises rather than letting Friday silently authenticate through it. Its
result is surfaced in every `friday --health` report under
`personal_token_tier`, so a broken guarantee is visible without reading code.

## Tests

```bash
pip install pytest
pytest
```

443 tests cover every module. The suite is **fully sandboxed**: `tests/conftest.py`
points `FRIDAY_REPO_PATH` at a throwaway temp git repo *before* any friday module
is imported, so the complete pipeline (capture → classify → format → save → index
→ daily log → git commit) runs end to end without ever touching your real devNote
repo or pushing to GitHub. AI calls are stubbed, so the suite is deterministic and
runs offline in ~25s.

## Notes
- Everything is local-first; the only outbound traffic is your own GitHub
  pushes and the free AI/feed APIs.
- `00-meta/index.json` in the knowledge repo tracks every note ever saved.
