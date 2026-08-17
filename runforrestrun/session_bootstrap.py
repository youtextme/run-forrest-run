"""Session bootstrap contract — every Cursor, Devin, OpenClaw prompt starts with Run Forrest Run."""

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

CURSOR_PATHS = (
    ".cursor/skills/run-forrest-run/SKILL.md",
    ".cursor/rules/run-forrest-run.mdc",
)

DEVIN_PATHS = (
    ".devin/global_rules.md",
    ".devin/rules/run-forrest-run.md",
    ".devin/skills/run-forrest-run/SKILL.md",
    ".agents/skills/run-forrest-run/SKILL.md",
)

OPENCLAW_PATHS = (
    "AGENTS.md",
    ".agents/skills/run-forrest-run/SKILL.md",
)


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _has_first_message(text: str) -> bool:
    return INVOKE in text and "warrant" in text.lower() and ICON in text


def _cursor_ok(root: Path) -> list[str]:
    errors: list[str] = []
    skill = root / CURSOR_PATHS[0]
    rule = root / CURSOR_PATHS[1]
    if not skill.exists():
        errors.append(f"missing {CURSOR_PATHS[0]}")
    else:
        body = _read(skill)
        if "alwaysApply: true" not in body:
            errors.append("cursor skill missing alwaysApply: true")
        if not _has_first_message(body):
            errors.append("cursor skill missing mandatory first message")
    if not rule.exists():
        errors.append(f"missing {CURSOR_PATHS[1]}")
    else:
        body = _read(rule)
        if "alwaysApply: true" not in body:
            errors.append("cursor rule missing alwaysApply: true")
        if not _has_first_message(body):
            errors.append("cursor rule missing mandatory first message")
    return errors


def _devin_ok(root: Path) -> list[str]:
    errors: list[str] = []
    for rel in DEVIN_PATHS:
        if not (root / rel).exists():
            errors.append(f"missing {rel}")
    global_rules = _read(root / ".devin/global_rules.md")
    if global_rules and not _has_first_message(global_rules):
        errors.append("devin global_rules missing mandatory first message")
    devin_rule = _read(root / ".devin/rules/run-forrest-run.md")
    if devin_rule:
        if "trigger: always_on" not in devin_rule.replace(" ", ""):
            if "trigger: always_on" not in devin_rule:
                errors.append("devin rule missing trigger: always_on")
        if not _has_first_message(devin_rule):
            errors.append("devin rule missing mandatory first message")
    agents = _read(root / "AGENTS.md")
    if "Run, Forrest, Run! (NON-NEGOTIABLE)" not in agents:
        errors.append("AGENTS.md missing Run Forrest Run NON-NEGOTIABLE block")
    if not _has_first_message(agents):
        errors.append("AGENTS.md missing mandatory first message")
    return errors


def _openclaw_ok(root: Path) -> list[str]:
    errors: list[str] = []
    for rel in OPENCLAW_PATHS:
        if not (root / rel).exists():
            errors.append(f"missing {rel}")
    agents = _read(root / "AGENTS.md")
    if "Run, Forrest, Run! (NON-NEGOTIABLE)" not in agents:
        errors.append("openclaw: AGENTS.md missing NON-NEGOTIABLE block")
    skill = _read(root / ".agents/skills/run-forrest-run/SKILL.md")
    if skill and not _has_first_message(skill):
        errors.append("openclaw skill missing mandatory first message")
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


def verify_session_bootstrap(project_root: Path | str | None = None) -> dict:
    """Return {ok, hosts: {cursor, devin, openclaw}, errors, first_message}."""
    root = Path(project_root or Path.cwd()).resolve()
    cursor_err = _cursor_ok(root)
    devin_err = _devin_ok(root)
    openclaw_err = _openclaw_ok(root)
    legacy_err = _legacy_absent(root)
    all_errors = legacy_err + cursor_err + devin_err + openclaw_err
    return {
        "ok": not all_errors,
        "first_message": FIRST_MESSAGE,
        "hosts": {
            "cursor": {"ok": not cursor_err, "errors": cursor_err},
            "devin": {"ok": not devin_err, "errors": devin_err},
            "openclaw": {"ok": not openclaw_err, "errors": openclaw_err},
        },
        "legacy_clean": not legacy_err,
        "errors": all_errors,
    }
