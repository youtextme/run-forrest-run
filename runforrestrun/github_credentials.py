"""Install Girish Mahadevan's youtextme GitHub PAT for Cursor, Devin, OpenClaw, and all agents."""

from __future__ import annotations

import os
import shutil
import stat
from pathlib import Path

OWNER = "youtextme"
OWNER_NAME = "Girish Mahadevan"
ACCOUNT_LABEL = f"{OWNER_NAME} personal access token (classic PAT)"


def _home() -> Path:
    return Path.home()


def _agent_config() -> Path:
    return _home() / ".config" / "agent"


def _host_config_dirs() -> tuple[Path, ...]:
    home = _home()
    return (
        _agent_config(),
        home / ".config" / "cursor",
        home / ".config" / "devin",
        home / ".config" / "openclaw",
        home / ".devin",
        home / ".openclaw",
        home / ".cursor",
    )

CREDENTIALS_MD = f"""# GitHub credentials — {ACCOUNT_LABEL}

This machine is authorized as **`{OWNER}`** ({OWNER_NAME}) via a **classic personal access token**.

## Load before any GitHub work

```bash
source ~/.config/agent/github.env
# or: source ~/.config/cursor/github.env
# or: source ~/.config/devin/github.env
# or: source ~/.config/openclaw/github.env
```

## Files (never commit these)

| Path | Purpose |
|------|---------|
| `~/.config/agent/github.env` | Exports `GH_TOKEN` and `GITHUB_TOKEN` |
| `~/.config/agent/github_pat` | Raw PAT (`chmod 600`) |
| `~/.config/agent/load-github.sh` | One-liner loader for shells |
| `~/.config/gh/hosts.yml` | `gh` CLI auth as `{OWNER}` |
| `~/.git-credentials` | Git HTTPS push/pull |

Mirrored under `~/.config/cursor/`, `~/.config/devin/`, and `~/.config/openclaw/`.

## Agent rules

- This is **{OWNER_NAME}'s personal PAT** — not a shared bot token, not optional.
- **Never** commit, log, echo, or paste the token in chat, PRs, issues, or code.
- **Do not ask** the human for a GitHub token — read `~/.config/agent/github_pat` or source `github.env`.
- Scope: full repo access on `{OWNER}` **except delete repository**.
- Use for: `gh`, `git push`, create repos, PRs, Actions secrets, API calls.

## Verify

```bash
source ~/.config/agent/load-github.sh
gh auth status
```
"""

CURSOR_RULE = f"""---
description: GitHub PAT for {OWNER} — {ACCOUNT_LABEL} (always on)
alwaysApply: true
---

# GitHub — {ACCOUNT_LABEL}

- Machine auth: **`{OWNER}`** via classic PAT stored at `~/.config/agent/github_pat`.
- Before `gh`, `git push`, or GitHub API: `source ~/.config/agent/github.env`
- **Never** commit or paste the token. **Never** ask the human for a GitHub key.
- Full access except delete-repo. Docs: `~/.config/agent/GITHUB_CREDENTIALS.md`
"""

DEVIN_INSTRUCTIONS = f"""# Devin — GitHub auth

Devin on this machine uses **{OWNER_NAME}'s** classic GitHub PAT for **`{OWNER}`**.

```bash
source ~/.config/devin/github.env
gh auth status
```

- Token: `~/.config/devin/github_pat` (same as `~/.config/agent/github_pat`)
- Never commit or log the token. Never ask the user for a GitHub token.
- See `~/.config/agent/GITHUB_CREDENTIALS.md`
"""

OPENCLAW_AGENTS_BLOCK = f"""## GitHub — {ACCOUNT_LABEL}

- Auth: **`{OWNER}`** classic PAT on this machine (`~/.config/openclaw/github.env`).
- Load: `source ~/.config/openclaw/github.env` before any GitHub or git push work.
- **Never** commit, log, or paste the token. **Never** ask the human for a GitHub key.
- Full repo access except delete-repo. Details: `~/.config/agent/GITHUB_CREDENTIALS.md`
"""

WORKSPACE_AGENTS_BLOCK = f"""## GitHub — {ACCOUNT_LABEL}

- This machine uses **{OWNER_NAME}'s** classic PAT for GitHub account **`{OWNER}`**.
- Load before any GitHub work: `source ~/.config/agent/github.env`
- Token file: `~/.config/agent/github_pat` (chmod 600). Also mirrored for Cursor, Devin, OpenClaw.
- **Never** commit or paste the token. **Never** ask for a GitHub token — use the machine store.
- Scope: full repo access except delete repository.
"""


def _read_existing_token() -> str | None:
    candidates = [
        os.environ.get("GH_TOKEN"),
        os.environ.get("GITHUB_TOKEN"),
        _agent_config() / "github_pat",
        _home() / ".config" / "cursor" / "github_pat",
        _home() / ".config" / "devin" / "github_pat",
        _home() / ".config" / "openclaw" / "github_pat",
    ]
    for c in candidates:
        if not c:
            continue
        if isinstance(c, str) and c.startswith(("ghp_", "github_pat_")):
            return c.strip()
        path = Path(c)
        if path.is_file():
            text = path.read_text(encoding="utf-8").strip()
            if text:
                return text
    return None


def _write_secret(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body if body.endswith("\n") else body + "\n", encoding="utf-8")
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)


def _upsert_agents_block(path: Path, block: str, marker: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else "# AGENTS.md\n"
    if marker in existing:
        start = existing.index(marker)
        rest = existing[start + len(marker) :]
        nxt = rest.find("\n## ")
        after = rest[nxt + 1 :] if nxt >= 0 else ""
        text = existing[:start] + block.rstrip() + ("\n\n" + after if after else "\n")
    else:
        text = existing.rstrip() + "\n\n" + block
    _write_secret(path, text)


def install_github_credentials(
    *,
    token: str | None = None,
    project_root: Path | None = None,
) -> dict:
    """Write PAT to all host config dirs and install agent instructions."""
    pat = (token or _read_existing_token() or "").strip()
    if not pat:
        return {"ok": False, "error": "no token found; set GH_TOKEN or ~/.config/cursor/github_pat"}

    env_body = f'export GH_TOKEN="{pat}"\nexport GITHUB_TOKEN="{pat}"\n'
    load_sh = """#!/usr/bin/env bash
set -a
for f in \\
  "${HOME}/.config/agent/github.env" \\
  "${HOME}/.config/cursor/github.env" \\
  "${HOME}/.config/devin/github.env" \\
  "${HOME}/.config/openclaw/github.env"; do
  if [ -f "$f" ]; then source "$f"; set +a; exit 0; fi
done
set +a
echo "No github.env found" >&2
exit 1
"""
    gh_yaml = f"""github.com:
    user: {OWNER}
    git_protocol: https
    oauth_token: {pat}
    users:
        {OWNER}:
            oauth_token: {pat}
"""

    written: list[str] = []
    for base in _host_config_dirs():
        base.mkdir(parents=True, exist_ok=True)
        for name, body in (
            ("github_pat", pat + "\n"),
            ("github.env", env_body),
            ("GITHUB_CREDENTIALS.md", CREDENTIALS_MD),
        ):
            p = base / name
            _write_secret(p, body)
            written.append(str(p))
        loader = base / "load-github.sh"
        _write_secret(loader, load_sh)
        os.chmod(loader, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        written.append(str(loader))

    gh_dir = _home() / ".config" / "gh"
    gh_dir.mkdir(parents=True, exist_ok=True)
    _write_secret(gh_dir / "hosts.yml", gh_yaml)
    _write_secret(gh_dir / "config.yml", "git_protocol: https\n")
    _write_secret(_home() / ".git-credentials", f"https://{OWNER}:{pat}@github.com\n")
    written.extend([str(gh_dir / "hosts.yml"), str(_home() / ".git-credentials")])

    root = (project_root or Path.cwd()).resolve()
    home = _home()

    # Cursor — always-on rule (world-readable so IDE/agents can load it)
    for rules_dir in (root / ".cursor" / "rules", home / ".cursor" / "rules"):
        rule = rules_dir / "github-credentials.mdc"
        rule.parent.mkdir(parents=True, exist_ok=True)
        rule.write_text(CURSOR_RULE if CURSOR_RULE.endswith("\n") else CURSOR_RULE + "\n", encoding="utf-8")
        os.chmod(rule, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH | stat.S_IWUSR)
        written.append(str(rule))

    # Devin — project + home instructions (world-readable)
    for devin_dir in (root / ".devin", home / ".devin"):
        doc = devin_dir / "GITHUB_CREDENTIALS.md"
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_text(DEVIN_INSTRUCTIONS if DEVIN_INSTRUCTIONS.endswith("\n") else DEVIN_INSTRUCTIONS + "\n", encoding="utf-8")
        os.chmod(doc, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH | stat.S_IWUSR)
        written.append(str(doc))

    # OpenClaw + workspace AGENTS.md
    marker = "## GitHub —"
    for agents_path in (
        root / "AGENTS.md",
        root / "run-forrest-run" / "AGENTS.md",
        home / ".openclaw" / "workspace" / "AGENTS.md",
        home / ".openclaw" / "AGENTS.md",
    ):
        if agents_path == root / "run-forrest-run" / "AGENTS.md" and not agents_path.exists():
            continue
        _upsert_agents_block(agents_path, OPENCLAW_AGENTS_BLOCK, marker)
        written.append(str(agents_path))

    # Workspace root AGENTS (figureitout monorepo)
    if (root / "figureitout").exists() or (root / "AGENTS.md").exists():
        _upsert_agents_block(root / "AGENTS.md", WORKSPACE_AGENTS_BLOCK, marker)
        if str(root / "AGENTS.md") not in written:
            written.append(str(root / "AGENTS.md"))

    # Also mirror to /home/ubuntu if different from current home
    alt_home = Path("/home/ubuntu")
    if alt_home != home and alt_home.exists():
        for sub in ("config/agent", "config/cursor", "config/devin", "config/openclaw"):
            d = alt_home / sub
            d.mkdir(parents=True, exist_ok=True)
            _write_secret(d / "github_pat", pat + "\n")
            _write_secret(d / "github.env", env_body)

    return {
        "ok": True,
        "account": OWNER,
        "owner": OWNER_NAME,
        "canonical": str(_agent_config()),
        "written": written,
        "hosts": ["cursor", "devin", "openclaw", "gh", "git"],
    }
