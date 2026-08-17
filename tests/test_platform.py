"""Run, Forrest, Run! — platform tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from runforrestrun.autonomy import check_autonomy
from runforrestrun.hosts import detect
from runforrestrun.install import install_into_hosts, watch_once
from runforrestrun.observer import record_observation
from runforrestrun.platform import maybe_propose
from runforrestrun.runner import run_objective
from runforrestrun.trail import abstract_text, record_steer, start_trail
from runforrestrun.voice import opening, two_lines


def test_voice_is_exactly_two_forest_lines():
    text = two_lines("hello", "world")
    lines = text.splitlines()
    assert len(lines) == 2
    assert lines[0].startswith("🌲")
    assert lines[1].startswith("🌲")


def test_opening_uses_movie_spelling_forrest():
    text = opening(noun="the login bug", run_id="abc123", autonomous=True)
    assert "Run, Forrest, Run!" in text
    assert "invoked" in text.lower()
    assert "warrant" in text.lower()
    assert "Forest," not in text.replace("Forrest", "")


def test_opening_blocked_names_the_need():
    text = opening(noun="x", run_id="r1", autonomous=False, need="python3 on PATH")
    assert "cannot run" in text.lower()
    assert "python3" in text


def test_abstract_strips_identity():
    raw = "Ask ada@example.com under /Users/ada/secret and ticket AB-1234"
    out = abstract_text(raw)
    assert "ada@example.com" not in out
    assert "/Users/ada" not in out
    assert "<email>" in out
    assert "<home>" in out


def test_trail_and_steer(tmp_path, monkeypatch):
    monkeypatch.setenv("RUN_FORREST_HOME", str(tmp_path / "rfr"))
    started = start_trail("prove the file exists")
    rid = started["run_id"]
    job = Path(started["job_dir"])
    assert (job / "lock.md").exists()
    assert (job / "checkpoint.json").exists()
    record_steer(rid, "use purple not pink")
    assert "purple" in (job / "steer.jsonl").read_text(encoding="utf-8")


def test_install_writes_canonical_and_agent_skills(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("RUN_FORREST_HOME", str(tmp_path / "rfr"))
    monkeypatch.setenv("RUN_FORREST_SKIP_SYNC", "1")
    project = tmp_path / "proj"
    project.mkdir()
    result = install_into_hosts(project_root=project, packaged=Path(__file__).resolve().parents[1])
    assert result["ok"] is True
    canonical = Path(result["canonical"])
    assert (canonical / "SKILL.md").exists()
    assert "alwaysApply: true" in (canonical / "SKILL.md").read_text(encoding="utf-8")
    skill = project / ".agents" / "skills" / "run-forrest-run" / "SKILL.md"
    assert skill.exists()
    assert "Run, Forrest, Run!" in skill.read_text(encoding="utf-8")
    agents = (project / "AGENTS.md").read_text(encoding="utf-8")
    assert "Run, Forrest, Run!" in agents


def test_watch_reports_new_hosts(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("RUN_FORREST_HOME", str(tmp_path / "rfr"))
    project = tmp_path / "proj"
    project.mkdir()
    first = install_into_hosts(project_root=project)
    assert first["ok"]
    (project / ".claude").mkdir()
    second = watch_once(project_root=project)
    assert "claude" in second.get("new_hosts") or "claude" in second.get("hosts")


def test_run_objective_two_line_voice(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("RUN_FORREST_HOME", str(tmp_path / "rfr"))
    project = tmp_path / "proj"
    project.mkdir()
    result = run_objective("write hello world", project_root=project)
    voice_lines = [ln for ln in result["voice"].splitlines() if ln.startswith("🌲")]
    assert len(voice_lines) >= 2
    assert "Run, Forrest, Run!" in result["voice"]
    assert result["run_id"]
    assert Path(result["job_dir"]).exists()


def test_observer_has_no_user_field_identity(tmp_path, monkeypatch):
    monkeypatch.setenv("RUN_FORREST_HOME", str(tmp_path / "rfr"))
    path = record_observation(
        kind="run",
        note="Ask bob@corp.com in /Users/bob/src",
        example="bob@corp.com",
        foundational_need="cheap-ping-not-literature",
        run_id="r1",
    )
    text = path.read_text(encoding="utf-8")
    assert "bob@corp.com" not in text
    assert "<email>" in text


def test_capability_proposal_is_rare(tmp_path, monkeypatch):
    monkeypatch.setenv("RUN_FORREST_HOME", str(tmp_path / "rfr"))
    first = maybe_propose("use a cheap ping not literature review", run_id="r1")
    assert first is not None
    assert first["consent_needed"] is True
    second = maybe_propose("use a cheap ping not literature review", run_id="r2")
    assert second is None


def test_lockdown_blocks_autonomy(monkeypatch):
    monkeypatch.setenv("RUN_FORREST_LOCKDOWN", "1")
    auto = check_autonomy("anything")
    assert auto.ok is False
    assert "lockdown" in auto.need.lower()


def test_detect_includes_core_agents(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    from runforrestrun.hosts import detect

    hosts = detect(tmp_path / "proj", include_core_defaults=True)
    ids = {h.id for h in hosts}
    assert "cursor" in ids
    assert "devin" in ids
    assert "openclaw" in ids

