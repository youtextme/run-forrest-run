"""Canonical home — one store every IDE and CLI shares."""

from __future__ import annotations

import os
from pathlib import Path


def home() -> Path:
    override = os.environ.get("RUN_FORREST_HOME", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / ".run-forrest-run"


def canonical_dir() -> Path:
    return home() / "canonical"


def runs_dir() -> Path:
    override = os.environ.get("RUN_FORREST_RUNS", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return home() / "runs"


def observations_dir() -> Path:
    return home() / "observations"


def platform_dir() -> Path:
    return home() / "platform"


def patterns_dir() -> Path:
    """Stored patterns — subsequent runs cheap-ping these instead of rediscovering."""
    return home() / "patterns"


def skills_dir() -> Path:
    """Cached subskills minted from proven access (Slack, MCP, …)."""
    return home() / "skills"


def model_aware_dir() -> Path:
    """Model gaps, MCP inventory, capability catalog."""
    return home() / "model-aware"


def hosts_state_path() -> Path:
    return home() / "hosts.json"


def lockdown() -> bool:
    return os.environ.get("RUN_FORREST_LOCKDOWN", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def ensure_layout() -> Path:
    for path in (
        home(),
        canonical_dir(),
        runs_dir(),
        observations_dir(),
        platform_dir() / "proposals",
        patterns_dir(),
        skills_dir(),
        model_aware_dir(),
        home() / "preferences",
    ):
        path.mkdir(parents=True, exist_ok=True)
    return home()
