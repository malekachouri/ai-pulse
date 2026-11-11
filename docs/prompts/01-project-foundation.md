# Prompt 01: Project foundation

| | |
|---|---|
| **Phase** | 1 of 9 |
| **Send it** | Send it first, in an empty repository. |
| **What it built in this repository** | Architecture document, folder structure, full database schema and first migration, authentication (Argon2id, JWT and a rotating refresh cookie, roles), core API, Docker. |
| **Check before the next prompt** | docs/ARCHITECTURE.md exists; `docker compose up -d --build --wait` starts; `cd backend && pytest -q` passes. |
| **Note from the guide** | Send this first. It establishes the rules Claude must follow throughout the project. |

Paste everything in the box below into Claude Code, in the repository, as one message.

~~~text
ROLE: Senior Software Architect, Full-Stack Engineer and AI Engineer
I want you to build a complete production-oriented application named AI Pulse.
1. Product vision
AI Pulse is an AI and Technology Intelligence Platform that automatically collects, processes, classifies, summarizes and displays information about:
- Latest AI models and releases.
- AI tools, frameworks and libraries.
- AI research papers and breakthroughs.
- RAG, LLMOps, MLOps and AI Agents.
- GitHub trending repositories, issues, bugs and fixes.
- Software failures and production incidents.
- Cybersecurity vulnerabilities, CVEs and security advisories.
- DevOps, Kubernetes, Docker and Cloud updates.
- AWS, Azure and Google Cloud incidents and announcements.
The application must provide a centralized intelligence dashboard with reliable sources, automatic updates, AI-powered summaries and personalized daily briefings.
2. Technology stack
Frontend:
- Next.js with App Router.
- TypeScript.
- Tailwind CSS.
- shadcn/ui.
- Lucide icons.
- Recharts for analytics.
Backend:
- Python 3.12+.
- FastAPI.
- Pydantic.
- SQLAlchemy 2.
- Alembic.
Database:
- PostgreSQL.
- pgvector for semantic search.
AI:
- OpenAI API integration.
- Ollama integration for local models.
- Provider abstraction to allow adding Anthropic and other LLM providers.
- Structured JSON outputs.
- AI summarization, classification, deduplication and relevance scoring.
Background processing:
- Celery.
- Redis.
- Scheduled ingestion tasks.
Infrastructure:
- Docker and Docker Compose.
- GitHub Actions.
- Prometheus and Grafana.
- Structured logging.
3. Architecture
Use a modular, maintainable architecture.

Separate:
- Frontend.
- Backend API.
- Domain/business logic.
- Database infrastructure.
- Data source connectors.
- AI processing services.
- Background workers.
- Scheduled jobs.
- Monitoring.
Follow clean code principles, SOLID, dependency injection and separation of concerns.
4. Main application modules
1. Authentication and user management.
2. Main intelligence dashboard.
3. AI News.
4. AI Models and Releases.
5. AI Tools and Frameworks.
6. Research Papers.
7. GitHub Radar.
8. Bugs and Software Failures.
9. Security Vulnerabilities.
10. DevOps and Cloud Radar.
11. AI Daily Briefing.
12. Semantic Search.
13. Notifications and Alerts.
14. Favorites and Bookmarks.
15. User Preferences.
16. Administration Panel.
17. Analytics and Statistics.
5. Development requirements
Before coding:
- Analyze the requirements.
- Create a complete project architecture.
- Create the folder structure.
- Define database entities and relationships.
- Define API endpoints.
- Define data ingestion workflows.
- Define AI processing workflows.
- Define security architecture.
- Create a development roadmap.
Then implement the project progressively.

For every module:
- Implement actual working functionality.
- Add validation and error handling.
- Add unit and integration tests.
- Add database migrations.
- Add API documentation.
- Add loading, empty and error states in the frontend.
- Ensure frontend/backend integration works.
6. Important rules
- Never generate fake news or fake security alerts.
- Every collected item must have its original source URL.
- Store publication date and collection date separately.
- Handle duplicate articles and repeated incidents.
- Respect API rate limits and source terms.
- Never expose API keys in frontend code.
- Never hardcode credentials.
- Use environment variables.
- Do not pretend that an incident is live without verified status information.
- Clearly distinguish confirmed facts from AI-generated analysis.
- Make the application functional, not just visually attractive.
- Do not leave important features as TODO placeholders.
7. Expected result
Build a professional, responsive, secure and scalable application.

Start by producing:
1. Architecture document.
2. Folder structure.
3. Database schema.
4. API specification.
5. Implementation roadmap.
After presenting the architecture, start implementing the project.

Do not stop after generating documentation. Continue with actual implementation, testing and validation.

Work incrementally and report completed features, changed files, tests and remaining tasks after each phase.
~~~

Previous: [project specification](00-project-specification.md) · Next: [02](02-frontend.md) · [All prompts](README.md)
