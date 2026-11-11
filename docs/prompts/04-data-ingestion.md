# Prompt 04: Automated ingestion engine

| | |
|---|---|
| **Phase** | 4 of 9 |
| **Send it** | After prompt 03. |
| **What it built in this repository** | 14 connectors for 28 official sources, Celery + Beat, retries, per-host rate limits, checkpoints, deduplication, source health (docs/INGESTION.md). |
| **Check before the next prompt** | `docker compose exec api python -m app.cli ingest nvd-cve` collects items; Admin → Ingestion shows every source. |

Paste everything in the box below into Claude Code, in the repository, as one message.

~~~text
This is one of the most important parts of the application.
Act as a senior data engineer.

Implement the complete automated data collection system for AI Pulse.

Use Python, FastAPI services, Celery, Redis and PostgreSQL.
Data source integrations
AI announcements
- OpenAI official news and release feeds.
- Anthropic official news.
- Google DeepMind blog.
- Hugging Face.
- Meta AI announcements.
- Mistral AI announcements.
Research
- arXiv API.
- Hugging Face Papers.
GitHub
Use GitHub REST API to collect:
- Trending repositories where supported by available data.
- Repository metadata.
- New releases.
- Open issues.
- Bug reports.
- Security-related issues where publicly accessible.
- Closed and fixed issues.
Do not claim GitHub provides a native trending API. Use a clearly documented alternative based on available repository search and ranking.
Security
- NVD CVE API.
- CISA Known Exploited Vulnerabilities catalog.
- Official vendor security advisories.
Collect:
- CVE ID.
- CVSS score when available.
- Severity.
- Affected products and versions.
- Published date.
- Last modified date.
- Remediation information.
- Official references.
- Known exploited status.
Cloud and DevOps
- AWS Health and official status information.
- Azure status and advisories.
- Google Cloud status.
- Kubernetes releases.
- Docker releases.
- CNCF projects and release feeds.
Respect authentication requirements and API terms.
Ingestion architecture
For each source create an independent connector.

Each connector must implement:
- fetch()
- normalize()
- validate()
- deduplicate()
- save()
- log_errors()
Create a shared normalized data format.

Implement:
- Scheduled polling.
- Retry policies.
- Exponential backoff.
- Rate limiting.
- Pagination.
- Checkpointing.
- Idempotent ingestion.
- Failed-job tracking.
- Source health monitoring.
Use Celery workers and periodic tasks.

Allow administrators to enable, disable and configure data sources.
Data quality
Every record must contain:
- Original URL.
- Source name.
- Source type.
- Publication date if available.
- Collection timestamp.
- Content hash.
- Category.
- Verification status.
Never invent missing information.

Preserve original content and metadata separately from AI-generated summaries.

Create integration tests using mocked external API responses.

Provide an ingestion status dashboard.

Implement this as real working connectors, not placeholder functions.
~~~

Previous: [03](03-backend-api.md) · Next: [05](05-ai-engine.md) · [All prompts](README.md)
