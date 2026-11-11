# Prompt 08: Production readiness

| | |
|---|---|
| **Phase** | 8 of 9 |
| **Send it** | After prompt 07. |
| **What it built in this repository** | Hardened images, Compose dev/prod, CI/CD with Trivy/CodeQL/audits and provenance, Prometheus/Grafana/alerts, rate limiting, secrets, admin console, backups (docs/DEPLOYMENT.md). |
| **Check before the next prompt** | CI is green on the pull request; `./scripts/smoke-test.sh http://localhost:3000` passes; a backup restores. |

Paste everything in the box below into Claude Code, in the repository, as one message.

~~~text
Act as a senior DevOps, Cloud and Platform Engineer.

Prepare AI Pulse for production deployment.
1. Docker
Create optimized Dockerfiles for:
- Next.js frontend.
- FastAPI backend.
- Celery worker.
- Celery Beat.
- PostgreSQL.
- Redis.
Create Docker Compose configurations for development and production.

Implement:
- Health checks.
- Persistent volumes.
- Internal networking.
- Environment configuration.
- Non-root containers where possible.
- Restart policies.
- Resource limits.
2. CI/CD
Create GitHub Actions workflows for:
- Frontend linting.
- TypeScript validation.
- Backend linting.
- Python tests.
- Integration tests.
- Docker image builds.
- Container vulnerability scanning.
- Deployment workflows.
Use secure GitHub Actions permissions and secrets.
3. Monitoring
Integrate:
- Prometheus.
- Grafana.
- Structured application logs.
Monitor:
- API latency.
- Error rates.
- Database connections.
- Celery queue length.
- Failed ingestion jobs.
- Data source availability.
- AI provider errors.
- Token usage and cost.
- Background job execution time.
Create useful Grafana dashboards and alert rules.
4. Admin dashboard
Implement:
- User management.
- Role management.
- Source management.
- Connector health.
- Ingestion job history.
- Failed task management.
- AI provider configuration.
- Usage statistics.
- System health.
- Audit logs.
5. Security
Implement:
- Secure secrets management.
- Input validation.
- Rate limiting.
- CORS configuration.
- Authentication and authorization.
- Secure cookies.
- Dependency scanning.
- Container scanning.
- Database backup procedures.
6. Documentation
Create:
- README.md.
- ARCHITECTURE.md.
- API documentation.
- DATABASE.md.
- DEVELOPMENT.md.
- DEPLOYMENT.md.
- SECURITY.md.
- CONTRIBUTING.md.
- .env.example.
7. Final validation
Run:
- All frontend tests.
- All backend tests.
- Database migration tests.
- Integration tests.
- Docker Compose validation.
- Production build.
- Security checks.
Fix errors instead of hiding or suppressing them.

Provide exact startup commands.

Do not claim production readiness until the validation checks have actually passed.
~~~

Previous: [07](07-briefings-notifications.md) · Next: [09](09-final-audit.md) · [All prompts](README.md)
