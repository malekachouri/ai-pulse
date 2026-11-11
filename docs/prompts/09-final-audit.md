# Prompt 09: Senior engineering review (final audit)

| | |
|---|---|
| **Phase** | 9 of 9 |
| **Send it** | Last, after every implementation phase is merged. |
| **What it built in this repository** | A verified audit: live runs of every source, every API operation and every page, 22 bugs fixed, and docs/AUDIT_REPORT.md. |
| **Check before the next prompt** | Read docs/AUDIT_REPORT.md, especially §5 (what could not be verified) and §6 (credentials). |
| **Note from the guide** | Send this after Claude finishes all implementation phases. |

Paste everything in the box below into Claude Code, in the repository, as one message.

~~~text
Perform a complete technical audit of the AI Pulse application.

Act as a principal software architect, senior QA engineer, AI engineer and DevSecOps engineer.

Review the entire repository.
Frontend audit
- Check all pages and navigation.
- Check responsive layouts.
- Check all forms and interactions.
- Check API integration.
- Check authentication.
- Check loading, empty and error states.
- Check TypeScript errors.
- Check accessibility.
Backend audit
- Check all endpoints.
- Check database relationships.
- Check authorization.
- Check validation.
- Check exception handling.
- Check API documentation.
- Check performance.
AI audit
- Test all LLM providers.
- Test summarization.
- Test classification.
- Test duplicate detection.
- Test embeddings.
- Test semantic search.
- Test RAG citations.
- Check hallucination prevention.
- Check token consumption and cost tracking.
Data collection audit
- Test all connectors.
- Verify source URLs.
- Check timestamps.
- Check duplicate prevention.
- Check retries.
- Check rate limits.
- Check failed jobs.
- Verify that all external integrations respect their API requirements.
DevOps audit
- Validate Dockerfiles.
- Validate Docker Compose.
- Test migrations.
- Test CI/CD workflows.
- Check environment variables.
- Check health checks.
- Check monitoring.
- Check security scanning.
Final objective
Do not simply produce a list of problems.

Fix every issue you can reproduce.

Run the complete test suite and production build.

Create a final report containing:
1. Implemented features.
2. Fixed bugs.
3. Test results.
4. Security findings.
5. Remaining limitations.
6. External API credentials required.
7. Exact commands to run the application.
8. Deployment instructions.
Do not claim a feature works unless you have verified it.
~~~

Previous: [08](08-production-readiness.md) · Next: [additional features](10-additional-features.md) · [All prompts](README.md)
