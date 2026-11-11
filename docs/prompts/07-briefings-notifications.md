# Prompt 07: Daily briefing and notifications

| | |
|---|---|
| **Phase** | 7 of 9 |
| **Send it** | After prompt 06. |
| **What it built in this repository** | 10-section personalised briefings in the user's timezone, 'what changed', notification center and per-kind preferences (docs/NOTIFICATIONS.md). |
| **Check before the next prompt** | Generate a briefing from the Briefing page; follow a technology in Settings and check the notifications. |

Paste everything in the box below into Claude Code, in the repository, as one message.

~~~text
Implement the complete Daily Intelligence and Notification system.
Daily briefing
Generate a personalized briefing for every user according to their interests.

Users can select:
- AI Engineering.
- Generative AI.
- RAG.
- AI Agents.
- LLMOps.
- DevOps.
- Cloud.
- Kubernetes.
- Cybersecurity.
- Software Engineering.
Each briefing must include:
1. Executive summary.
2. Most important AI news.
3. New model releases.
4. New tools and frameworks.
5. Research papers.
6. Important bugs.
7. Critical vulnerabilities.
8. Cloud and infrastructure incidents.
9. What changed since the previous briefing.
10. Recommended learning activities.
Notifications
Implement:
- In-app notifications.
- Critical alert notifications.
- New model release notifications.
- Bug and vulnerability notifications.
- Daily briefing notifications.
Create notification preferences.
User experience
Users should be able to:
- Mark notifications as read.
- Save important articles.
- Follow technologies.
- Follow GitHub repositories.
- Follow AI providers.
- Select notification severity.
- Configure briefing frequency.
Scheduling
Use Celery Beat or an equivalent scheduler.

Implement configurable schedules, timezone support, retries and idempotency.

Avoid sending duplicate notifications.

Create tests for scheduling, preferences and notification delivery.

Build the complete frontend pages and integrate them with the backend.
~~~

Previous: [06](06-bugs-failures-radar.md) · Next: [08](08-production-readiness.md) · [All prompts](README.md)
