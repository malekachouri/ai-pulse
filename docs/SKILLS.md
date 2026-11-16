# Skills Radar

New **MCP servers**, **Claude Code plugins** and **Agent Skills** from official listings, with how to install
each one and which AI Pulse technologies it covers. Page: **Skills Radar** (`/skills`). API: `/api/v1/skills`.

| Kind | What it is | Installs with |
|---|---|---|
| MCP server | Gives an AI assistant new tools and data through the Model Context Protocol | `claude mcp add …` |
| Plugin | A Claude Code plugin: commands, agents, skills, hooks or MCP servers in one install | `/plugin install <name>@<marketplace>` |
| Agent Skill | Instructions and scripts an agent loads when a task needs them (a `SKILL.md` folder) | the plugin that bundles it |

## Sources

| Source | Connector | Every | What is read |
|---|---|---|---|
| Official MCP Registry (`registry.modelcontextprotocol.io`) | `mcp_registry` | hour | latest version of each server published or updated since the last run |
| Claude Code plugins, official marketplace (`anthropics/claude-plugins-official`) | `claude_marketplace` | 6 hours | `.claude-plugin/marketplace.json` |
| Agent Skills by Anthropic (`anthropics/skills`) | `claude_marketplace` | 6 hours | `marketplace.json` and the front matter of each listed `SKILL.md` |

Live-checked on 2026-11-15. More marketplaces: add their repository to a `claude_marketplace` source's
`marketplaces` list (**Admin → Sources**), e.g. `{"repo": "acme/claude-plugins", "ref": "main"}`.

**Volume.** The registry changes by more than a thousand servers a day. Radar entries are stored in their own
table (`ai_skills`), never as articles: they do not reach the news feed, search, briefings or the AI
analysis queue. A run reads at most `max_pages` pages of 100 (default 30); the next run resumes from the
cursor, so the first sync (the last `initial_days` = 3 days) catches up over a few hours.

## What is shown, and where it comes from

Facts only, all from the listing:

- name, title, description, version, publisher (the registry's verified namespace, or the plugin author),
  category, status (`active`, `deprecated`, `deleted` in the registry; `removed` when a plugin leaves its
  marketplace; inactive entries are hidden unless asked for);
- links: the official listing, the website and the source code, when the listing gives them;
- dates: the registry's publication date of the version, and when AI Pulse first saw the entry.

**"New"** means first seen by AI Pulse in the last 7 days. A marketplace's first collection is the
**baseline**: those plugins and skills already existed, so they are marked "Listed before AI Pulse started
watching this source" and never counted as new. Registry entries are read by date, so they are not a baseline.

**Install commands** are assembled from the listing's own fields (`app/skills/install.py`), never guessed:

| Listing gives | Command |
|---|---|
| a remote (`streamable-http` / `sse`) | `claude mcp add --transport http|sse <name> <url>`; required headers as `--header 'Name: <NAME>'` |
| an npm / PyPI / NuGet package | `claude mcp add <name> -e 'VAR=<VAR>' -- npx -y pkg@version` (`uvx pkg==version`, `dnx pkg@version`) |
| an OCI image | `docker run -i --rm -e VAR <image>` (then `claude mcp add --transport http …` when it serves HTTP) |
| an MCP bundle (`.mcpb`) | the bundle's download URL |
| anything else | no command: a note points to the listing |

Runtime and package arguments are placed where the registry's `server.json` schema puts them. Required
variables become `<NAME>` placeholders, explained in the notes (secret or not, with the listing's
description). AI Pulse does not review third-party code: read what a server or plugin does before installing it.

**"Fits AI Pulse"** tags are whole-word matches of the technologies this project uses (PostgreSQL, Redis,
Docker, Kubernetes, GitHub, security, Python, TypeScript/Next.js, Ollama/local models, monitoring, testing)
in the name, title, description and category (`app/skills/stack.py`). The registry namespace is ignored:
`io.github.<user>/…` says where a server is published, not what it does.

## API

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/v1/skills` | filters: `kind`, `source` (slug), `stack` (tags, any), `fits=true`, `days` (new in N days, baseline excluded), `q`, `include_inactive=true`; `sort`: `-first_seen_at` (default), `-published_at`, `name`, `-updated_at` |
| `GET` | `/api/v1/skills/facets` | counts per kind and technology, entries and last collection per radar source, new this week |
| `GET` | `/api/v1/skills/{id}` | one entry with the listing facts (packages, remotes, marketplace source) |

## Operations

```bash
docker compose exec api python -m app.cli ingest mcp-registry
```

```bash
docker compose exec api python -m app.cli ingest claude-plugins-official
```

Source health, failures and jobs are on **Admin → Connector health**, like every other source. A failing
marketplace changes nothing: entries are marked `removed` only when every marketplace of the source was read.
