# Contributing to Run, Forrest, Run!

Thanks for helping make the objective-runner platform clearer, safer, and more useful for both vibe coders and production teams.

## Quick start for developers

```bash
git clone https://github.com/youtextme/run-forrest-run.git
cd run-forrest-run
pip install -e ".[dev]"
pytest
```

## What to change where

| If you are changing… | Edit… | Also update… |
|---------------------|-------|--------------|
| Agent behavior / voice | Root [`SKILL.md`](SKILL.md) | [`RUN_FORREST_RUN.md`](RUN_FORREST_RUN.md) if tenets or loop change |
| Recruitment / stories | [`runforrestrun/recruitment.py`](runforrestrun/recruitment.py), [`stories.py`](runforrestrun/stories.py), [`initiative.py`](runforrestrun/initiative.py) | [`HOW_TO_BUILD.md`](HOW_TO_BUILD.md) science function; tests in [`tests/test_initiative.py`](tests/test_initiative.py) |
| Host install paths | [`runforrestrun/hosts.py`](runforrestrun/hosts.py) | [`HOW_TO_BUILD.md`](HOW_TO_BUILD.md) |
| Always-latest sync list | [`runforrestrun/upstream.py`](runforrestrun/upstream.py) `SYNC_FILES` | README “Why you always get the latest” |
| Model assessor / catalog | [`runforrestrun/assessor.py`](runforrestrun/assessor.py), [`runforrestrun/model_catalog.json`](runforrestrun/model_catalog.json) | SKILL “Model (bar raiser)”, README disk layout |
| Community loop catalog | [`runforrestrun/frontier.json`](runforrestrun/frontier.json) | Keep entries as methods, not tenets |
| CLI flags | [`runforrestrun/__main__.py`](runforrestrun/__main__.py) | README Commands table |
| Cached skills / patterns | [`runforrestrun/model_aware.py`](runforrestrun/model_aware.py) | [`runforrestrun/patterns.py`](runforrestrun/patterns.py), [`runforrestrun/cached_skills.py`](runforrestrun/cached_skills.py) |

## Design constraints (please keep)

1. **Forrest** — movie spelling, two r’s.
2. **Two lines** — every update is exactly two 🌲 lines.
3. **Tenets** — Atoms, Probe, Conservation only. Loops are methods in `frontier.json`.
4. **No PR per prompt** — platform proposals are foundational and opt-in with credit.
5. **Identity stripping** — observer and public observations never ship emails, paths, or names.
6. **Latest from main** — behavior files in `SYNC_FILES` are the contract; bump package version when Python API changes.
7. **Same model** — the assessor plugs deficiencies with extra research and effort. It never tells the agent to switch models.

## Pull requests

- One focused change per PR when possible.
- Include or update tests in [`tests/`](tests/) (`test_platform.py`, `test_model_aware.py`, …).
- Run `pytest` before opening.
- Update README if user-visible behavior changes.

## Code style

Match the existing module: small functions, typed where helpful, zero unnecessary dependencies, plain English docstrings.

## Questions

Open an issue with: what you tried, what you expected, and trail artifacts if relevant (redact secrets).
