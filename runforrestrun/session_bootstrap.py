"""Session bootstrap contract — every platform variant starts with Run Forrest Run."""

from __future__ import annotations

import re
from pathlib import Path

from runforrestrun import ICON, INVOKE

# Exact first message every session must emit (before any other content).
FIRST_MESSAGE_LINE1 = f"{ICON} {INVOKE}"
FIRST_MESSAGE_LINE2 = (
    f"{ICON} I don't have a warrant on this yet. I'll probe it. "
    "Type anything to course-correct — the trail keeps everything."
)
FIRST_MESSAGE = FIRST_MESSAGE_LINE1 + "\n" + FIRST_MESSAGE_LINE2

LEGACY_RUNNER_NAMES = frozenset(
    {
        "figureitout",
        "runforest",
        "true-that",
        "letscook",
        "objective-runner",
    }
)

LEGACY_RULE_FILES = frozenset({"figureitout.mdc"})

# Five platform variants — all must carry the mandatory first message.
PLATFORM_VARIANTS: dict[str, tuple[str, ...]] = {
    "cursor_local": (
        ".cursor/skills/run-forrest-run/SKILL.md",
        ".cursor/rules/run-forrest-run.mdc",
    ),
    "cursor_cloud": (
        "AGENTS.md",
        ".cursor/rules/run-forrest-run.mdc",
        ".cursor/skills/run-forrest-run/SKILL.md",
    ),
    "devin_local": (
        ".config/devin/AGENTS.md",
        ".devin/global_rules.md",
        ".devin/rules/run-forrest-run.md",
    ),
    "devin_cloud": (
        "AGENTS.md",
        ".devin/global_rules.md",
        ".devin/rules/run-forrest-run.md",
        ".devin/skills/run-forrest-run/SKILL.md",
    ),
    "openclaw": (
        "AGENTS.md",
        ".agents/skills/run-forrest-run/SKILL.md",
        ".openclaw/workspace/AGENTS.md",
    ),
}


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _has_first_message(text: str) -> bool:
    return INVOKE in text and "warrant" in text.lower() and ICON in text


def _check_paths(base: Path, rels: tuple[str, ...], label: str) -> list[str]:
    errors: list[str] = []
    for rel in rels:
        p = base / rel
        if not p.exists():
            errors.append(f"{label}: missing {rel}")
            continue
        body = _read(p)
        if not _has_first_message(body):
            errors.append(f"{label}: {rel} missing mandatory first message")
        if rel.endswith("SKILL.md") and "alwaysApply: true" not in body:
            errors.append(f"{label}: {rel} missing alwaysApply: true")
        if rel.endswith("run-forrest-run.mdc") and "alwaysApply: true" not in body:
            errors.append(f"{label}: {rel} missing alwaysApply: true")
        if rel.endswith("run-forrest-run.md") and "trigger: always_on" not in body:
            errors.append(f"{label}: {rel} missing trigger: always_on")
    return errors


def _legacy_absent(root: Path) -> list[str]:
    errors: list[str] = []
    for base in (
        root / ".cursor" / "skills",
        root / ".devin" / "skills",
        root / ".agents" / "skills",
        root / ".claude" / "skills",
    ):
        if not base.exists():
            continue
        for child in base.iterdir():
            if child.is_dir() and child.name in LEGACY_RUNNER_NAMES:
                errors.append(f"legacy runner still present: {child}")
    for rules in (root / ".cursor" / "rules",):
        if not rules.exists():
            continue
        for name in LEGACY_RULE_FILES:
            if (rules / name).exists():
                errors.append(f"legacy rule still present: {rules / name}")
    if re.search(r"## figureitout\b", _read(root / "AGENTS.md"), re.I):
        errors.append("AGENTS.md still references figureitout")
    return errors


def verify_all_platforms(
    project_root: Path | str | None = None,
    home_root: Path | str | None = None,
) -> dict:
    """Verify cursor local/cloud, devin local/cloud, openclaw bootstrap."""
    root = Path(project_root or Path.cwd()).resolve()
    home = Path(home_root or Path.home()).resolve()
    platforms: dict[str, dict] = {}
    all_errors: list[str] = []

    checks = {
        "cursor_local": _check_paths(root, PLATFORM_VARIANTS["cursor_local"], "cursor_local")
        + _check_paths(home, (".cursor/skills/run-forrest-run/SKILL.md",), "cursor_local_home"),
        "cursor_cloud": _check_paths(root, PLATFORM_VARIANTS["cursor_cloud"], "cursor_cloud"),
        "devin_local": _check_paths(home, PLATFORM_VARIANTS["devin_local"], "devin_local"),
        "devin_cloud": _check_paths(root, PLATFORM_VARIANTS["devin_cloud"], "devin_cloud"),
        "openclaw": _check_paths(root, PLATFORM_VARIANTS["openclaw"][:2], "openclaw")
        + _check_paths(home, (".openclaw/workspace/AGENTS.md",), "openclaw_home"),
    }

    for name, errs in checks.items():
        platforms[name] = {"ok": not errs, "errors": errs}
        all_errors.extend(errs)

    legacy_err = _legacy_absent(root)
    all_errors.extend(legacy_err)

    return {
        "ok": not all_errors,
        "first_message": FIRST_MESSAGE,
        "platforms": platforms,
        "legacy_clean": not legacy_err,
        "errors": all_errors,
    }


def verify_session_bootstrap(project_root: Path | str | None = None) -> dict:
    """Backward-compatible wrapper."""
    result = verify_all_platforms(project_root=project_root)
    return {
        "ok": result["ok"],
        "first_message": result["first_message"],
        "hosts": {
            "cursor": result["platforms"].get("cursor_local", {}),
            "devin": result["platforms"].get("devin_cloud", {}),
            "openclaw": result["platforms"].get("openclaw", {}),
        },
        "platforms": result["platforms"],
        "legacy_clean": result["legacy_clean"],
        "errors": result["errors"],
    }
