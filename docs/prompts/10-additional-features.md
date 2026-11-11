# Next: additional features

The original guide recommends these once the MVP works. **Built so far:** AI change detection, the
Learning Assistant and personalised learning recommendations (see docs/AI.md). The others are not built
yet. Each prompt below
is written for the current repository, so it can be sent as is, one at a time, after `main` is green.

Previous: [09](09-final-audit.md) · [All prompts](README.md)

## Technology watchlist

~~~text
Continue the existing AI Pulse repository. Add a Technology Watchlist: users follow specific models,
frameworks, repositories and technologies (reuse the existing followed_* preferences), see a dedicated
"Watchlist" page with everything new about them, and get a notification when a followed item changes.
Keep every item linked to its original source. Add tests, update docs, and keep CI green.
~~~

## AI change detection (built)

~~~text
Continue the existing AI Pulse repository. Add AI Change Detection: when a new release of a model, tool or
repository is collected, compare it with the previous release (changelog, version, license, benchmarks
quoted by the source) and show "what changed" with citations to both sources. Never invent differences:
if the sources do not say, show "not documented". Add tests with recorded data, update docs.
~~~

## Bug intelligence agent

~~~text
Continue the existing AI Pulse repository. Add a Bug Intelligence explanation to bug and CVE pages: why it
occurs, impact, affected versions and available fixes, generated only from the collected official
sources (issue, advisory, CVE record, release notes) with citations, using the existing grounding checks.
Show "insufficient information" when the sources do not cover it. Add tests, update docs/AI.md.
~~~

## AI model comparison

~~~text
Continue the existing AI Pulse repository. Add an AI Comparison page that compares models (e.g. GPT,
Claude, Gemini, Llama) only with benchmarks and facts taken from collected, cited sources, with the date
and source of each number. No number without a source. Add tests and docs.
~~~

## Learning assistant (built)

~~~text
Continue the existing AI Pulse repository. Add a Learning Assistant that turns the day's important news
and papers into short technical lessons, linked to the curated official documentation already in
app/ai/learning.py, personalised by followed technologies. Label everything as AI-generated. Add tests.
~~~

## Weekly intelligence report (PDF)

~~~text
Continue the existing AI Pulse repository. Add a Weekly Intelligence Report: a PDF generated every Monday
in the user's timezone from the week's briefings (sections, citations, links), downloadable from the
Briefing page and optionally emailed with the existing SMTP sender. Add tests and docs.
~~~

## Personalised learning recommendations (built)

~~~text
Continue the existing AI Pulse repository. Add personalised recommendations of what to learn next, based
on followed technologies, read and bookmarked items, explained ("because you follow vLLM and read …").
Recommendations only point to collected items and curated official documentation. Add tests and docs.
~~~

## Offsite backups (deferred)

~~~text
Continue the existing AI Pulse repository. Copy every backup offsite (S3-compatible storage, encrypted,
with retention) in addition to the local volume, and extend the restore drill to restore from the offsite
copy. Credentials as Docker secrets. Update docs/DEPLOYMENT.md §5 and keep the CI drill green.
~~~
