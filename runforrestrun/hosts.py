"""Find IDEs and CLIs on this computer. New ones get the same canonical default."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Host:
    id: str
    title: str
    kind: str  # ide | cli | agent
    markers: tuple[str, ...] = ()
    binaries: tuple[str, ...] = ()
    env_flags: tuple[str, ...] = ()


# Presence, not preference. If the host exists, we default it.
CATALOG: tuple[Host, ...] = (
    Host("cursor", "Cursor", "ide", markers=(".cursor",), binaries=("cursor", "cursor-agent")),
    Host("vscode", "VS Code", "ide", markers=(".vscode",), binaries=("code", "code-insiders")),
    Host("windsurf", "Windsurf", "ide", binaries=("windsurf",)),
    Host("zed", "Zed", "ide", binaries=("zed", "zeditor")),
    Host("claude", "Claude Code", "ide", markers=(".claude",), binaries=("claude",)),
    Host("devin", "Devin", "agent", markers=(".devin",), binaries=("devin",)),
    Host("openclaw", "OpenClaw", "agent", binaries=("openclaw",)),
    Host("codex", "Codex", "cli", binaries=("codex",)),
    Host("aider", "Aider", "cli", binaries=("aider",)),
    Host("goose", "Goose", "cli", binaries=("goose",)),
    Host("gemini", "Gemini CLI", "cli", binaries=("gemini",)),
    Host("amp", "Amp", "cli", binaries=("amp",)),
    Host("continue", "Continue", "ide", binaries=()),
    Host("copilot", "GitHub Copilot", "ide", binaries=()),
    Host("agents-spec", "Agent Skills", "agent"),
    Host("cli-python", "Python CLI", "cli", binaries=("python3", "python")),
)


def _home() -> Path:
    return Path.home()


def _exists(path: Path) -> bool:
    try:
        return path.exists()
    except OSError:
        return False


CORE_DEFAULT_HOSTS = frozenset({"cursor", "devin", "openclaw"})


def detect(project_root: Path | None = None, *, include_core_defaults: bool = True) -> list[Host]:
    """Hosts on this machine. Core agents (Cursor, Devin, OpenClaw) always default."""
    root = (project_root or Path.cwd()).resolve()
    home = _home()
    found: list[Host] = []
    seen: set[str] = set()

    extra_markers = {
        "cursor": [home / ".cursor", root / ".cursor", home / ".config" / "Cursor"],
        "vscode": [home / ".vscode", root / ".vscode", home / "Library" / "Application Support" / "Code"],
        "windsurf": [
            home / ".codeium" / "windsurf",
            home / ".windsurf",
            home / "Library" / "Application Support" / "Windsurf",
        ],
        "zed": [home / ".config" / "zed", home / "Library" / "Application Support" / "Zed"],
        "claude": [home / ".claude", root / ".claude"],
        "devin": [
            home / ".devin",
            root / ".devin",
            home / ".config" / "devin",
            home / "Library" / "Application Support" / "devin",
        ],
        "openclaw": [
            home / ".openclaw",
            root / ".agents",
            home / ".agents",
            Path(os.environ.get("OPENCLAW_HOME") or ""),
        ],
        "aider": [home / ".aider", root / ".aider.conf.yml", root / "CONVENTIONS.md"],
        "goose": [home / ".config" / "goose", home / ".goose"],
        "continue": [home / ".continue", root / ".continue"],
        "copilot": [root / ".github" / "copilot-instructions.md"],
        "agents-spec": [home / ".agents", root / ".agents"],
        "codex": [root / "AGENTS.md"],
        "gemini": [home / ".gemini"],
    }

    for host in CATALOG:
        hit = False
        if any(os.environ.get(flag) for flag in host.env_flags):
            hit = True
        for binary in host.binaries:
            if shutil.which(binary):
                hit = True
                break
        for marker in extra_markers.get(host.id, []):
            if marker and _exists(Path(marker)):
                hit = True
                break
        for rel in host.markers:
            if _exists(root / rel) or _exists(home / rel):
                hit = True
        # Python is always a possible CLI if we are installing a Python package.
        if host.id == "cli-python":
            hit = True
        if host.id == "agents-spec":
            hit = True  # portable default; cheap to write
        if hit and host.id not in seen:
            seen.add(host.id)
            found.append(host)

    if include_core_defaults:
        for host in CATALOG:
            if host.id in CORE_DEFAULT_HOSTS and host.id not in seen:
                seen.add(host.id)
                found.append(host)
    return found


def skill_destinations(host: Host, project_root: Path) -> list[Path]:
    """Where this host reads SKILL.md / instructions. Canonical is copied here."""
    home = _home()
    root = project_root.resolve()
    name = "run-forrest-run"
    dests: list[Path] = []
    if host.id == "cursor":
        dests += [
            root / ".cursor" / "skills" / name,
            home / ".cursor" / "skills" / name,
        ]
    elif host.id == "claude":
        dests += [
            root / ".claude" / "skills" / name,
            home / ".claude" / "skills" / name,
        ]
    elif host.id == "devin":
        dests += [
            root / ".devin" / "skills" / name,
            home / ".devin" / "skills" / name,
            home / ".config" / "devin" / "skills" / name,
        ]
    elif host.id == "openclaw":
        openclaw = Path(os.environ.get("OPENCLAW_HOME") or (home / ".openclaw"))
        dests += [
            root / ".agents" / "skills" / name,
            home / ".agents" / "skills" / name,
            openclaw / "workspace" / "skills" / name,
            openclaw / "skills" / name,
        ]
    elif host.id == "vscode":
        dests += []  # copilot-instructions.md via extra_instruction_files
    elif host.id == "continue":
        dests += [home / ".continue" / "skills" / name]
    elif host.id in {"aider", "goose", "codex", "gemini", "amp"}:
        dests += []  # AGENTS.md / CONVENTIONS only — never overwrite repo SKILL.md
    elif host.id == "agents-spec":
        dests += [
            root / ".agents" / "skills" / name,
            home / ".agents" / "skills" / name,
        ]
    elif host.id == "cli-python":
        dests += [canonical_from_home()]
    else:
        dests += [
            root / ".agents" / "skills" / name,
            home / ".agents" / "skills" / name,
        ]
    # unique
    out: list[Path] = []
    seen: set[str] = set()
    for path in dests:
        key = str(path)
        if key not in seen:
            seen.add(key)
            out.append(path)
    return out


def canonical_from_home() -> Path:
    from runforrestrun.paths import canonical_dir

    return canonical_dir()


def extra_instruction_files(host: Host, project_root: Path) -> dict[str, str]:
    """Side files some hosts read instead of SKILL.md."""
    root = project_root.resolve()
    home = _home()
    files: dict[str, str] = {}
    if host.id in {"codex", "aider", "goose", "amp", "gemini", "cli-python", "agents-spec", "devin", "openclaw"}:
        files[str(root / "AGENTS.md")] = "agents"
    if host.id == "devin":
        files[str(root / ".devin" / "global_rules.md")] = "devin_global"
        files[str(root / ".devin" / "rules" / "run-forrest-run.md")] = "devin_rule"
        files[str(home / ".devin" / "global_rules.md")] = "devin_global"
        files[str(home / ".devin" / "rules" / "run-forrest-run.md")] = "devin_rule"
        files[str(home / ".config" / "devin" / "AGENTS.md")] = "agents"
    if host.id == "cursor":
        files[str(root / ".cursor" / "rules" / "run-forrest-run.mdc")] = "rule"
        files[str(home / ".cursor" / "rules" / "run-forrest-run.mdc")] = "rule"
        files[str(home / ".cursor" / "skills" / "run-forrest-run" / "SKILL.md")] = "cursor_home_skill"
    if host.id == "vscode" or host.id == "copilot":
        files[str(root / ".github" / "copilot-instructions.md")] = "copilot"
    if host.id == "aider":
        files[str(root / "CONVENTIONS.md")] = "aider"
    if host.id == "openclaw":
        openclaw = Path(os.environ.get("OPENCLAW_HOME") or (home / ".openclaw"))
        files[str(openclaw / "workspace" / "AGENTS.md")] = "agents"
        files[str(openclaw / "AGENTS.md")] = "agents"
    return files
