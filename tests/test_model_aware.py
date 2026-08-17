"""Model-aware cached skills — store, review, and cheap-ping patterns."""

from __future__ import annotations

from pathlib import Path

from runforrestrun.cached_skills import looks_secret, mint_skill
from runforrestrun.model_aware import (
    consult,
    learn,
    plug_gap,
    record_access,
    register_mcp,
    remember_run,
    snapshot,
)
from runforrestrun.patterns import review_pattern, upsert_pattern
from runforrestrun.runner import run_objective
from runforrestrun.trail import start_trail


def test_remember_run_stores_abstracted_pattern(tmp_path, monkeypatch):
    monkeypatch.setenv("RUN_FORREST_HOME", str(tmp_path / "rfr"))
    row = remember_run("Ask ada@example.com to post in Slack", run_id="r1")
    assert row["id"] == "access-slack"
    assert row["hits"] == 1
    assert "ada@example.com" not in str(row)
    assert "<email>" in " ".join(row.get("examples") or [])


def test_record_access_mints_slack_subskill(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("RUN_FORREST_HOME", str(tmp_path / "rfr"))
    result = record_access(
        "slack",
        method="mcp",
        how="MCP slack list_channels then post. Workspace already authorized.",
        run_id="r9",
        mcp_tool="list_channels",
        project_root=tmp_path / "proj",
    )
    skill = result["skill"]
    assert skill["slug"] == "slack"
    assert skill["host_skill"] == "rfr-slack"
    skill_md = Path(skill["path"]).read_text(encoding="utf-8")
    assert "Do **not** rediscover" in skill_md
    assert "list_channels" in skill_md or "mcp" in skill_md.lower()
    catalog = (tmp_path / "rfr" / "skills" / "catalog.json").read_text(encoding="utf-8")
    assert "slack" in catalog
    host = home / ".cursor" / "skills" / "rfr-slack" / "SKILL.md"
    assert host.exists()
    assert "rfr-slack" in host.read_text(encoding="utf-8")


def test_consult_returns_cached_slack_on_similar_prompt(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("RUN_FORREST_HOME", str(tmp_path / "rfr"))
    record_access(
        "slack",
        method="mcp",
        how="Use MCP slack. Do not re-auth.",
        run_id="first",
    )
    aware = consult("post a standup message to slack #eng")
    assert aware["cheap_ping"] is True
    slugs = [s["slug"] for s in aware["skills"]]
    assert "slack" in slugs
    ids = [p["id"] for p in aware["patterns"]]
    assert "access-slack" in ids
    assert "do not rediscover" in aware["instruction"].lower()


def test_second_access_increments_hits_no_duplicate_skill(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("RUN_FORREST_HOME", str(tmp_path / "rfr"))
    record_access("slack", method="mcp", how="first", run_id="a")
    record_access("slack", method="mcp", how="second, fewer steps", run_id="b", steps=2)
    skills = snapshot()["skills"]
    slack = [s for s in skills if s["slug"] == "slack"]
    assert len(slack) == 1
    assert slack[0]["hits"] == 2


def test_review_promotes_more_efficient_method(tmp_path, monkeypatch):
    monkeypatch.setenv("RUN_FORREST_HOME", str(tmp_path / "rfr"))
    row = upsert_pattern(kind="access", example="talk to slack", surfaces=["slack"])
    review_pattern(row["id"], success=True, steps=9, method="browse the slack web UI")
    better = review_pattern(row["id"], success=True, steps=2, method="mcp slack post_message")
    assert better is not None
    assert better["best_steps"] == 2
    assert "mcp slack" in better["best_method"]


def test_catalog_strips_identity_and_rejects_secret_cache(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("RUN_FORREST_HOME", str(tmp_path / "rfr"))
    secret = tmp_path / "slack_token.txt"
    secret.write_text("xoxb-secret", encoding="utf-8")
    assert looks_secret(secret) is True
    ok = tmp_path / "channels.json"
    ok.write_text('{"channels": ["eng"]}', encoding="utf-8")
    result = record_access(
        "slack",
        method="mcp",
        how="Ask bob@corp.com via slack",
        cache_src=ok,
    )
    assert "bob@corp.com" not in str(result["skill"])
    cache_dir = tmp_path / "rfr" / "skills" / "slack" / "cache"
    assert (cache_dir / "channels.json").exists()
    denied = record_access("slack", method="mcp", how="again", cache_src=secret)
    assert "slack_token.txt" not in (denied["skill"].get("cache") or [])


def test_register_mcp_builds_capability_and_skill(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("RUN_FORREST_HOME", str(tmp_path / "rfr"))
    result = register_mcp(
        server="slack",
        tool="post_message",
        how="call post_message with channel + text",
        run_id="m1",
    )
    assert "slack" in result["mcp"]["servers"]
    assert "post_message" in result["mcp"]["servers"]["slack"]["tools"]
    assert result["skill"]["slug"] == "slack"
    assert result["skill"]["method"] == "mcp"


def test_plug_gap_surfaces_on_consult(tmp_path, monkeypatch):
    monkeypatch.setenv("RUN_FORREST_HOME", str(tmp_path / "rfr"))
    plug_gap(
        gap="model did not know slack MCP wiring",
        plug="use cached rfr-slack",
        skill="slack",
        surfaces=["slack"],
    )
    aware = consult("need slack MCP wiring")
    assert aware["gaps_plugged"]
    assert aware["gaps_plugged"][0]["skill"] == "slack"


def test_run_objective_stores_pattern_and_cheap_pings(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("RUN_FORREST_HOME", str(tmp_path / "rfr"))
    monkeypatch.setenv("RUN_FORREST_SKIP_SYNC", "1")
    project = tmp_path / "proj"
    project.mkdir()
    packaged = Path(__file__).resolve().parents[1]
    record_access(
        "slack",
        method="mcp",
        how="cached slack MCP",
        project_root=project,
    )
    result = run_objective(
        "list slack channels then post hello",
        project_root=project,
        packaged=packaged,
    )
    assert result["model_aware"]["cheap_ping"] is True
    assert any(s["slug"] == "slack" for s in result["cached_skills"])
    voice = result["voice"]
    assert "Cached skill" in voice
    truth = Path(result["job_dir"]) / "truth.md"
    body = truth.read_text(encoding="utf-8")
    assert "Model-aware cheap-ping" in body
    assert "slack" in body
    # pattern from this run is on disk for the *next* run
    nxt = consult("post to slack again")
    assert nxt["cheap_ping"] is True


def test_learn_mints_from_access_events_not_mentions(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("RUN_FORREST_HOME", str(tmp_path / "rfr"))
    started = start_trail("maybe mention slack someday")
    # mention-only: learn must not mint
    out = learn()
    assert "slack" not in (out.get("minted") or [])
    from runforrestrun.trail import append_event

    append_event(started["run_id"], "access", "github via cli — skill rfr-github")
    out2 = learn()
    assert "github" in out2["minted"]
    assert any(s["slug"] == "github" for s in out2["skills"])


def test_parent_skill_documents_model_aware():
    root = Path(__file__).resolve().parents[1]
    skill = (root / "SKILL.md").read_text(encoding="utf-8")
    assert "Model-aware" in skill
    assert "catalog.json" in skill
    assert "--learned-access" in skill


def test_minted_skill_is_runnable_without_rediscovery(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("RUN_FORREST_HOME", str(tmp_path / "rfr"))
    access = mint_skill(
        surface="slack",
        kind="access",
        method="mcp",
        how="Use the slack MCP session already on this machine.",
        mcp_server="slack",
        mcp_tool="list_channels",
    )
    body = Path(access["path"]).read_text(encoding="utf-8")
    assert "Do **not** rediscover" in body
    assert "rfr-slack" in body
    assert "cache/" in body
    index = (tmp_path / "rfr" / "skills" / "CACHED_SKILLS.md").read_text(encoding="utf-8")
    assert "rfr-slack" in index or "`slack`" in index


def test_cli_learned_access_and_skills(tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("RUN_FORREST_HOME", str(tmp_path / "rfr"))
    monkeypatch.chdir(tmp_path)
    from runforrestrun.__main__ import main

    code = main(
        [
            "--learned-access",
            "slack",
            "--method",
            "mcp",
            "--how",
            "use slack MCP",
            "--json",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "slack" in out
    code = main(["--skills", "--json"])
    assert code == 0
    listed = capsys.readouterr().out
    assert "slack" in listed
    code = main(["--patterns", "--json"])
    assert code == 0
    patterns = capsys.readouterr().out
    assert "access-slack" in patterns

