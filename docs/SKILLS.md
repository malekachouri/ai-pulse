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

**Technologies** tags are whole-word matches of common technologies (PostgreSQL, Redis, Docker, Kubernetes,
GitHub, security, Python, TypeScript/Next.js, Ollama/local models, monitoring, testing) in the name, title,
description and category (`app/skills/stack.py`; add a tag there to track another technology). The filter
"Any of these technologies" is `fits=true` in the API. The registry namespace is ignored:
`io.github.<user>/…` says where a server is published, not what it does.

## "What is it good for?" (AI, on demand)

Each entry has a button that asks the configured AI model (OpenAI, Anthropic or Ollama) for a short,
**general** explanation, useful for any project, in four sections: **what it does**, **what it is good for**
(the kinds of projects and tasks the sources describe), **how to try it** and **before you use it**. It runs
only when a signed-in user asks (AI rate limit), never in the background.

The model may use only the tool's own material, as numbered sources (`app/skills/explain.py`):

| # | Source |
|---|---|
| [1] | the official listing as collected: description, version, publisher, install instructions, packages |
| [2] | the project's README, when the listing links a `https://github.com/<owner>/<repo>` repository (fetched on demand, badges and HTML removed, first 6,000 characters) |

Then the answer is checked: uncited text and unknown citations are dropped; sentences with numbers,
versions or ids that the cited sources do not contain are removed and listed. An empty section says
"insufficient information". The result is stored on the entry with the provider, model,
date and the listing version it was written for, and shown labelled **AI-generated**. If the model fails
(a timeout with a slow local model, for example), nothing is replaced and the failure is recorded in AI usage.

## API

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/v1/skills` | filters: `kind`, `source` (slug), `stack` (tags, any), `fits=true`, `days` (new in N days, baseline excluded), `q`, `include_inactive=true`; `sort`: `-first_seen_at` (default), `-published_at`, `name`, `-updated_at` |
| `GET` | `/api/v1/skills/facets` | counts per kind and technology, entries and last collection per radar source, new this week |
| `GET` | `/api/v1/skills/{id}` | one entry with the listing facts (packages, remotes, marketplace source) |
| `GET` | `/api/v1/skills/{id}/explanation` | the stored AI explanation (`status: none` when there is none yet), and whether an LLM is configured |
| `POST` | `/api/v1/skills/{id}/explanation` | generate it (signed in; AI rate limit); `status: failed` with the error when the model does not answer |

## Operations

```bash
docker compose exec api python -m app.cli ingest mcp-registry
```

```bash
docker compose exec api python -m app.cli ingest claude-plugins-official
```

Source health, failures and jobs are on **Admin → Connector health**, like every other source. A failing
marketplace changes nothing: entries are marked `removed` only when every marketplace of the source was read.
