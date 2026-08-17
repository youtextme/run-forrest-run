"""Model assessor — bar raiser is foundational to every objective."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from runforrestrun.__main__ import main
from runforrestrun.assessor import (
    FAST_BAR,
    _identity_from_raw,
    assess_model,
    cache_is_fresh,
    detect_model,
    load_cached_dossier,
    load_catalog,
    research_model,
    save_dossier,
    ttl_days,
)
from runforrestrun.prompt_processor import process_prompt
from runforrestrun.runner import run_objective
from runforrestrun.session_bootstrap import FIRST_MESSAGE_LINE1, FIRST_MESSAGE_LINE2


def _home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("RUN_FORREST_HOME", str(tmp_path / "rfr"))
    return home


def test_detect_model_from_env(tmp_path, monkeypatch):
    _home(tmp_path, monkeypatch)
    monkeypatch.setenv("RUN_FORREST_MODEL", "cursor-grok-4.6-high-fast")
    ident = detect_model()
    assert ident.slug == "cursor-grok-4.6-high-fast"
    assert ident.family == "grok-4.6"
    assert "fast" in ident.variant
    assert ident.source == "RUN_FORREST_MODEL"
    assert "xAI" in ident.vendor or "SpaceXAI" in ident.vendor


def test_detect_model_unknown_when_unset(tmp_path, monkeypatch):
    _home(tmp_path, monkeypatch)
    monkeypatch.delenv("RUN_FORREST_MODEL", raising=False)
    monkeypatch.delenv("CURSOR_MODEL", raising=False)
    monkeypatch.delenv("MODEL", raising=False)
    ident = detect_model()
    assert ident.family == "unknown"
    assert ident.source == "undetected"


def test_bare_model_env_ignored_when_not_a_name(tmp_path, monkeypatch):
    _home(tmp_path, monkeypatch)
    monkeypatch.delenv("RUN_FORREST_MODEL", raising=False)
    monkeypatch.setenv("MODEL", "auto")
    ident = detect_model()
    assert ident.family == "unknown"


def test_cache_ttl_is_few_days_to_few_weeks(monkeypatch):
    monkeypatch.delenv("RUN_FORREST_MODEL_CACHE_DAYS", raising=False)
    assert ttl_days() == 14
    monkeypatch.setenv("RUN_FORREST_MODEL_CACHE_DAYS", "2")
    assert ttl_days() == 3
    monkeypatch.setenv("RUN_FORREST_MODEL_CACHE_DAYS", "90")
    assert ttl_days() == 21
    assert cache_is_fresh(4, ttl=14) is True
    assert cache_is_fresh(10, ttl=14) is True
    assert cache_is_fresh(22, ttl=14) is False
    assert cache_is_fresh(None, ttl=14) is False


def test_fresh_cache_skips_fetch(tmp_path, monkeypatch):
    _home(tmp_path, monkeypatch)
    monkeypatch.setenv("RUN_FORREST_MODEL", "cursor-grok-4.6-high-fast")
    first = assess_model("fix the failing test")
    assert first.researched is True
    calls = {"n": 0}

    def boom(url: str, timeout: float = 12.0) -> str | None:
        calls["n"] += 1
        raise AssertionError("fetch must not run on a fresh cache")

    monkeypatch.delenv("RUN_FORREST_SKIP_MODEL_RESEARCH", raising=False)
    second = assess_model("fix the failing test", fetch=boom)
    assert second.cache_hit is True
    assert second.researched is False
    assert calls["n"] == 0
    assert second.cache_age_days is not None
    assert second.cache_age_days < 1


def test_stale_cache_re_researches(tmp_path, monkeypatch):
    _home(tmp_path, monkeypatch)
    monkeypatch.setenv("RUN_FORREST_MODEL", "grok-4.6")
    first = assess_model("research the API")
    stale_at = (datetime.now(timezone.utc) - timedelta(days=22)).isoformat()
    dossier = dict(first.dossier)
    dossier["assessed_at"] = stale_at
    save_dossier(first.identity.slug, dossier)
    cached, age = load_cached_dossier(first.identity.slug)
    assert cached is not None
    assert age is not None and age > 21
    assert cache_is_fresh(age) is False

    seen: list[str] = []

    def fake_fetch(url: str, timeout: float = 12.0) -> str | None:
        seen.append(url)
        return (
            "Grok 4.6 still hallucinates when uncertain. "
            "The January 2026 cutoff means live docs are required. "
            "Terminal-Bench remains a weakness versus Sol."
        )

    monkeypatch.setenv("RUN_FORREST_SKIP_MODEL_RESEARCH", "0")
    refreshed = assess_model("research the API", fetch=fake_fetch)
    assert refreshed.cache_hit is False
    assert refreshed.researched is True
    assert seen
    assert any("hallucin" in x.lower() for x in refreshed.dossier.get("live_findings") or [])


def test_injected_prompts_plug_gaps_without_switching_models(tmp_path, monkeypatch):
    _home(tmp_path, monkeypatch)
    monkeypatch.setenv("RUN_FORREST_MODEL", "cursor-grok-4.6-high-fast")
    assessment = assess_model("implement the CLI and fix the failing test")
    blob = "\n".join(assessment.injected).lower()
    assert "do not switch models" in blob or "same model" in blob
    assert "switch to gpt" not in blob
    assert "switch to claude" not in blob
    assert "bar" in blob
    assert any("cutoff" in p.lower() or "sample" in p.lower() for p in assessment.injected)
    assert any("research" in p.lower() for p in assessment.injected)
    assert assessment.bar["min_score"] == FAST_BAR
    assert assessment.bar["same_model_only"] is True
    assert assessment.research_plan
    assert "deepswe" in blob or "terminal" in blob or "swe" in blob


def test_unknown_model_still_gets_a_bar(tmp_path, monkeypatch):
    _home(tmp_path, monkeypatch)
    for key in ("RUN_FORREST_MODEL", "CURSOR_MODEL", "MODEL"):
        monkeypatch.delenv(key, raising=False)
    assessment = assess_model("look up the latest docs")
    assert assessment.identity.family == "unknown"
    assert assessment.bar["min_score"] >= 80
    assert any("cutoff" in p.lower() for p in assessment.injected)


def test_run_objective_writes_model_bar_injected(tmp_path, monkeypatch):
    _home(tmp_path, monkeypatch)
    monkeypatch.setenv("RUN_FORREST_MODEL", "cursor-grok-4.6-high-fast")
    project = tmp_path / "proj"
    project.mkdir()
    result = run_objective("write hello world", project_root=project)
    job = Path(result["job_dir"])
    assert (job / "model.json").exists()
    assert (job / "bar.md").exists()
    assert (job / "injected.md").exists()
    payload = json.loads((job / "model.json").read_text(encoding="utf-8"))
    assert payload["identity"]["family"] == "grok-4.6"
    assert "Bar:" in (job / "truth.md").read_text(encoding="utf-8")
    assert result["model"]
    assert result["bar"]["min_score"] == FAST_BAR
    assert result["injected"]
    lines = result["voice"].splitlines()
    assert lines[0] == FIRST_MESSAGE_LINE1
    assert lines[1] == FIRST_MESSAGE_LINE2
    assert any("Model at work" in ln for ln in lines)


def test_process_prompt_keeps_mandatory_opening(tmp_path, monkeypatch):
    _home(tmp_path, monkeypatch)
    monkeypatch.setenv("RUN_FORREST_MODEL", "claude-opus-5")
    project = tmp_path / "proj"
    project.mkdir()
    result = process_prompt(
        "Fix the typo in README",
        project_root=project,
        packaged=Path(__file__).resolve().parents[1],
    )
    lines = result["voice"].splitlines()
    assert lines[0] == FIRST_MESSAGE_LINE1
    assert lines[1] == FIRST_MESSAGE_LINE2
    assert result["assessor"]["identity"]["family"] == "claude-opus-5"


def test_cli_assess_model_json(tmp_path, monkeypatch, capsys):
    _home(tmp_path, monkeypatch)
    monkeypatch.setenv("RUN_FORREST_MODEL", "gpt-5.6-sol")
    rc = main(["--assess-model", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["identity"]["family"] == "gpt-5.6"
    assert payload["bar"]["min_score"] >= 80
    assert payload["injected"]


def test_seed_research_merges_fetch(tmp_path, monkeypatch):
    _home(tmp_path, monkeypatch)
    ident = _identity_from_raw("grok-4.6", source="test", catalog=load_catalog())

    def fake_fetch(url: str, timeout: float = 12.0) -> str | None:
        return (
            "Independent review: Grok 4.6 underperforms on Terminal-Bench. "
            "Hallucination remains a limitation when the model is uncertain."
        )

    monkeypatch.delenv("RUN_FORREST_SKIP_MODEL_RESEARCH", raising=False)
    dossier = research_model(ident, fetch=fake_fetch, objective="fix tests")
    assert dossier["origin"] == "research"
    assert dossier["same_model_only"] is True
    assert dossier["live_findings"]


def test_skill_documents_bar_raiser():
    skill = Path(__file__).resolve().parents[1] / "SKILL.md"
    text = skill.read_text(encoding="utf-8")
    assert "bar raiser" in text.lower()
    assert "few days" in text.lower()
    assert "same model" in text.lower()
    assert "injected.md" in text
