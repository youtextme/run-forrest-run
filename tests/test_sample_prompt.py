"""TDD: sample prompt must open every session with Run Forrest Run."""

from __future__ import annotations

from pathlib import Path

import pytest

from runforrestrun import ICON, INVOKE
from runforrestrun.install import install_into_hosts
from runforrestrun.prompt_processor import (
    SAMPLE_PROMPT,
    assert_valid_session_opening,
    is_valid_session_opening,
    process_prompt,
    process_sample_prompt,
)
from runforrestrun.session_bootstrap import (
    FIRST_MESSAGE,
    FIRST_MESSAGE_LINE1,
    FIRST_MESSAGE_LINE2,
    PLATFORM_VARIANTS,
    verify_all_platforms,
)


def test_sample_prompt_constant():
    assert "List the files" in SAMPLE_PROMPT
    assert len(SAMPLE_PROMPT) > 20


def test_sample_prompt_opens_with_exact_first_message(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("RUN_FORREST_HOME", str(tmp_path / "rfr"))
    monkeypatch.setenv("RUN_FORREST_SKIP_SYNC", "1")
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    project = tmp_path / "proj"
    project.mkdir()
    packaged = Path(__file__).resolve().parents[1]

    install = install_into_hosts(project_root=project, packaged=packaged)
    assert install["ok"] is True, install.get("bootstrap", {}).get("errors")

    result = process_sample_prompt(project_root=project, packaged=packaged)
    assert result["processed_by"] == "run-forrest-run"
    assert result["run_id"]
    assert Path(result["job_dir"]).exists()
    assert result["first_message"] == FIRST_MESSAGE

    voice = result["voice"]
    lines = voice.splitlines()
    assert lines[0] == FIRST_MESSAGE_LINE1
    assert lines[1] == FIRST_MESSAGE_LINE2
    assert is_valid_session_opening(voice, require_exact=True)


def test_process_prompt_rejects_bad_opening():
    with pytest.raises(AssertionError):
        assert_valid_session_opening("hello\nworld")


def test_all_five_platform_variants_after_install(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("RUN_FORREST_HOME", str(tmp_path / "rfr"))
    monkeypatch.setenv("RUN_FORREST_SKIP_SYNC", "1")
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    project = tmp_path / "proj"
    project.mkdir()
    packaged = Path(__file__).resolve().parents[1]

    install = install_into_hosts(project_root=project, packaged=packaged)
    assert install["ok"] is True

    check = verify_all_platforms(project_root=project, home_root=home)
    assert check["ok"] is True, check["errors"]

    for name in PLATFORM_VARIANTS:
        assert check["platforms"][name]["ok"] is True, (
            f"{name}: {check['platforms'][name]['errors']}"
        )


def test_sample_prompt_through_process_prompt(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("RUN_FORREST_HOME", str(tmp_path / "rfr"))
    monkeypatch.setenv("RUN_FORREST_SKIP_SYNC", "1")

    project = tmp_path / "proj"
    project.mkdir()
    result = process_prompt(
        "Fix the typo in README",
        project_root=project,
        packaged=Path(__file__).resolve().parents[1],
    )
    assert INVOKE in result["voice"]
    assert result["voice"].splitlines()[0].startswith(ICON)
