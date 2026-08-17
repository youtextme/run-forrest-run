"""Recruitment, MECE stories, subvisions, synthesis, and plan revision."""

from __future__ import annotations

from pathlib import Path

from runforrestrun.initiative import (
    add_user_stories,
    apply_steer,
    complete_story,
    open_initiative,
)
from runforrestrun.recruitment import GENERALIST_ID, recruit
from runforrestrun.runner import run_objective
from runforrestrun.signature import mece_cuts
from runforrestrun.stories import parse_added_stories, stories_for_first_slice
from runforrestrun.trail import start_trail


def test_science_function_is_not_a_job_title_table():
    rust = recruit("repair the rustc borrow checker diagnostic")
    css = recruit("repair the css flexbox overflow")
    assert rust.lead.recruit_id != GENERALIST_ID
    assert css.lead.recruit_id != GENERALIST_ID
    assert rust.lead.recruit_id != css.lead.recruit_id
    assert "rustc" in rust.lead.skill_set
    assert "css" in css.lead.skill_set
    assert rust.lead.likelihood_ratio > rust.recruiter.likelihood_ratio
    assert css.lead.likelihood_ratio > css.recruiter.likelihood_ratio


def test_generalist_recruits_and_never_authors():
    rec = recruit("fix the failing pytest for github credentials")
    assert rec.recruiter.recruit_id == GENERALIST_ID
    assert rec.recruiter.eligible_solver is False
    assert rec.lead.role == "specialist"
    assert rec.lead.eligible_solver is True
    bundle = stories_for_first_slice(rec)
    assert bundle["authored_by"] == rec.lead.recruit_id
    assert bundle["authored_by"] != GENERALIST_ID
    for story in bundle["stories"]:
        assert story["authored_by"] != GENERALIST_ID
        assert story["assigned_to"] != GENERALIST_ID
        assert story["assigned_to"]
        assert story["question"]


def test_first_slice_only_then_mece_stories(tmp_path, monkeypatch):
    monkeypatch.setenv("RUN_FORREST_HOME", str(tmp_path / "rfr"))
    objective = "fix the failing pytest and document the CLI and publish the skill"
    cuts = mece_cuts(objective)
    assert len(cuts) >= 3
    trail = start_trail(objective)
    opened = open_initiative(trail["run_id"], objective)
    hypo = opened["hypothesis"]
    assert hypo[0]["status"] == "active"
    assert hypo[0]["title"] == cuts[0]
    assert all(h["status"] == "hypothesized" for h in hypo[1:])
    bundle = opened["stories"]
    assert bundle["slice"] == cuts[0]
    assert bundle["mece"]["ok"] is True
    assert bundle["mece"]["mutually_exclusive"] is True
    assert bundle["mece"]["collectively_exhaustive"] is True
    assert len(bundle["stories"]) >= 3
    partitions = [tuple(s["partition"]) for s in bundle["stories"]]
    assert len(partitions) == len(set(partitions))


def test_human_can_add_seven_stories(tmp_path, monkeypatch):
    monkeypatch.setenv("RUN_FORREST_HOME", str(tmp_path / "rfr"))
    trail = start_trail("fix the login cookie")
    open_initiative(trail["run_id"], "fix the login cookie")
    msg = (
        "add these 7 more stories: "
        "trace the cookie jar; pin the expiry; cover http only; "
        "cover secure flag; cover same site; add a regression fixture; "
        "prove the redirect"
    )
    titles = parse_added_stories(msg)
    assert len(titles) == 7
    result = add_user_stories(trail["run_id"], msg)
    stories = result["stories"]["stories"]
    assert len(stories) >= 8
    assert result["stories"]["mece"]["mutually_exclusive"] is True
    human = [s for s in stories if s["source"] == "human"]
    assert len(human) == 7
    for story in stories:
        assert story["assigned_to"] != GENERALIST_ID


def test_subvisions_are_exclusive_payloads(tmp_path, monkeypatch):
    monkeypatch.setenv("RUN_FORREST_HOME", str(tmp_path / "rfr"))
    trail = start_trail("write hello world")
    opened = open_initiative(trail["run_id"], "write hello world")
    job = Path(opened["job_dir"])
    assert (job / "recruit.json").exists()
    assert (job / "stories.json").exists()
    assert (job / "who.md").exists()
    ids = [s["id"] for s in opened["stories"]["stories"]]
    for sid in ids:
        payload = (job / "subvisions" / sid / "payload.json").read_text(encoding="utf-8")
        brief = (job / "subvisions" / sid / "brief.md").read_text(encoding="utf-8")
        assert sid in payload
        assert "do_not_pull" in payload
        for other in ids:
            if other == sid:
                continue
            assert f"subvisions/{other}/" in payload
        assert "mutually exclusive" in brief.lower()


def test_complete_first_slice_revises_hypothesis(tmp_path, monkeypatch):
    monkeypatch.setenv("RUN_FORREST_HOME", str(tmp_path / "rfr"))
    objective = "fix the failing pytest and document the CLI"
    trail = start_trail(objective)
    opened = open_initiative(trail["run_id"], objective)
    rid = trail["run_id"]
    assert len(opened["hypothesis"]) >= 2
    for story in list(opened["stories"]["stories"]):
        complete_story(rid, story["id"], evidence=f"{story['id']} contacted the world")
    job = Path(opened["job_dir"])
    import json

    hypo = json.loads((job / "hypothesis.json").read_text(encoding="utf-8"))["hypothesis"]
    assert hypo[0]["status"] == "done"
    assert any(h["status"] == "active" for h in hypo[1:])
    assert (job / "revisions.jsonl").exists()
    plan = (job / "plan.md").read_text(encoding="utf-8")
    assert "living hypothesis" in plan.lower()


def test_steer_can_rethink_the_whole_plan(tmp_path, monkeypatch):
    monkeypatch.setenv("RUN_FORREST_HOME", str(tmp_path / "rfr"))
    objective = "fix the failing pytest and document the CLI and publish the skill"
    trail = start_trail(objective)
    open_initiative(trail["run_id"], objective)
    result = apply_steer(trail["run_id"], "rethink the whole thing from scratch")
    assert result["revision"]["rethink_all"] is True
    actives = [h for h in result["hypothesis"] if h["status"] == "active"]
    assert len(actives) == 1


def test_run_objective_defaults_to_recruitment(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("RUN_FORREST_HOME", str(tmp_path / "rfr"))
    monkeypatch.setenv("RUN_FORREST_SKIP_SYNC", "1")
    project = tmp_path / "proj"
    project.mkdir()
    result = run_objective("write hello world", project_root=project)
    job = Path(result["job_dir"])
    assert (job / "recruit.json").exists()
    assert (job / "stories.json").exists()
    assert (job / "who.md").exists()
    assert result["recruitment"]["lead"]["recruit_id"] != GENERALIST_ID
    assert result["stories"]["authored_by"] == result["recruitment"]["lead"]["recruit_id"]
    voice_lines = [ln for ln in result["voice"].splitlines() if ln.startswith("🌲")]
    assert len(voice_lines) >= 2
    who = (job / "who.md").read_text(encoding="utf-8")
    assert "did **not**" in who
    assert "generalist" in who.lower()
