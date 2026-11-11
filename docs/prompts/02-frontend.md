# Prompt 02: Complete user interface

| | |
|---|---|
| **Phase** | 2 of 9 |
| **Send it** | After prompt 01 is merged and its tests pass. |
| **What it built in this repository** | App shell, 13 pages, dashboard, article cards, URL-synced filters, bookmarks, notifications, preferences, a clearly labelled demo mode. |
| **Check before the next prompt** | `cd frontend && npm run lint && npm run typecheck && npm test && npm run build`; open every page on a phone-sized window. |

Paste everything in the box below into Claude Code, in the repository, as one message.

~~~text
Continue the AI Pulse project.

Act as a senior frontend engineer and UI/UX designer.

Build a complete professional SaaS interface using Next.js, TypeScript, Tailwind CSS, shadcn/ui and Lucide icons.
Design direction
Create a modern technology intelligence dashboard inspired by professional SaaS analytics platforms.

Visual style:
- Premium dark navy theme with optional light mode.
- Blue and violet accent colors.
- Clean typography.
- Elegant cards.
- Consistent spacing.
- Responsive layouts.
- Smooth but subtle animations.
- Professional charts and data visualizations.
Main layout
Create:
- Collapsible sidebar.
- Top navigation.
- Global search.
- Notification center.
- User profile menu.
- Theme switcher.
- Main content area.
Sidebar navigation
1. Overview
2. AI News
3. AI Models
4. AI Tools
5. Research Papers
6. GitHub Radar
7. Bugs & Failures
8. Security & CVEs
9. DevOps & Cloud
10. Daily Briefing
11. Bookmarks
12. Analytics
13. Settings
Dashboard
Display:
- Total collected articles.
- AI model releases.
- New GitHub issues.
- Critical vulnerabilities.
- Active incidents.
- Trending technologies.
- Latest AI announcements.
- Important security alerts.
- Recent software failures.
- Daily AI briefing preview.
- News distribution chart.
- Activity timeline.
News feed
Create reusable article cards containing:
- Title.
- Description.
- Source.
- Category.
- Publication date.
- Importance score.
- Severity when applicable.
- AI-generated summary.
- Original source link.
- Bookmark action.
- Read/unread status.
Filtering and search
Implement:
- Search by title and content.
- Category filters.
- Source filters.
- Date range.
- Severity filters.
- Importance filters.
- Sorting by latest, relevance and importance.
- Pagination.
Pages
Implement all sidebar pages with consistent reusable components.

Use realistic-looking UI states, but clearly mark mock data as demo data until real API integration is complete.

Do not build static screenshots. Implement functional components and connect them to backend APIs.

Ensure mobile, tablet and desktop responsiveness.
~~~

Previous: [01](01-project-foundation.md) · Next: [03](03-backend-api.md) · [All prompts](README.md)
