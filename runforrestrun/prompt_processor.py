"""Process every prompt through Run Forrest Run — session must open with two 🌲 lines."""

from __future__ import annotations

from pathlib import Path

from runforrestrun import ICON, INVOKE
from runforrestrun.runner import run_objective
from runforrestrun.session_bootstrap import FIRST_MESSAGE, FIRST_MESSAGE_LINE1, FIRST_MESSAGE_LINE2

# Canonical sample prompt for TDD — proves objective-runner wiring end-to-end.
SAMPLE_PROMPT = "List the files in this repository and summarize what each directory does."


def assert_valid_session_opening(voice: str, *, require_exact: bool = True) -> None:
    """Raise AssertionError if voice does not start with mandatory Run Forrest Run opening."""
    lines = [ln for ln in voice.splitlines() if ln.strip()]
    if len(lines) < 2:
        raise AssertionError(f"expected at least 2 lines, got {len(lines)}")
    if not lines[0].startswith(ICON):
        raise AssertionError(f"line 1 must start with {ICON!r}, got {lines[0]!r}")
    if not lines[1].startswith(ICON):
        raise AssertionError(f"line 2 must start with {ICON!r}, got {lines[1]!r}")
    if INVOKE not in lines[0]:
        raise AssertionError(f"line 1 must contain invoke, got {lines[0]!r}")
    if "warrant" not in lines[1].lower():
        raise AssertionError(f"line 2 must mention warrant/probe, got {lines[1]!r}")
    if require_exact:
        if lines[0].strip() != FIRST_MESSAGE_LINE1.strip():
            raise AssertionError(f"line 1 must be exact first message, got {lines[0]!r}")
        if lines[1].strip() != FIRST_MESSAGE_LINE2.strip():
            raise AssertionError(f"line 2 must be exact first message, got {lines[1]!r}")


def is_valid_session_opening(voice: str, *, require_exact: bool = True) -> bool:
    try:
        assert_valid_session_opening(voice, require_exact=require_exact)
        return True
    except AssertionError:
        return False


def process_prompt(
    objective: str,
    *,
    project_root: Path | None = None,
    packaged: Path | None = None,
) -> dict:
    """Run objective through run-forrest-run. Opening voice is validated before return."""
    result = run_objective(objective, project_root=project_root, packaged=packaged)
    voice = result.get("voice") or ""
    assert_valid_session_opening(voice, require_exact=result.get("autonomy", True))
    result["first_message"] = FIRST_MESSAGE
    result["processed_by"] = "run-forrest-run"
    return result


def process_sample_prompt(
    *,
    project_root: Path | None = None,
    packaged: Path | None = None,
) -> dict:
    """TDD harness: sample prompt must produce valid session opening."""
    return process_prompt(SAMPLE_PROMPT, project_root=project_root, packaged=packaged)
