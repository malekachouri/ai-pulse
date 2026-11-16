# Suggestions for later

Improvements that were discussed but are **not built yet**. Each one is optional: the app works without
it. Pick one, open an issue or a branch, and follow [CONTRIBUTING.md](../CONTRIBUTING.md).

## 1. AI on small local models (Ollama)

These help most on a PC that runs a small model (for example `qwen2.5:3b`) on the CPU.

| # | Suggestion | Why | Today's workaround |
|---|---|---|---|
| 1.1 | **Small embedding batches for local providers**: send 8 texts per embedding request instead of 64, configurable in `.env` | Large batches time out on a CPU, so semantic search has to be turned off | `EMBEDDING_PROVIDER=none` (keyword search only) |
| 1.2 | **Interactive requests first**: background analysis pauses while a user asks for "Explain with AI" or a RAG answer | A slow local model handles one request at a time; a user click waits behind the batch | `AI_BATCH_SIZE=2` keeps batches short |
| 1.3 | **Shorter sources for local models**: trim each source passed to the model (local providers only, limit configurable in `.env`) | Long prompts are the main cost on a CPU | `LLM_TIMEOUT_SECONDS=900` |
| 1.4 | **No duplicate AI sentence**: drop AI text that only repeats a fact already shown with its citation | The same version or fix sometimes appears twice in Bug intelligence | none (cosmetic) |
| 1.5 | **Stricter AI categories**: keep a category suggested by the model only when its keywords appear in the text | Unrelated "Learn more" links (Kubernetes, Docker, AWS) appear on some CVEs | none |

## 1b. Skills Radar

| # | Suggestion | Why |
|---|---|---|
| 1b.2 | **Retention for registry entries**: delete inactive MCP servers not updated for 180 days | The registry adds more than a thousand entries a day |
| 1b.3 | **More marketplaces** in the catalog (official vendor marketplaces as they appear) | Today: Anthropic's plugin and skills marketplaces |

## 2. Operations and backups

| # | Suggestion | Why |
|---|---|---|
| 2.1 | **Alert when an offsite backup fails**: export the last successful upload time and add a Prometheus rule | A failed upload today only shows up in the `backup` logs |
| 2.2 | **Clean up old `collection_jobs`**: delete rows older than 90 days in a nightly Beat task | The table grows with every collection run |
| 2.3 | **Point-in-time recovery (WAL archiving)** next to the nightly dumps | Restores today go back to the last dump, up to 24 hours of data lost |

## 3. Features and security

| # | Suggestion | Why |
|---|---|---|
| 3.1 | **Non-Latin fonts in the weekly PDF** (Arabic, CJK, ...) | Titles in those scripts render as empty boxes |
| 3.2 | **Two-factor authentication for admins** (TOTP) | Admin accounts can change sources, users and settings |

## 4. Tests to add

The current suites and how to run them are in [DEVELOPMENT.md](DEVELOPMENT.md) and
[e2e/README.md](../e2e/README.md). Gaps worth filling:

- an end-to-end test against a real (small) Ollama model, run manually or nightly, not on every pull
  request;
- a restore drill in CI: restore the latest backup into a throwaway database and run the migrations check.
