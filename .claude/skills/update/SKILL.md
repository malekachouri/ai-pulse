---
name: update
description: Update the user's local AI Pulse to the latest code from GitHub: pull main, rebuild and restart the Docker stack, run the smoke test, and explain what changed. Use when the user says they merged a pull request or asks to get the latest version on their computer.
argument-hint: "[--no-pull]"
disable-model-invocation: true
allowed-tools: Bash(./scripts/update.sh:*), Bash(git status:*), Bash(git log:*), Bash(git branch:*), Bash(docker compose ps:*), Bash(docker compose logs:*)
---

# /update: get the latest AI Pulse running

1. Check where the user is: `git status` and `git branch --show-current`.
   - On a branch other than `main`: tell the user and ask before switching (`git switch main`).
   - Local changes to tracked files: show them (`git status`) and ask whether to keep them
     (`git stash`) before going on. Never discard them yourself. Untracked files (for example a personal
     script) do not block the update.
2. Run, with a timeout of at least 30 minutes (rebuilding the images can take several minutes):

   ```bash
   ./scripts/update.sh $ARGUMENTS
   ```

   It pulls `main` (fast-forward only), rebuilds only what changed, restarts the stack and waits until every
   service is healthy (database migrations run on their own), then runs the smoke test.
3. Explain the result in plain words:
   - what changed: summarise the `New changes:` commit list in a few user-facing bullets (features, fixes);
     read `git log -p` for a commit when its title is unclear;
   - whether the smoke test passed, and the status of every service.
4. If something fails, find the cause before suggesting a fix:
   - a service is unhealthy: `docker compose logs --tail 80 <service>`. Right after an update `beat` can show
     unhealthy for up to about 3 minutes while it starts; check again before calling it a problem;
   - the build fails: show the failing step and its error;
   - `git pull` refuses (diverged history): explain, and do not force anything.
5. If the script printed `Note: .env.example changed`, explain each new setting it lists and whether the user
   needs it in their own `.env` (most have safe defaults; see `.env.example` and the module guide in `docs/`).
