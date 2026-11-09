# AI Pulse — AI intelligence engine

Design rule: **the AI never becomes the source of facts.** Everything that can be computed deterministically
is (language, keywords, entities, categories, duplicates, importance). The LLM writes explanations, and every
generated statement is checked against the original source before it is stored or shown.

## Providers (`backend/app/ai/providers`)

Configured only through environment variables — no model names or keys in code.

| Variable | Meaning |
|---|---|
| `LLM_PROVIDER` | `openai` · `anthropic` · `ollama` · `none` (default) |
| `LLM_MODEL` | model id for that provider (required when a provider is set) |
| `EMBEDDING_PROVIDER` | `auto` (same as LLM when it can embed) · `openai` · `ollama` · `none` |
| `EMBEDDING_MODEL` | must produce **768-dim** vectors (pgvector column). OpenAI `text-embedding-3-*` are requested with `dimensions=768`; Ollama `nomic-embed-text` is 768 natively |
| `OPENAI_API_KEY`, `OPENAI_BASE_URL` | key, and any OpenAI-compatible endpoint |
| `ANTHROPIC_API_KEY`, `ANTHROPIC_API_URL` | Anthropic has no embeddings API — pair with OpenAI or Ollama embeddings |
| `OLLAMA_BASE_URL` | local models, e.g. `http://host.docker.internal:11434` from Docker |
| `LLM_TIMEOUT_SECONDS`, `LLM_MAX_OUTPUT_TOKENS`, `LLM_TEMPERATURE` | request limits |
| `LLM_PRICE_INPUT_PER_MTOK`, `LLM_PRICE_OUTPUT_PER_MTOK` | optional USD prices for cost tracking (prices change, so they are config) |
| `AI_BATCH_SIZE`, `AI_DAILY_TOKEN_BUDGET` | items analysed per run; stop LLM work for the day at the budget |

Structured output: OpenAI `response_format: json_schema`, Anthropic a forced tool whose `input_schema` is the
schema, Ollama `format: <schema>`. Output is validated with Pydantic; malformed or schema-violating JSON is
retried **once** with the validation error, then recorded as a failed analysis (`valid=false`, error kept,
retried on later runs up to 3 times). HTTP 429/5xx retry with backoff; 4xx (e.g. bad key) fail fast. Every
call is logged in `ai_usage` (purpose, provider, model, tokens, cost, ok/error) and exported as Prometheus
`aipulse_ai_calls_total` / `aipulse_ai_tokens_total`. Keys are never logged or returned by the API.

## Pipeline (`app/ai/pipeline.py`) — runs every 2 minutes and right after each ingestion

| # | Step | How |
|---|---|---|
| 1 | Content cleaning | HTML/markdown/code/boilerplate removed; original content untouched |
| 2 | Language detection | script detection + stopword frequency (en, fr, de, es, it, pt, zh, ja, ko, ru, ar); `null` when unsure |
| 3 | Category classification | keyword rules (15 categories, multi-label) + LLM categories restricted to the allowed list |
| 4 | Keyword extraction | TF-weighted unigrams/bigrams with a technology lexicon; one-off phrases dropped |
| 5 | Entity extraction | rule-based (CVE, CWE, models, organisations, technologies, versions) — every value literally appears in the text; LLM entities stored separately |
| 6 | Duplicate detection | canonical keys at ingestion; `pg_trgm` title similarity ≥ 0.85 within ±3 days across sources; embedding cosine ≥ 0.94 |
| 7 | Importance scoring | explainable formula below |
| 8 | Summarisation | short summary, detailed explanation, what happened, why it matters, who is affected |
| 9 | Technical impact | level + description; recommended actions; related technologies |
| 10 | Learning resources | LLM suggests *topics only*; links come from a curated catalog of official docs (`app/ai/learning.py`) |

Steps 1–7 need no LLM and run for every item. Steps 8–10 run for the most important items first
(`AI_BATCH_SIZE` per run, token budget enforced). Prompts are versioned (`PROMPT_VERSION`); analyses are stored
per (item, kind, version) in `ai_analyses`, always flagged AI-generated in the API/UI.

### Grounding / hallucination controls

* The prompt contains only the source text and structured facts (CVSS, KEV status, affected products…).
* **Claim check:** any version, decimal number, percentage, date, CVE/CWE id in generated text that is not in
  the source material is unsupported; sentences carrying one are removed and listed in
  `unsupported_claims_removed`.
* **Remediation:** for vulnerabilities, upgrade/patch instructions are kept only when an official remediation
  exists (CISA KEV required action / NVD-embedded KEV action); otherwise they are removed and replaced with
  "No official remediation was published in the collected sources; follow the vendor advisory."
* `source_references` are attached by AI Pulse (article URL + official references) — never by the model.

## Importance score (`app/ai/scoring.py`) — AI Pulse importance 0–100, **not CVSS**

`score = 100 × Σ wᵢ·fᵢ / Σ wᵢ` over the factors that apply (inapplicable ones are listed as excluded and the
weights renormalised). Every factor is stored with its value, weight, contribution and reason.

| Factor | Weight | Value |
|---|---|---|
| Source reliability | 0.20 | `sources.reliability` |
| Severity | 0.25 | official severity (critical 1 … info 0.1, with its basis); otherwise a per-type baseline |
| Recency | 0.15 | half-life 72 h |
| Technical impact | 0.15 | AI-assessed level (high 1, medium 0.6, low 0.3) or incident active per provider |
| Exploitation | 0.15 | vulnerabilities only: CISA KEV known-exploited = 1 |
| Verification | 0.10 | official 1, verified 0.9, unverified 0.5, disputed 0.2 |

Personalisation adds up to +15 for the user's interests and followed technologies/providers/repos (explained in
`personal_reasons`); it never changes the stored base score. Scores are recomputed hourly for the last 14 days.

## Search (`app/ai/search.py`, `GET /api/v1/search`)

* `keyword` — PostgreSQL FTS (`websearch_to_tsquery`, weighted title/description/content, `ts_rank_cd`) with
  highlighted snippets.
* `semantic` — query embedding vs `articles.embedding` (HNSW, cosine).
* `hybrid` — lexical candidates re-scored with **Okapi BM25** (k1 1.5, b 0.75; IDF over the candidate pool,
  since PostgreSQL has no native BM25) fused with semantic results by **Reciprocal Rank Fusion** (k = 60).
* All modes apply metadata filters (type, category, severity, date) and hide duplicates. Semantic/hybrid return
  501 until an embedding provider is configured. `GET /search/capabilities` tells the UI what is available.

## Question answering (`app/ai/rag.py`, `POST /api/v1/search/ask`)

1. **Interpret** the question with transparent rules: time words ("this week" → 7 days, "recently/latest" →
   30 days), item types ("vulnerabilities", "bugs", "model releases", "outages", "papers", "tools"), topic terms.
2. **Retrieve** hybrid (or BM25 without embeddings), lightly boosted by importance and recency.
3. **Sufficiency gate before any generation:** at least 2 sources (or 1 that fully covers the question) and
   ≥ 50 % of the informative question terms present — otherwise `insufficient: true`, no LLM call.
4. **Generate** from numbered sources only; the model may itself answer `insufficient`.
5. **Validate:** citations must point to provided sources (invalid ones removed), unsupported claims removed,
   an answer with no valid citation is withheld. Without an LLM, the relevant sources are returned.

## Daily briefings (`app/ai/briefing.py`)

Sections — top AI developments, model releases, tools & frameworks, research papers, critical vulnerabilities
(critical/high or KEV), bugs & incidents, DevOps & cloud, *what changed since the previous briefing*, learning
tasks — are filled from collected items ranked by personalised importance. Only the executive summary is
LLM-written (from the listed items, claim-checked); without an LLM a factual summary is generated. One
briefing per user per local date (`POST /briefings/generate`, or Celery every 15 min at each user's
`briefing_hour` in their `timezone`, honouring daily/weekdays/weekly/off) plus a global briefing.

## Verification status

* All deterministic stages, search, RAG gating/validation and briefings were run on the ~2,800 real items
  collected in Phase 4.
* LLM and embedding providers were **not** called live in development (no API key / no Ollama available);
  their request/response formats, retries, errors and malformed outputs are covered by tests with mocked HTTP
  and scripted providers. Configure a provider and run `python -m app.cli ai-analyze --llm-limit 5` to verify
  against your account.
