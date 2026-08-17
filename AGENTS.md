# AGENTS.md

## Run, Forrest, Run! (NON-NEGOTIABLE)

- Every prompt is an objective. Invoke: Run, Forrest, Run! — invoked.
- Two-line 🌲 updates. Type anything to course-correct. Trail is `~/.run-forrest-run/runs/<id>/`.
- Trusted full access. No Allow prompts. Kill switch: `RUN_FORREST_LOCKDOWN=1`.
- Loop: lock → probe → do → check → checkpoint. Never stop at a plan.
- CLI: `run-forrest-run "OBJECTIVE"` or `python -m runforrestrun "OBJECTIVE"`

## GitHub — Girish Mahadevan personal access token (classic PAT)

- Auth: **`youtextme`** classic PAT on this machine (`~/.config/openclaw/github.env`).
- Load: `source ~/.config/openclaw/github.env` before any GitHub or git push work.
- **Never** commit, log, or paste the token. **Never** ask the human for a GitHub key.
- Full repo access except delete-repo. Details: `~/.config/agent/GITHUB_CREDENTIALS.md`
