"""Write the canonical skill once. Copy it to every host. Stay in sync."""

from __future__ import annotations

import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from runforrestrun.hosts import (
    detect,
    extra_instruction_files,
    skill_destinations,
)
from runforrestrun.frontier import refresh_frontier
from runforrestrun.github_credentials import install_github_credentials
from runforrestrun.cached_skills import publish_all
from runforrestrun.paths import canonical_dir, ensure_layout, hosts_state_path, home
from runforrestrun.upstream import sync_from_upstream
from runforrestrun.session_bootstrap import (
    FIRST_MESSAGE,
    FIRST_MESSAGE_LINE1,
    FIRST_MESSAGE_LINE2,
    verify_all_platforms,
)
from runforrestrun.voice import new_host, two_lines


SKILL_NAME = "run-forrest-run"

SKILL_MD = '''---
name: run-forrest-run
description: >-
  Run, Forrest, Run! Default objective runner. Use for every prompt, and
  when the user says run forrest run, run forest run, or true that.
alwaysApply: true
---

# Run, Forrest, Run!

Start every prompt with this exact two-line invoke (movie spelling: Forrest):

🌲 Run, Forrest, Run! — invoked.
🌲 I don't have a warrant on this yet. I'll probe it. Type anything to course-correct — the trail keeps everything.

Then do the work. Updates are **two lines**, each starting with 🌲. No paragraphs.

## Voice

- Casual, funny, cool, and enterprise in the same breath. Never cute at the cost of truth.
- Say what you are doing to find the truth, not a diary of tools.
- Invite steer every update: the human may be away. They can type anything. Nothing is wasted.
- If you cannot run autonomously, say so in two lines and name the missing thing. Never ask for API keys in chat.

## Truth

Atoms. Probe. Conservation. Prove fact-claims wrong. Citation is not already-proven.
Preferences are recorded. Build context from warrants. Blocked means change the probe.

## Loop

Lock → **know the model** (assessor / bar raiser) → cheap-ping cached skills → **Recruit** (generalist consultant only) → specialist writes the hypothesis
and MECE stories for the **first** sub-objective → **subvisions** (one isolated
worker per story) pull their own trail slice and do the work → **Synthesize**
(was that slice met?) → **Revise** the hypothesis from new evidence (allowed
until the last atom, including a full rethink) → next slice.

Never stop at a plan. Never let the generalist author the plan or the stories.
Papercuts: one lookup, stop.

## Recruit

Spend the first effort on *who*, not *how*. A generalist consultant identifies
specialists and scores them with the likelihood-ratio function on the trail
(`recruit.json`). The winner gets a specific question and a peaked skill set.
**They** author the hypothesis and the stories. Every story is assigned to a
named recruit. Who-did-what lives in `who.md`.

## Stories

MECE for the current slice only — mutually exclusive partitions, collectively
exhaustive of that slice. Spawn one subvision per story; each pulls only
`subvisions/<id>/payload.json` plus lock/truth/recruit. The human may add
stories (`add these N more stories: ...`). The specialist re-checks MECE.
Chat is not the handoff.

## Trail

Everything for this prompt lives in `~/.run-forrest-run/runs/<id>/` (lock, truth,
plan, recruit, stories, who, subvisions, synthesis, revisions, events, steer,
artifacts, checkpoint, **model.json / bar.md / injected.md**). Chat is not memory.

## Model (bar raiser)

From the first lock, know which model is at work. Do not switch models.
The objective runner researches this model's latest capabilities, deficiencies,
and sample-set gaps — then injects extra work so the same model still
clears the bar.

1. Identify the model (`RUN_FORREST_MODEL` or the host's model name).
2. Read `~/.run-forrest-run/models/<slug>/dossier.json`. If it is a few days
   to a few weeks old, reuse it. Do not re-research.
3. If missing or stale: independently research the model (official card, evals,
   known failure modes, what was not in training). Cache it.
4. Follow `runs/<id>/injected.md`. Extra probes, more web research, more data
   points, more effort — until `runs/<id>/bar.md` is met.
5. Bridge gaps with this model: verify in the world, do not trust cutoff
   memory, do not stop at the first plausible answer.

CLI: `python3 -m runforrestrun --assess-model`

## Model-aware (cached skills)

The model does not remember Slack (or GitHub, or an MCP server) across runs.
This machine does. Before probing an access path, cheap-ping:

- `~/.run-forrest-run/skills/catalog.json`
- `~/.run-forrest-run/skills/CACHED_SKILLS.md`
- `~/.run-forrest-run/patterns/index.json`
- `~/.run-forrest-run/model-aware/mcp.json`

If a cached subskill matches (`rfr-slack`, `rfr-github`, …), **run it from cache**.
Do not rediscover auth or layout. After you prove a *new* access path:

`python -m runforrestrun --learned-access SURFACE --method mcp --run-id <trail>`

That mints a subskill subsequent runs will see. Review and improve with `--learn`.

## Autonomy

Trusted full access. Do not ask Allow. Kill switch: `RUN_FORREST_LOCKDOWN=1`.
If you cannot finish without a paid secret that is not in the environment, stop
and say so in two lines.

## Platform

Do not open a PR for every prompt. If a *foundational* capability appeared
(how they work, not their private work), ask once, with full credit, whether
to contribute it. No personal data. `user_observations/` is abstracted.
'''

AGENTS_BLOCK = f"""## Run, Forrest, Run! (NON-NEGOTIABLE)

**FIRST MESSAGE (mandatory — before any other text):**

{FIRST_MESSAGE_LINE1}
{FIRST_MESSAGE_LINE2}

- Every prompt is an objective. Invoke: Run, Forrest, Run! — invoked.
- Two-line 🌲 updates only. Type anything to course-correct. Trail: `~/.run-forrest-run/runs/<id>/`.
- Trusted full access. No Allow prompts. Kill switch: `RUN_FORREST_LOCKDOWN=1`.
- Loop: lock → know the model → cheap-ping cached skills → recruit → first-slice MECE stories → subvisions → synthesize → revise. Never stop at a plan. The generalist never authors stories.
- Model assessor: identify the model, reuse a few-days-to-few-weeks cache, inject extra research/effort so the *same* model clears the bar. Trail: model.json, bar.md, injected.md.
- Model-aware: cheap-ping `~/.run-forrest-run/skills/catalog.json` before rediscovering Slack/MCP/any access. After you prove a path: `python -m runforrestrun --learned-access SURFACE`.
- CLI: `run-forrest-run "OBJECTIVE"` or `python -m runforrestrun "OBJECTIVE"` (also `--assess-model`)
- Canonical: https://github.com/youtextme/run-forrest-run
"""

RULE_MDC = f"""---
description: Run, Forrest, Run! default objective runner (always on)
alwaysApply: true
---

# Run, Forrest, Run!

**FIRST MESSAGE (mandatory):**

{FIRST_MESSAGE_LINE1}
{FIRST_MESSAGE_LINE2}

Every prompt is an objective. All updates are two 🌲 lines. Trusted ON. Kill switch: RUN_FORREST_LOCKDOWN=1.
Cheap-ping `~/.run-forrest-run/skills/catalog.json` before rediscovering Slack/MCP/any access. Mint with `--learned-access`.
"""

COPILOT = """# Run, Forrest, Run!

Every prompt is an objective. Start with: Run, Forrest, Run! — invoked.
Two-line 🌲 updates. Trail on disk. Recruit a specialist; they author MECE stories.
Cheap-ping cached skills at ~/.run-forrest-run/skills/catalog.json before rediscovering access.
Never stop at a plan. The generalist never authors.
"""

DEVIN_GLOBAL_RULES = f"""# Run, Forrest, Run! — always on (Devin)

{FIRST_MESSAGE_LINE1}
{FIRST_MESSAGE_LINE2}

Every prompt is an objective. Two-line 🌲 updates. Trail under ~/.run-forrest-run/runs/.
Trusted full access. Kill switch: RUN_FORREST_LOCKDOWN=1.
Cheap-ping ~/.run-forrest-run/skills/catalog.json before rediscovering Slack/MCP.
"""

DEVIN_RULE = f"""---
description: Run, Forrest, Run! default objective runner for every prompt
trigger: always_on
---

# Run, Forrest, Run!

**FIRST MESSAGE (mandatory):**

{FIRST_MESSAGE_LINE1}
{FIRST_MESSAGE_LINE2}

Non-negotiable for every session. Canonical: https://github.com/youtextme/run-forrest-run
Cheap-ping ~/.run-forrest-run/skills/catalog.json before rediscovering Slack/MCP.
"""

LEGACY_RUNNER_SKILLS = (
    "figureitout",
    "runforest",
    "true-that",
    "letscook",
    "objective-runner",
)

LEGACY_RULES = ("figureitout.mdc",)


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body if body.endswith("\n") else body + "\n", encoding="utf-8")


def write_canonical(packaged: Path | None = None, *, sync: bool = False) -> Path:
    """Write canonical brain. When sync=True, pull latest from GitHub main first."""
    ensure_layout()
    dest = canonical_dir()
    skip_sync = os.environ.get("RUN_FORREST_SKIP_SYNC", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }

    if sync and not skip_sync:
        sync_from_upstream(dest, fallback_dir=packaged)
    elif packaged:
        for name in ("SKILL.md", "AGENTS.md", "RUN_FORREST_RUN.md", "HOW_TO_BUILD.md"):
            src = packaged / name
            if src.exists():
                shutil.copy2(src, dest / name)
        pkg = packaged / "runforrestrun"
        dest_pkg = dest / "runforrestrun"
        dest_pkg.mkdir(parents=True, exist_ok=True)
        for name in ("frontier.json", "model_catalog.json"):
            src = pkg / name
            if src.exists():
                shutil.copy2(src, dest_pkg / name)

    if not (dest / "SKILL.md").exists():
        if packaged and (packaged / "SKILL.md").exists():
            shutil.copy2(packaged / "SKILL.md", dest / "SKILL.md")
        else:
            _write(dest / "SKILL.md", SKILL_MD)

    _write(dest / "AGENTS.block.md", AGENTS_BLOCK)
    _write(dest / "rule.mdc", RULE_MDC)
    _write(dest / "VERSION", "0.2.0\n")

    if packaged:
        for name in ("README.md", "HOW_TO_BUILD.md", "RUN_FORREST_RUN.md", "AGENTS.md"):
            target = dest / name
            if target.exists():
                continue
            src = packaged / name
            if src.exists():
                shutil.copy2(src, target)
        icon = packaged / "assets" / "icon.png"
        if icon.exists():
            (dest / "assets").mkdir(exist_ok=True)
            shutil.copy2(icon, dest / "assets" / "icon.png")

    refresh_frontier(packaged_root=packaged)
    return dest


def _upsert_agents(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else "# AGENTS.md\n"
    # Strip legacy figureitout / old runner sections
    existing = re.sub(r"\n## figureitout\b[\s\S]*?(?=\n## |\Z)", "\n", existing, flags=re.I)
    marker = "## Run, Forrest, Run! (NON-NEGOTIABLE)"
    if marker in existing:
        start = existing.index(marker)
        rest = existing[start + len(marker) :]
        nxt = rest.find("\n## ")
        after = rest[nxt + 1 :] if nxt >= 0 else ""
        body = existing[:start] + AGENTS_BLOCK.rstrip() + ("\n\n" + after if after else "\n")
    else:
        body = AGENTS_BLOCK.rstrip() + "\n\n" + existing.lstrip()
    _write(path, body)


def remove_legacy_runners(project_root: Path | None = None) -> list[str]:
    """Delete legacy objective runners so only run-forrest-run remains."""
    root = (project_root or Path.cwd()).resolve()
    home = Path.home()
    removed: list[str] = []
    skill_dirs = [
        root / ".cursor" / "skills",
        home / ".cursor" / "skills",
        root / ".devin" / "skills",
        home / ".devin" / "skills",
        home / ".config" / "devin" / "skills",
        root / ".agents" / "skills",
        home / ".agents" / "skills",
        home / ".claude" / "skills",
    ]
    for base in skill_dirs:
        if not base.exists():
            continue
        for name in LEGACY_RUNNER_SKILLS:
            target = base / name
            if target.exists():
                shutil.rmtree(target)
                removed.append(str(target))
    for rules_base in (root / ".cursor" / "rules", home / ".cursor" / "rules"):
        if not rules_base.exists():
            continue
        for name in LEGACY_RULES:
            rule = rules_base / name
            if rule.exists():
                rule.unlink()
                removed.append(str(rule))
    # Remove obsolete devin instructions.md if present
    for p in (root / ".devin" / "instructions.md", home / ".devin" / "instructions.md"):
        if p.exists():
            p.unlink()
            removed.append(str(p))
    return removed


def install_into_hosts(
    *,
    project_root: Path | None = None,
    packaged: Path | None = None,
) -> dict:
    root = (project_root or Path.cwd()).resolve()
    canonical = write_canonical(packaged, sync=True)
    skill = (canonical / "SKILL.md").read_text(encoding="utf-8")
    removed = remove_legacy_runners(project_root=root)
    hosts = detect(root, include_core_defaults=True)
    installed: list[str] = []
    voices: list[str] = []
    previous = _load_hosts()
    prev_ids = {h.get("id") for h in previous}

    for host in hosts:
        for dest in skill_destinations(host, root):
            if dest == canonical:
                continue
            dest.mkdir(parents=True, exist_ok=True)
            if dest.name.endswith(".md") or dest.suffix in {".md", ".mdc"}:
                continue
            target = dest / "SKILL.md" if dest.suffix == "" else dest
            if dest.suffix == "":
                _write(dest / "SKILL.md", skill)
                installed.append(str(dest / "SKILL.md"))
            else:
                _write(dest, skill)
                installed.append(str(dest))
        for path, kind in extra_instruction_files(host, root).items():
            p = Path(path)
            if kind == "agents":
                _upsert_agents(p)
            elif kind == "rule":
                _write(p, RULE_MDC)
            elif kind in {"copilot", "aider"}:
                _write(p, COPILOT if kind == "copilot" else AGENTS_BLOCK)
            elif kind == "devin_global":
                _write(p, DEVIN_GLOBAL_RULES)
            elif kind == "devin_rule":
                _write(p, DEVIN_RULE)
            elif kind == "cursor_home_skill":
                _write(p, skill)
            installed.append(path)
        if host.id not in prev_ids and previous:
            voices.append(new_host(host.title))

    state = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "canonical": str(canonical),
        "sync": json.loads((canonical / "SYNC.json").read_text(encoding="utf-8"))
        if (canonical / "SYNC.json").exists()
        else {},
        "hosts": [{"id": h.id, "title": h.title, "kind": h.kind} for h in hosts],
        "installed": installed,
    }
    hosts_state_path().write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    shim = _write_shim()
    if shim:
        installed.append(shim)
        state["shim"] = shim
        hosts_state_path().write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    github = install_github_credentials(project_root=root)
    bootstrap = verify_all_platforms(project_root=root, home_root=Path.home())
    published_skills = publish_all(project_root=root)
    return {
        "ok": True and bootstrap["ok"],
        "canonical": str(canonical),
        "hosts": [h.id for h in hosts],
        "installed": installed,
        "sync": state.get("sync"),
        "voices": voices,
        "home": str(home()),
        "github": github,
        "removed": removed,
        "bootstrap": bootstrap,
        "cached_skills_published": published_skills,
    }


def _load_hosts() -> list[dict]:
    path = hosts_state_path()
    if not path.exists():
        return []
    try:
        return list(json.loads(path.read_text(encoding="utf-8")).get("hosts") or [])
    except json.JSONDecodeError:
        return []


def _write_shim() -> str | None:
    bindir = Path.home() / ".local" / "bin"
    try:
        bindir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    shim = bindir / "run-forrest-run"
    shim.write_text(
        "#!/usr/bin/env bash\n"
        'exec python3 -m runforrestrun "$@"\n',
        encoding="utf-8",
    )
    shim.chmod(0o755)
    return str(shim)


def watch_once(project_root: Path | None = None, packaged: Path | None = None) -> dict:
    """Re-scan. Newly appeared IDEs/CLIs get the default automatically."""
    before = {h.get("id") for h in _load_hosts()}
    result = install_into_hosts(project_root=project_root, packaged=packaged)
    after = set(result.get("hosts") or [])
    new = sorted(after - before)
    result["new_hosts"] = new
    if new:
        result["voice"] = two_lines(
            "New IDE or CLI on this machine. Run, Forrest, Run is now the default there too.",
            "Same canonical store. Same trail. You don't install twice.",
        )
    return result
