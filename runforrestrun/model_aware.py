"""Model-aware capability — plug model gaps with repeatable cached skills.

The model does not remember Slack (or any access path) across runs.
This module does: store the pattern, review what was efficient, mint a
subskill, cheap-ping it the next time the same shape appears.

Three verbs, always:
- store patterns
- review patterns
- access patterns (and the skills they minted)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runforrestrun.cached_skills import (
    catalog_path,
    list_skills,
    match_skills,
    mint_skill,
    publish_all,
)
from runforrestrun.observer import record_observation
from runforrestrun.paths import ensure_layout, model_aware_dir, runs_dir
from runforrestrun.patterns import (
    detect_surfaces,
    list_patterns,
    load_pattern,
    match_patterns,
    review_pattern,
    upsert_pattern,
)
from runforrestrun.trail import abstract_text, append_event

CAPABILITY = "model-aware"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    tmp.replace(path)


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=True, default=str) + "\n")


def mcp_catalog_path() -> Path:
    return model_aware_dir() / "mcp.json"


def gaps_path() -> Path:
    return model_aware_dir() / "gaps.jsonl"


def load_mcp() -> dict[str, Any]:
    ensure_layout()
    data = _read_json(mcp_catalog_path(), {"updated_at": "", "servers": {}})
    if not isinstance(data, dict):
        return {"updated_at": "", "servers": {}}
    data.setdefault("servers", {})
    return data


def save_mcp(data: dict[str, Any]) -> Path:
    data["updated_at"] = _now()
    path = mcp_catalog_path()
    _write_json(path, data)
    return path


def instruction_for(skills: list[dict[str, Any]], patterns: list[dict[str, Any]]) -> str:
    """Short block for truth.md — what this run should cheap-ping."""
    lines = ["## Model-aware cheap-ping", ""]
    if skills:
        names = ", ".join(f"`{s.get('slug')}`" for s in skills)
        lines.append(f"Cached skills matching this prompt: {names}.")
        lines.append(
            "Run the cached subskill. Do not rediscover auth, layout, or MCP wiring."
        )
        for skill in skills:
            best = skill.get("best_method") or skill.get("how") or ""
            if best:
                lines.append(f"- `{skill.get('slug')}` best method: {best}")
            host = skill.get("host_skill") or f"rfr-{skill.get('slug')}"
            lines.append(
                f"- Host skill: `{host}` — `~/.run-forrest-run/skills/{skill.get('slug')}/SKILL.md`"
            )
    else:
        lines.append(
            "No cached skill matches yet. After you prove an access path, mint a "
            "subskill (`python -m runforrestrun --learned-access SURFACE`) so the "
            "next run skips rediscovery."
        )
    if patterns:
        lines.append("")
        lines.append("Matching patterns:")
        for pat in patterns[:5]:
            best = pat.get("best_method") or "(unscored)"
            lines.append(
                f"- `{pat.get('id')}` hits={pat.get('hits')} "
                f"score={pat.get('match_score', pat.get('score', 0))} best={best}"
            )
    lines += [
        "",
        f"Catalog: `{catalog_path()}`",
        "Patterns: `~/.run-forrest-run/patterns/index.json`",
        "MCP: `~/.run-forrest-run/model-aware/mcp.json`",
        "",
    ]
    return "\n".join(lines)


def matching_gaps(objective: str) -> list[dict[str, Any]]:
    ensure_layout()
    if not gaps_path().exists():
        return []
    obj = (objective or "").lower()
    hits: list[dict[str, Any]] = []
    for line in gaps_path().read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        needle = str(row.get("gap") or "").lower()
        skill = str(row.get("skill") or "").lower()
        if (needle and needle[:40] in obj) or (skill and skill in obj):
            hits.append(row)
        elif any(s in obj for s in (row.get("surfaces") or [])):
            hits.append(row)
    return hits[-8:]


def consult(objective: str, *, run_id: str = "") -> dict[str, Any]:
    """Access stored patterns + cached skills for this prompt. Cheap."""
    ensure_layout()
    patterns = match_patterns(objective)
    skills = match_skills(objective, patterns)
    gaps = matching_gaps(objective)
    surfaces = detect_surfaces(objective)
    return {
        "capability": CAPABILITY,
        "run_id": run_id,
        "surfaces": surfaces,
        "patterns": patterns,
        "skills": skills,
        "gaps_plugged": gaps,
        "cheap_ping": bool(skills),
        "instruction": instruction_for(skills, patterns),
        "catalog": str(catalog_path()),
    }


def remember_run(
    objective: str,
    *,
    run_id: str = "",
    matches: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Every prompt stores a pattern. Chat is not memory; this is."""
    surfaces = detect_surfaces(objective)
    kind = "access" if surfaces else "workflow"
    skill = ""
    if matches:
        skills = list(matches.get("skills") or [])
        if skills:
            skill = str(skills[0].get("slug") or "")
    row = upsert_pattern(
        kind=kind,
        example=objective,
        surfaces=surfaces,
        run_id=run_id,
        skill=skill,
    )
    record_observation(
        kind="pattern",
        note=f"stored {row['id']}",
        example=objective,
        foundational_need=CAPABILITY,
        run_id=run_id,
    )
    return row


def record_access(
    surface: str,
    *,
    method: str = "",
    how: str = "",
    run_id: str = "",
    mcp_server: str = "",
    mcp_tool: str = "",
    cache_src: Path | None = None,
    project_root: Path | None = None,
    success: bool = True,
    steps: int = 1,
) -> dict[str, Any]:
    """Proven access → pattern + cached subskill. Next similar prompt cheap-pings it."""
    ensure_layout()
    surface = (surface or "").strip()
    if not surface:
        raise ValueError("surface is required")
    if method == "mcp" and not mcp_server:
        mcp_server = surface if surface != "mcp" else mcp_server
    how_text = abstract_text(how or f"Use cached {surface} via {method or 'known access'}.")
    skill = mint_skill(
        surface=surface,
        kind="access",
        method=method,
        how=how_text,
        mcp_server=mcp_server,
        mcp_tool=mcp_tool,
        run_id=run_id,
        cache_src=cache_src,
        project_root=project_root,
        best_method=how_text,
    )
    row = upsert_pattern(
        kind="access",
        example=f"{surface} {how_text}",
        surfaces=[surface] + (["mcp"] if method == "mcp" or mcp_server else []),
        run_id=run_id,
        skill=skill["slug"],
        method=how_text,
    )
    reviewed = review_pattern(
        row["id"],
        success=success,
        steps=steps,
        method=how_text,
        notes=f"learned-access {surface}",
        run_id=run_id,
    )
    if run_id:
        append_event(
            run_id,
            "access",
            f"{surface} via {method or 'cached'} — skill rfr-{skill['slug']}",
        )
    if mcp_server:
        register_mcp(
            server=mcp_server,
            tool=mcp_tool,
            how=how_text,
            run_id=run_id,
            mint=False,
        )
    record_observation(
        kind="cached-skill",
        note=f"minted {skill['slug']} via {method or 'access'}",
        example=how_text,
        foundational_need=CAPABILITY,
        run_id=run_id,
    )
    return {
        "skill": skill,
        "pattern": reviewed or row,
        "surface": surface,
    }


def register_mcp(
    *,
    server: str,
    tool: str = "",
    how: str = "",
    run_id: str = "",
    mint: bool = True,
    project_root: Path | None = None,
) -> dict[str, Any]:
    """Inventory an MCP server/tool and optionally mint a cached skill for it."""
    ensure_layout()
    server = (server or "").strip()
    if not server:
        raise ValueError("server is required")
    catalog = load_mcp()
    servers: dict[str, Any] = dict(catalog.get("servers") or {})
    entry = dict(servers.get(server) or {"tools": {}, "hits": 0, "skill": server})
    entry["hits"] = int(entry.get("hits") or 0) + 1
    tools = dict(entry.get("tools") or {})
    if tool:
        tool_row = dict(tools.get(tool) or {"hits": 0, "how": ""})
        tool_row["hits"] = int(tool_row.get("hits") or 0) + 1
        if how:
            tool_row["how"] = abstract_text(how)[:400]
        tools[tool] = tool_row
    entry["tools"] = tools
    if how and not tool:
        entry["how"] = abstract_text(how)[:400]
    servers[server] = entry
    catalog["servers"] = servers
    save_mcp(catalog)
    result: dict[str, Any] = {"server": server, "tool": tool, "mcp": catalog}
    if mint:
        learned = record_access(
            server,
            method="mcp",
            how=how or f"MCP server `{server}`" + (f" tool `{tool}`" if tool else ""),
            run_id=run_id,
            mcp_server=server,
            mcp_tool=tool,
            project_root=project_root,
        )
        result["skill"] = learned["skill"]
        result["pattern"] = learned["pattern"]
    return result


def plug_gap(
    *,
    gap: str,
    plug: str,
    skill: str = "",
    run_id: str = "",
    surfaces: list[str] | None = None,
) -> dict[str, Any]:
    """The model lacked X. We now have Y. Next similar prompt uses Y."""
    ensure_layout()
    found = list(surfaces or detect_surfaces(f"{gap} {plug} {skill}"))
    payload = {
        "ts": _now(),
        "gap": abstract_text(gap)[:400],
        "plug": abstract_text(plug)[:400],
        "skill": skill,
        "surfaces": found,
        "run_id": run_id,
    }
    _append_jsonl(gaps_path(), payload)
    if skill or found:
        upsert_pattern(
            kind="gap",
            example=f"{gap} → {plug}",
            surfaces=found or ([skill] if skill else []),
            run_id=run_id,
            skill=skill,
            method=plug,
        )
    record_observation(
        kind="model-gap",
        note=payload["gap"],
        example=payload["plug"],
        foundational_need=CAPABILITY,
        run_id=run_id,
    )
    return payload


def learn(*, limit_runs: int = 40, project_root: Path | None = None) -> dict[str, Any]:
    """Review stored patterns. Mint skills only from proven access events."""
    ensure_layout()
    minted: list[str] = []
    reviewed: list[str] = []
    known = {str(s.get("slug")) for s in list_skills()}
    run_root = runs_dir()
    if run_root.exists():
        jobs = sorted((p for p in run_root.iterdir() if p.is_dir()), key=lambda p: p.name)
        for job in jobs[-limit_runs:]:
            events_file = job / "events.jsonl"
            if not events_file.exists():
                continue
            lines = [ln for ln in events_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
            event_count = len(lines)
            for line in lines:
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if ev.get("kind") != "access":
                    continue
                text = str(ev.get("text") or "")
                surface = (text.split() or [""])[0].lower().strip(".,:;")
                if not surface:
                    continue
                if surface not in known:
                    skill = mint_skill(
                        surface=surface,
                        kind="access",
                        method="",
                        how=f"Proven on trail `{job.name}`. Use cached {surface}.",
                        run_id=job.name,
                        project_root=project_root,
                    )
                    minted.append(skill["slug"])
                    known.add(skill["slug"])
                pid = f"access-{surface}"
                if load_pattern(pid) is None:
                    upsert_pattern(
                        kind="access",
                        example=text,
                        surfaces=[surface],
                        run_id=job.name,
                        skill=surface,
                    )
                reviewed_row = review_pattern(
                    pid,
                    success=True,
                    steps=max(event_count, 1),
                    method=text,
                    notes="learn-from-access-event",
                    run_id=job.name,
                )
                if reviewed_row and pid not in reviewed:
                    reviewed.append(pid)
    for summary in list_patterns():
        pid = str(summary.get("id") or "")
        if not pid:
            continue
        review_pattern(
            pid,
            success=True,
            steps=int(summary.get("best_steps") or max(int(summary.get("hits") or 1), 1)),
            method=str(summary.get("best_method") or ""),
            notes="learn-review",
        )
        if pid not in reviewed:
            reviewed.append(pid)
    published = publish_all(project_root=project_root)
    return {
        "ok": True,
        "capability": CAPABILITY,
        "minted": minted,
        "reviewed": reviewed,
        "skills": list_skills(),
        "patterns": list_patterns(),
        "mcp": load_mcp(),
        "published": published,
    }


def snapshot() -> dict[str, Any]:
    """Machine-readable view of everything subsequent runs can cheap-ping."""
    ensure_layout()
    return {
        "capability": CAPABILITY,
        "skills": list_skills(),
        "patterns": list_patterns(),
        "mcp": load_mcp(),
        "catalog": str(catalog_path()),
        "gaps_file": str(gaps_path()),
    }
