"""TDD: every Cursor, Devin, OpenClaw session must bootstrap with Run Forrest Run."""

from __future__ import annotations

from pathlib import Path

import pytest

from runforrestrun import ICON, INVOKE
from runforrestrun.install import install_into_hosts, remove_legacy_runners
from runforrestrun.session_bootstrap import (
    FIRST_MESSAGE,
    FIRST_MESSAGE_LINE1,
    FIRST_MESSAGE_LINE2,
    LEGACY_RUNNER_NAMES,
    verify_session_bootstrap,
)


def test_first_message_is_exactly_two_forest_lines():
    lines = FIRST_MESSAGE.splitlines()
    assert len(lines) == 2
    assert lines[0] == FIRST_MESSAGE_LINE1
    assert lines[1] == FIRST_MESSAGE_LINE2
    assert "Run, Forrest, Run!" in lines[0]
    assert "Forest," not in lines[0].replace("Forrest", "")
    assert lines[0].startswith(ICON)
    assert lines[1].startswith(ICON)


def test_verify_fails_before_install(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    result = verify_session_bootstrap(project)
    assert result["ok"] is False
    assert result["hosts"]["cursor"]["ok"] is False
    assert result["hosts"]["devin"]["ok"] is False
    assert result["hosts"]["openclaw"]["ok"] is False


def test_install_then_all_hosts_bootstrap(tmp_path, monkeypatch):
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

    # Seed legacy runners — install must remove them
    legacy = project / ".cursor" / "skills" / "figureitout" / "SKILL.md"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("---\nname: figureitout\nalwaysApply: true\n---\n", encoding="utf-8")
    (project / ".cursor" / "rules").mkdir(parents=True)
    (project / ".cursor" / "rules" / "figureitout.mdc").write_text(
        "---\nalwaysApply: true\n---\nfigureitout\n", encoding="utf-8"
    )
    (project / "AGENTS.md").write_text("## figureitout\nold\n", encoding="utf-8")

    install = install_into_hosts(project_root=project, packaged=packaged)
    assert install["ok"] is True
    assert "cursor" in install["hosts"]
    assert "devin" in install["hosts"]
    assert "openclaw" in install["hosts"]

    check = verify_session_bootstrap(project)
    assert check["ok"] is True, check["errors"]
    assert check["legacy_clean"] is True
    for name in ("cursor_local", "cursor_cloud", "devin_local", "devin_cloud", "openclaw"):
        assert check["platforms"][name]["ok"] is True, check["platforms"][name]["errors"]

    skill = (project / ".cursor/skills/run-forrest-run/SKILL.md").read_text(encoding="utf-8")
    assert "alwaysApply: true" in skill
    assert INVOKE in skill

    devin_rule = (project / ".devin/rules/run-forrest-run.md").read_text(encoding="utf-8")
    assert "trigger: always_on" in devin_rule

    agents = (project / "AGENTS.md").read_text(encoding="utf-8")
    assert agents.index("Run, Forrest, Run!") < agents.index("NON-NEGOTIABLE")
    assert "figureitout" not in agents.lower()

    for name in LEGACY_RUNNER_NAMES:
        assert not (project / ".cursor" / "skills" / name).exists()


def test_remove_legacy_runners_deletes_dirs(tmp_path):
    root = tmp_path / "proj"
    for name in ("figureitout", "letscook"):
        p = root / ".cursor" / "skills" / name
        p.mkdir(parents=True)
        (p / "SKILL.md").write_text("x", encoding="utf-8")
    removed = remove_legacy_runners(project_root=root)
    assert removed
    assert not (root / ".cursor" / "skills" / "figureitout").exists()
