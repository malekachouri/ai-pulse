# Prompt 05: AI-powered analysis

| | |
|---|---|
| **Phase** | 5 of 9 |
| **Send it** | After prompt 04, once real items are collected. |
| **What it built in this repository** | OpenAI/Anthropic/Ollama providers, 10-step pipeline with grounding checks, explainable importance score, hybrid search, RAG with citations (docs/AI.md). |
| **Check before the next prompt** | `docker compose exec api python -m app.cli ai-analyze --limit 20`; ask a question on the Search page and check every citation. |

Paste everything in the box below into Claude Code, in the repository, as one message.

~~~text
This is what makes AI Pulse different from ordinary news websites.
Act as a senior AI Engineer specializing in LLM applications, RAG and AI Agents.

Implement the AI Intelligence Engine for AI Pulse.
1. LLM provider architecture
Create a provider abstraction supporting:
- OpenAI API.
- Ollama local models.
- Anthropic API as an optional provider.
Configure the active provider through environment variables.

Never hardcode model names or API keys.
2. AI processing pipeline
For every collected article, issue, vulnerability or incident, implement:
1. Content cleaning.
2. Language detection.
3. Category classification.
4. Keyword extraction.
5. Entity extraction.
6. Duplicate detection.
7. Importance scoring.
8. AI-generated summarization.
9. Technical impact analysis.
10. Recommended learning resources.
3. Categorization
Support:
- AI Models.
- AI Research.
- AI Tools.
- RAG.
- LLMOps.
- MLOps.
- AI Agents.
- Software Engineering.
- Bugs.
- Infrastructure Failures.
- Cybersecurity.
- DevOps.
- Cloud.
- Kubernetes.
- Docker.
Allow multiple categories per item.
4. AI summaries
For every item generate:
- Short summary.
- Detailed explanation.
- What happened?
- Why does it matter?
- Who is affected?
- Technical impact.
- Recommended actions.
- Related technologies.
- Original source references.
For vulnerabilities, include remediation only when supported by trusted source information.
5. Importance scoring
Build an explainable scoring system based on:
- Source reliability.
- Severity.
- Recency.
- Technical impact.
- Relevance to user interests.
- Exploitation status for security issues.
Clearly distinguish importance scores from official CVSS scores.
6. Semantic search and RAG
Implement:
- Embedding generation.
- PostgreSQL pgvector.
- Semantic search.
- Hybrid search.
- Keyword search.
- BM25 where appropriate.
- Similarity ranking.
- Metadata filtering.
Users should be able to ask questions such as:

"What are the latest important developments in RAG?"

"Which Kubernetes vulnerabilities were recently disclosed?"

"What are the most important AI model releases this week?"

"What new bugs are affecting popular AI frameworks?"

Build a RAG pipeline that answers using collected information and cites the original articles.

If information is insufficient, explicitly say so rather than hallucinating.
7. Daily briefing generation
Generate daily personalized reports containing:
- Top 5 AI developments.
- Top 5 new tools.
- Important research papers.
- Critical vulnerabilities.
- Important bugs and failures.
- DevOps and Cloud updates.
- Recommended learning tasks.
Store each generated briefing in the database.

Implement tests for AI provider errors, malformed outputs and unsupported claims.
~~~

Previous: [04](04-data-ingestion.md) · Next: [06](06-bugs-failures-radar.md) · [All prompts](README.md)
