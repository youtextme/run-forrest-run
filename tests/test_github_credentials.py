
def test_install_github_credentials(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("RUN_FORREST_HOME", str(tmp_path / "rfr"))
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    token = "ghp_test_token_for_unit_tests_only"
    (home / ".config" / "cursor").mkdir(parents=True)
    (home / ".config" / "cursor" / "github_pat").write_text(token + "\n", encoding="utf-8")
    project = tmp_path / "proj"
    project.mkdir()
    from runforrestrun.github_credentials import install_github_credentials

    result = install_github_credentials(project_root=project)
    assert result["ok"] is True
    assert result["account"] == "youtextme"
    agent_env = home / ".config" / "agent" / "github.env"
    assert agent_env.exists()
    assert token in agent_env.read_text(encoding="utf-8")
    cursor_rule = home / ".cursor" / "rules" / "github-credentials.mdc"
    assert cursor_rule.exists()
    assert "Girish Mahadevan" in cursor_rule.read_text(encoding="utf-8")
    devin_doc = project / ".devin" / "GITHUB_CREDENTIALS.md"
    assert devin_doc.exists()
    agents = (project / "AGENTS.md").read_text(encoding="utf-8")
    assert "youtextme" in agents
    assert "personal access token" in agents.lower()
