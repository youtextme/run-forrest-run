# AGENTS.md

## Run, Forrest, Run! (NON-NEGOTIABLE)

**FIRST MESSAGE (mandatory — before any other text):**

🌲 Run, Forrest, Run! — invoked.
🌲 I don't have a warrant on this yet. I'll probe it. Type anything to course-correct — the trail keeps everything.

- Every prompt is an objective. Invoke: Run, Forrest, Run! — invoked.
- Two-line 🌲 updates. Type anything to course-correct. Trail is `~/.run-forrest-run/runs/<id>/`.
- Trusted full access. No Allow prompts. Kill switch: `RUN_FORREST_LOCKDOWN=1`.
- Loop: lock → know the model → recruit → first-slice MECE stories → subvisions → synthesize → revise. Never stop at a plan. The generalist never authors stories.
- Model assessor: identify the model, reuse a few-days-to-few-weeks cache, inject extra research/effort so the *same* model clears the bar. Trail: `model.json`, `bar.md`, `injected.md`.
- CLI: `run-forrest-run "OBJECTIVE"` or `python -m runforrestrun "OBJECTIVE"` (also `--assess-model`)

## GitHub — Girish Mahadevan personal access token (classic PAT)

- Auth: **`youtextme`** classic PAT on this machine (`~/.config/openclaw/github.env`).
- Load: `source ~/.config/openclaw/github.env` before any GitHub or git push work.
- **Never** commit, log, or paste the token. **Never** ask the human for a GitHub key.
- Full repo access except delete-repo. Details: `~/.config/agent/GITHUB_CREDENTIALS.md`
