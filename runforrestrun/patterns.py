"""Store, review, and match work patterns so the next similar prompt is cheaper.

Every run writes a pattern. Every reuse reviews it. Best method wins.
Identity is stripped — we keep the shape of the work, never who you are.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runforrestrun.paths import ensure_layout, patterns_dir
from runforrestrun.trail import abstract_text

# Surfaces that mint access subskills once proven. Keep this a catalog of
# *kinds of access*, not anyone's private workspace names.
SURFACE_SPECS: tuple[tuple[str, str], ...] = (
    ("slack", r"\bslack\b"),
    ("github", r"\b(github|\bgh\b|pull request|github\.com)\b"),
    ("discord", r"\bdiscord\b"),
    ("linear", r"\blinear\.app\b|\blinear\b"),
    ("jira", r"\bjira\b"),
    ("notion", r"\bnotion\b"),
    ("pagerduty", r"\bpagerduty\b"),
    ("gmail", r"\bgmail\b|\bgoogle mail\b"),
    ("calendar", r"\b(google calendar|gcal)\b"),
    ("aws", r"\b(aws|amazon web services)\b"),
    ("gcp", r"\b(gcp|google cloud)\b"),
    ("azure", r"\bazure\b"),
    ("docker", r"\bdocker\b"),
    ("kubernetes", r"\b(kubernetes|\bk8s\b)\b"),
    ("postgres", r"\b(postgres|postgresql)\b"),
    ("snowflake", r"\bsnowflake\b"),
    ("bigquery", r"\bbigquery\b"),
    ("datadog", r"\bdatadog\b"),
    ("sentry", r"\bsentry\b"),
    ("stripe", r"\bstripe\b"),
    ("figma", r"\bfigma\b"),
    ("mcp", r"\bmcp\b|model context protocol"),
)

SURFACE_RES: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (name, re.compile(pat, re.I)) for name, pat in SURFACE_SPECS
)

_STOP = frozenset(
    """
    the a an to for and of in on at by with from into over after before
    this that these those is are was were be been being it its you your
    we our they them their not just please help me my i
    """.split()
)

_SLUG = re.compile(r"[^a-z0-9]+")
_MATCH_THRESHOLD = 0.28


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


def slugify(text: str) -> str:
    s = _SLUG.sub("-", (text or "").lower()).strip("-")
    return (s or "pattern")[:48]


def tokens(text: str) -> list[str]:
    abstracted = abstract_text(text or "").lower()
    words = re.findall(r"[a-z0-9][a-z0-9_-]{1,}", abstracted)
    out: list[str] = []
    seen: set[str] = set()
    for word in words:
        if word in _STOP or len(word) < 2:
            continue
        if word not in seen:
            seen.add(word)
            out.append(word)
    return out


def signature(text: str) -> str:
    return " ".join(tokens(text)[:24])


def detect_surfaces(text: str) -> list[str]:
    found: list[str] = []
    for name, pattern in SURFACE_RES:
        if pattern.search(text or ""):
            found.append(name)
    return found


def pattern_id(kind: str, surfaces: list[str], sig: str) -> str:
    if surfaces:
        return f"{slugify(kind)}-{slugify(surfaces[0])}"
    core = slugify(sig) or "workflow"
    return f"{slugify(kind)}-{core[:24]}"


def index_path() -> Path:
    return patterns_dir() / "index.json"


def load_index() -> dict[str, Any]:
    ensure_layout()
    data = _read_json(index_path(), {"updated_at": "", "patterns": []})
    if not isinstance(data, dict):
        return {"updated_at": "", "patterns": []}
    data.setdefault("patterns", [])
    return data


def save_index(data: dict[str, Any]) -> Path:
    data["updated_at"] = _now()
    path = index_path()
    _write_json(path, data)
    return path


def _pattern_path(pid: str) -> Path:
    return patterns_dir() / f"{pid}.json"


def load_pattern(pid: str) -> dict[str, Any] | None:
    data = _read_json(_pattern_path(pid), None)
    return data if isinstance(data, dict) else None


def save_pattern(row: dict[str, Any]) -> Path:
    pid = str(row["id"])
    row["updated_at"] = _now()
    path = _pattern_path(pid)
    _write_json(path, row)
    index = load_index()
    summary = {
        "id": pid,
        "kind": row.get("kind"),
        "surfaces": list(row.get("surfaces") or []),
        "signature": row.get("signature") or "",
        "skill": row.get("skill") or "",
        "hits": int(row.get("hits") or 0),
        "best_method": row.get("best_method") or "",
        "best_steps": row.get("best_steps"),
        "score": float(row.get("score") or 0),
        "last_run_id": row.get("last_run_id") or "",
        "updated_at": row["updated_at"],
    }
    others = [p for p in index["patterns"] if p.get("id") != pid]
    others.append(summary)
    others.sort(key=lambda p: (-int(p.get("hits") or 0), str(p.get("id"))))
    index["patterns"] = others
    save_index(index)
    return path


def append_pattern_event(kind: str, payload: dict[str, Any]) -> None:
    ensure_layout()
    line = json.dumps({"ts": _now(), "kind": kind, **payload}, ensure_ascii=True, default=str)
    with (patterns_dir() / "events.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def upsert_pattern(
    *,
    kind: str,
    example: str,
    surfaces: list[str] | None = None,
    run_id: str = "",
    skill: str = "",
    method: str = "",
) -> dict[str, Any]:
    """Store or update a pattern from a prompt / proven access. Abstracted."""
    ensure_layout()
    text = abstract_text(example or "")
    found = list(surfaces if surfaces is not None else detect_surfaces(example or ""))
    sig = signature(text)
    kind = slugify(kind) or "workflow"
    pid = pattern_id(kind, found, sig)
    row = load_pattern(pid) or {
        "id": pid,
        "kind": kind,
        "surfaces": found,
        "signature": sig,
        "skill": skill,
        "hits": 0,
        "best_method": "",
        "best_steps": None,
        "score": 0.0,
        "reviews": [],
        "examples": [],
        "created_at": _now(),
        "last_run_id": "",
    }
    row["hits"] = int(row.get("hits") or 0) + 1
    row["last_run_id"] = run_id or row.get("last_run_id") or ""
    if found:
        merged = list(dict.fromkeys([*list(row.get("surfaces") or []), *found]))
        row["surfaces"] = merged
    if skill:
        row["skill"] = skill
    if method and not row.get("best_method"):
        row["best_method"] = abstract_text(method)[:400]
    if sig and sig not in (row.get("signature") or ""):
        # Grow the signature with new tokens so similar prompts keep matching.
        merged_sig = signature(f"{row.get('signature') or ''} {sig}")
        row["signature"] = merged_sig
    examples = list(row.get("examples") or [])
    clipped = text[:400]
    if clipped and clipped not in examples:
        examples.append(clipped)
        row["examples"] = examples[-12:]
    save_pattern(row)
    append_pattern_event(
        "store",
        {"id": pid, "kind": kind, "run_id": run_id, "hits": row["hits"]},
    )
    return row


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def match_score(objective: str, pattern: dict[str, Any]) -> float:
    obj_tokens = set(tokens(objective))
    pat_tokens = set(str(pattern.get("signature") or "").split())
    surfaces = [str(s) for s in (pattern.get("surfaces") or [])]
    obj_surfaces = set(detect_surfaces(objective))
    surface_hit = bool(obj_surfaces.intersection(surfaces))
    overlap = _jaccard(obj_tokens, pat_tokens)
    if surface_hit:
        return min(1.0, 0.72 + 0.28 * overlap)
    return overlap


def match_patterns(objective: str, *, limit: int = 8) -> list[dict[str, Any]]:
    """Return stored patterns that look like this objective, best first."""
    index = load_index()
    scored: list[tuple[float, dict[str, Any]]] = []
    for summary in index.get("patterns") or []:
        score = match_score(objective, summary)
        if score < _MATCH_THRESHOLD:
            continue
        full = load_pattern(str(summary.get("id") or "")) or summary
        scored.append((score, {**full, "match_score": round(score, 4)}))
    scored.sort(key=lambda pair: (-pair[0], -int(pair[1].get("hits") or 0)))
    return [row for _, row in scored[:limit]]


def review_pattern(
    pid: str,
    *,
    success: bool,
    steps: int = 1,
    method: str = "",
    notes: str = "",
    run_id: str = "",
) -> dict[str, Any] | None:
    """Score a reuse. Promote the method when it is strictly more efficient."""
    row = load_pattern(pid)
    if row is None:
        return None
    steps_n = max(int(steps), 1)
    score = (1.0 / steps_n) if success else 0.0
    method_text = abstract_text(method or row.get("best_method") or "")[:400]
    review = {
        "ts": _now(),
        "success": bool(success),
        "steps": steps_n,
        "score": score,
        "method": method_text,
        "notes": abstract_text(notes)[:400],
        "run_id": run_id,
    }
    reviews = list(row.get("reviews") or [])
    reviews.append(review)
    row["reviews"] = reviews[-50:]
    best = float(row.get("score") or 0)
    if success and (score > best or row.get("best_method") in {"", None}):
        row["score"] = score
        row["best_method"] = method_text
        row["best_steps"] = steps_n
    elif success and score == best:
        prev_steps = row.get("best_steps")
        if prev_steps is None or steps_n < int(prev_steps):
            row["best_method"] = method_text
            row["best_steps"] = steps_n
            row["score"] = score
    save_pattern(row)
    append_pattern_event("review", {"id": pid, **review})
    return row


def list_patterns() -> list[dict[str, Any]]:
    return list(load_index().get("patterns") or [])
