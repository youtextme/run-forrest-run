"""Cached subskills — proven access, token-cheap to reuse.

If this machine already knows how to reach Slack (or GitHub, or an MCP
server), the next run must not spend a laboratory rediscovering it.
Subskills live on disk and are copied next to host skills as `rfr-<slug>`.
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runforrestrun.paths import ensure_layout, skills_dir
from runforrestrun.trail import abstract_text

_SECRET_NAME = re.compile(
    r"(token|secret|password|passwd|credential|api[_-]?key|\.env$|\.pem$|\.p12$|pat$|private)",
    re.I,
)


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


def skill_slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return (s or "skill")[:48]


def skill_dir(slug: str) -> Path:
    return skills_dir() / skill_slug(slug)


def catalog_path() -> Path:
    return skills_dir() / "catalog.json"


def cached_skills_md_path() -> Path:
    return skills_dir() / "CACHED_SKILLS.md"


def load_catalog() -> dict[str, Any]:
    ensure_layout()
    data = _read_json(catalog_path(), {"updated_at": "", "skills": []})
    if not isinstance(data, dict):
        return {"updated_at": "", "skills": []}
    data.setdefault("skills", [])
    return data


def get_skill(slug: str) -> dict[str, Any] | None:
    want = skill_slug(slug)
    for row in load_catalog().get("skills") or []:
        if str(row.get("slug")) == want:
            return row
    access = skill_dir(want) / "access.json"
    data = _read_json(access, None)
    return data if isinstance(data, dict) else None


def looks_secret(path: Path | str) -> bool:
    name = Path(path).name
    return bool(_SECRET_NAME.search(name))


def _skill_md(
    *,
    slug: str,
    title: str,
    kind: str,
    method: str,
    how: str,
    mcp_server: str,
    mcp_tool: str,
    best_method: str,
    cache_files: list[str],
    hits: int,
) -> str:
    cache_list = "\n".join(f"- `{name}`" for name in cache_files) or "- (empty — fill after the next successful probe)"
    mcp_line = ""
    if mcp_server:
        mcp_line = f"- MCP server: `{mcp_server}`" + (f" / tool `{mcp_tool}`" if mcp_tool else "")
        mcp_line += "\n"
    how_text = abstract_text(how or best_method or f"Use the already-proven {title} access path.")
    best = abstract_text(best_method or how_text)
    return (
        f"---\n"
        f"name: rfr-{slug}\n"
        f"description: >-\n"
        f"  Cached {title} access proven on this machine. Use when the\n"
        f"  objective involves {title}. Do not rediscover auth or layout.\n"
        f"---\n\n"
        f"# {title} (cached subskill of Run, Forrest, Run)\n\n"
        f"Do **not** rediscover. This machine already proved this access path.\n"
        f"Cheap-ping this skill and `~/.run-forrest-run/skills/{slug}/cache/` "
        f"before any live probe.\n\n"
        f"## When to use\n\n"
        f"Objectives that match pattern `{kind}:{slug}`. Hits so far: {hits}.\n\n"
        f"## Access\n\n"
        f"- Method: `{method or 'unknown'}`\n"
        f"{mcp_line}"
        f"- Pointers only — never store tokens here. Auth stays in the environment / MCP session.\n"
        f"- If the pointer is dead, re-probe **once**, then update this skill.\n\n"
        f"## How (cached)\n\n"
        f"{how_text}\n\n"
        f"## Best reviewed method\n\n"
        f"{best or 'Not scored yet — first success becomes the baseline.'}\n\n"
        f"## Cached resources\n\n"
        f"{cache_list}\n\n"
        f"## Do not\n\n"
        f"- Do not re-authenticate from scratch when the MCP / CLI session already works.\n"
        f"- Do not re-enumerate the world when a cache file above still matches.\n"
        f"- Do not copy secrets into this folder.\n"
    )


def _render_catalog_md(catalog: dict[str, Any]) -> str:
    rows = list(catalog.get("skills") or [])
    lines = [
        "# Cached subskills",
        "",
        "Cheap-ping this file at the start of every objective. "
        "If a row matches, run that subskill from cache — do not rediscover.",
        "",
        "Catalog: `~/.run-forrest-run/skills/catalog.json`",
        "Patterns: `~/.run-forrest-run/patterns/index.json`",
        "",
    ]
    if not rows:
        lines += [
            "_No cached skills yet._ After you prove an access path "
            "(Slack, GitHub, an MCP server), mint one with "
            "`python -m runforrestrun --learned-access SURFACE`.",
            "",
        ]
        return "\n".join(lines)
    lines += [
        "| Skill | Kind | Method | Hits | Best method |",
        "|-------|------|--------|------|-------------|",
    ]
    for row in rows:
        best = str(row.get("best_method") or "").replace("|", "/")[:80]
        lines.append(
            f"| `{row.get('slug')}` | {row.get('kind') or ''} | "
            f"{row.get('method') or ''} | {row.get('hits') or 0} | {best} |"
        )
    lines.append("")
    for row in rows:
        slug = row.get("slug")
        lines += [
            f"## {slug}",
            "",
            str(row.get("how") or row.get("best_method") or "Run from cache."),
            "",
            f"- Path: `~/.run-forrest-run/skills/{slug}/SKILL.md`",
            f"- Host skill name: `rfr-{slug}`",
            "",
        ]
    return "\n".join(lines)


def save_catalog(catalog: dict[str, Any]) -> Path:
    catalog["updated_at"] = _now()
    skills = list(catalog.get("skills") or [])
    skills.sort(key=lambda r: (-int(r.get("hits") or 0), str(r.get("slug"))))
    catalog["skills"] = skills
    path = catalog_path()
    _write_json(path, catalog)
    cached_skills_md_path().write_text(_render_catalog_md(catalog), encoding="utf-8")
    return path


def cache_resource(slug: str, src: Path) -> Path | None:
    """Copy a non-secret file into the skill cache for later cheap-ping."""
    src = Path(src)
    if not src.is_file() or looks_secret(src):
        return None
    dest_dir = skill_dir(slug) / "cache"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    shutil.copy2(src, dest)
    return dest


def host_skill_destinations(slug: str, *, project_root: Path | None = None) -> list[Path]:
    """Where IDEs will see the subskill without opening the catalog first."""
    name = f"rfr-{skill_slug(slug)}"
    home_root = Path.home()
    dests = [
        home_root / ".agents" / "skills" / name,
        home_root / ".cursor" / "skills" / name,
        home_root / ".claude" / "skills" / name,
        home_root / ".devin" / "skills" / name,
        home_root / ".config" / "devin" / "skills" / name,
    ]
    if project_root is not None:
        root = Path(project_root).resolve()
        dests += [
            root / ".agents" / "skills" / name,
            root / ".cursor" / "skills" / name,
            root / ".claude" / "skills" / name,
            root / ".devin" / "skills" / name,
        ]
    out: list[Path] = []
    seen: set[str] = set()
    for path in dests:
        key = str(path)
        if key not in seen:
            seen.add(key)
            out.append(path)
    return out


def publish_skill(slug: str, body: str, *, project_root: Path | None = None) -> list[str]:
    written: list[str] = []
    for dest in host_skill_destinations(slug, project_root=project_root):
        dest.mkdir(parents=True, exist_ok=True)
        target = dest / "SKILL.md"
        target.write_text(body if body.endswith("\n") else body + "\n", encoding="utf-8")
        written.append(str(target))
    return written


def publish_all(*, project_root: Path | None = None) -> list[str]:
    """Copy every cached subskill into host skill folders (install / watch)."""
    written: list[str] = []
    for row in load_catalog().get("skills") or []:
        slug = str(row.get("slug") or "")
        skill_md = skill_dir(slug) / "SKILL.md"
        if not slug or not skill_md.exists():
            continue
        written.extend(
            publish_skill(slug, skill_md.read_text(encoding="utf-8"), project_root=project_root)
        )
    return written


def mint_skill(
    *,
    surface: str,
    kind: str = "access",
    method: str = "",
    how: str = "",
    mcp_server: str = "",
    mcp_tool: str = "",
    run_id: str = "",
    cache_src: Path | None = None,
    project_root: Path | None = None,
    best_method: str = "",
) -> dict[str, Any]:
    """Create or update a cached subskill from proven access."""
    ensure_layout()
    slug = skill_slug(surface)
    dest = skill_dir(slug)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "cache").mkdir(exist_ok=True)

    cached: list[str] = []
    if cache_src is not None:
        copied = cache_resource(slug, cache_src)
        if copied is not None:
            cached.append(copied.name)
    existing_cache = sorted(p.name for p in (dest / "cache").iterdir() if p.is_file())
    for name in existing_cache:
        if name not in cached:
            cached.append(name)

    catalog = load_catalog()
    previous = next((s for s in catalog["skills"] if s.get("slug") == slug), None)
    hits = int((previous or {}).get("hits") or 0) + 1
    how_text = abstract_text(how or (previous or {}).get("how") or "")[:800]
    method_text = method or (previous or {}).get("method") or ""
    best = abstract_text(best_method or (previous or {}).get("best_method") or how_text)[:400]
    title = slug.replace("-", " ")
    kind = kind or (previous or {}).get("kind") or "access"
    mcp_server = mcp_server or (previous or {}).get("mcp_server") or ""
    mcp_tool = mcp_tool or (previous or {}).get("mcp_tool") or ""
    if method_text == "mcp" and not mcp_server:
        mcp_server = slug if slug != "mcp" else mcp_server

    body = _skill_md(
        slug=slug,
        title=title,
        kind=kind,
        method=method_text,
        how=how_text,
        mcp_server=mcp_server,
        mcp_tool=mcp_tool,
        best_method=best,
        cache_files=cached,
        hits=hits,
    )
    (dest / "SKILL.md").write_text(body, encoding="utf-8")

    access = {
        "slug": slug,
        "title": title,
        "kind": kind,
        "method": method_text,
        "how": how_text,
        "mcp_server": mcp_server,
        "mcp_tool": mcp_tool,
        "best_method": best,
        "hits": hits,
        "cache": cached,
        "minted_from_run": run_id or (previous or {}).get("minted_from_run") or "",
        "updated_at": _now(),
        "path": str(dest / "SKILL.md"),
        "host_skill": f"rfr-{slug}",
        "parent": "run-forrest-run",
    }
    _write_json(dest / "access.json", access)

    others = [s for s in catalog["skills"] if s.get("slug") != slug]
    others.append(
        {
            "slug": slug,
            "title": title,
            "kind": kind,
            "method": method_text,
            "how": how_text,
            "mcp_server": mcp_server,
            "mcp_tool": mcp_tool,
            "best_method": best,
            "hits": hits,
            "path": str(dest / "SKILL.md"),
            "host_skill": f"rfr-{slug}",
            "parent": "run-forrest-run",
            "updated_at": access["updated_at"],
        }
    )
    catalog["skills"] = others
    save_catalog(catalog)
    published = publish_skill(slug, body, project_root=project_root)
    access["published"] = published
    return access


def list_skills() -> list[dict[str, Any]]:
    return list(load_catalog().get("skills") or [])


def match_skills(objective: str, patterns: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Skills this objective should cheap-ping instead of rediscovering."""
    catalog = list_skills()
    if not catalog:
        return []
    wanted: set[str] = set()
    for row in patterns or []:
        skill = str(row.get("skill") or "")
        if skill:
            wanted.add(skill_slug(skill))
        for surface in row.get("surfaces") or []:
            wanted.add(skill_slug(str(surface)))
    from runforrestrun.patterns import detect_surfaces

    for surface in detect_surfaces(objective):
        wanted.add(skill_slug(surface))
    matched: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in catalog:
        slug = str(row.get("slug") or "")
        if slug in wanted and slug not in seen:
            seen.add(slug)
            matched.append(row)
    return matched
