# Prompt 03: FastAPI backend and database

| | |
|---|---|
| **Phase** | 3 of 9 |
| **Send it** | After prompt 02. |
| **What it built in this repository** | Typed modules (models, tools, research, GitHub, bugs, security, incidents), keyword search, admin users/roles/jobs/audit, strict validation. |
| **Check before the next prompt** | `alembic upgrade head && alembic check`; backend tests pass; `/docs` lists every endpoint. |

Paste everything in the box below into Claude Code, in the repository, as one message.

~~~text
Continue the existing AI Pulse repository.

Act as a senior Python backend engineer.

Build a complete FastAPI backend using clean architecture, SQLAlchemy 2, Pydantic and PostgreSQL.
Database models
Implement the following entities:
1. User
2. Role
3. UserPreference
4. Article
5. Source
6. Category
7. AIModel
8. AIModelRelease
9. AITool
10. ResearchPaper
11. GitHubRepository
12. GitHubIssue
13. SoftwareBug
14. SecurityVulnerability
15. Incident
16. DailyBriefing
17. Bookmark
18. Notification
19. CollectionJob
20. AIAnalysis
Define relationships, indexes, constraints, timestamps and appropriate enumerations.

Use UUID identifiers where appropriate.

Add PostgreSQL full-text search and pgvector support.
Authentication
Implement:
- User registration.
- Login.
- Secure authentication.
- Password hashing.
- Access tokens.
- Refresh token rotation.
- Logout.
- Role-based access control.
- User profile management.
- Password reset workflow.
Use secure cookie handling where appropriate.
API modules
Create versioned endpoints:

/api/v1/auth
/api/v1/dashboard
/api/v1/news
/api/v1/models
/api/v1/tools
/api/v1/research
/api/v1/github
/api/v1/bugs
/api/v1/security
/api/v1/incidents
/api/v1/briefings
/api/v1/search
/api/v1/bookmarks
/api/v1/notifications
/api/v1/admin
/api/v1/preferences

Implement:
- Filtering.
- Sorting.
- Pagination.
- Validation.
- Consistent error responses.
- API documentation.
- Authorization.
Requirements
Use dependency injection and service/repository separation.

Add Alembic migrations.

Write unit and integration tests.

Add health and readiness endpoints.

Connect the backend to the existing frontend.

Do not duplicate existing code or break completed modules.

Run migrations and tests before considering this phase complete.




6. Data collection and integrations
~~~

Previous: [02](02-frontend.md) · Next: [04](04-data-ingestion.md) · [All prompts](README.md)
