---
name: reanalyse
description: Analyse one AI Pulse item again with the AI model now (a CVE such as CVE-2026-125331, an item id, or a canonical key), replacing its old AI summary, then report the new result. Use when an analysis is outdated or wrong, or after the AI prompts or rules changed.
argument-hint: "<CVE-id | item-id | canonical-key>"
disable-model-invocation: true
allowed-tools: Bash(docker compose exec -T api python -m app.cli reanalyse:*), Bash(docker compose ps:*), Bash(docker compose logs:*)
---

# /reanalyse: analyse one item again

The target is `$ARGUMENTS`. If it is empty, ask the user which CVE or item to analyse (they can copy the CVE
id from the item's page) and stop.

1. Check the stack runs: `docker compose ps api`. If `api` is not running or not healthy, tell the user to
   start it (`docker compose up -d --wait`) and stop.
2. Run, with a timeout of at least 20 minutes (a small local model on a CPU can take several minutes):

   ```bash
   docker compose exec -T api python -m app.cli reanalyse $ARGUMENTS
   ```

3. Read the result and explain it simply:

   | Output | Meaning and next step |
   |---|---|
   | `items found: N  analysed: N` and exit code 0 | Done. Reload the item's page: the analysis date is today's. For a CVE, N counts every copy of it (NVD, GitHub advisory, ...); only the main one is analysed by the AI. |
   | `No item found` (exit 2) | The CVE or item is not in the database (not collected yet, or a typo). |
   | `Another analysis run is in progress` (exit 3) | The background worker is analysing other items; nothing was changed. Wait a few minutes and run `/reanalyse` again, or pause the worker with `docker compose stop worker beat`, run it, then `docker compose start worker beat`. Ask the user before stopping services. |
   | `failed: 1` (exit 1) | The AI model did not answer correctly. Show the error, then look at the model's logs: for Ollama on WSL, `journalctl -u ollama --since "15 min ago"`. A timeout means the model is too slow for `LLM_TIMEOUT_SECONDS` in `.env`. |
   | `note: no AI model is configured` | Only the rule-based analysis ran. The AI model is set in `.env` (`LLM_PROVIDER`, `LLM_MODEL`): see `docs/AI.md`. |

4. The Bug intelligence panel on the item's page is separate: the user refreshes it with its own
   **Regenerate with AI** button.
