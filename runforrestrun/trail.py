"""One run ID. Everything for a prompt lives here. Chat is not the store."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runforrestrun.paths import ensure_layout, runs_dir


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]


def trail_dir(run_id: str) -> Path:
    path = runs_dir() / run_id
    path.mkdir(parents=True, exist_ok=True)
    (path / "artifacts").mkdir(exist_ok=True)
    return path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def start_trail(objective: str, run_id: str | None = None) -> dict[str, Any]:
    ensure_layout()
    rid = run_id or new_run_id()
    job = trail_dir(rid)
    lock = {
        "run_id": rid,
        "objective": objective,
        "created_at": _now(),
        "phase": "lock",
        "status": "running",
        "steer": [],
        "next_action": "recruit a specialist; they author first-slice stories",
    }
    (job / "lock.md").write_text(
        f"# Lock\n\nRun: `{rid}`\n\nThis run succeeds when the objective is evidenced:\n\n{objective}\n",
        encoding="utf-8",
    )
    (job / "trail.md").write_text(
        f"# Trail `{rid}`\n\nStarted {_now()}\n\nObjective: {objective}\n",
        encoding="utf-8",
    )
    (job / "steer.jsonl").write_text("", encoding="utf-8")
    save_checkpoint(rid, lock)
    append_event(rid, "lock", f"locked {objective!r}")
    return {"run_id": rid, "job_dir": str(job), **lock}


def save_checkpoint(run_id: str, state: dict[str, Any]) -> Path:
    job = trail_dir(run_id)
    payload = dict(state)
    payload["run_id"] = run_id
    payload["updated_at"] = _now()
    path = job / "checkpoint.json"
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    return path


def load_checkpoint(run_id: str) -> dict[str, Any] | None:
    path = runs_dir() / run_id / "checkpoint.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def append_event(run_id: str, kind: str, text: str) -> None:
    job = trail_dir(run_id)
    line = json.dumps({"ts": _now(), "kind": kind, "text": text[:2000]}, ensure_ascii=True)
    with (job / "events.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    trail = job / "trail.md"
    with trail.open("a", encoding="utf-8") as fh:
        fh.write(f"\n- { _now() } **{kind}**: {text[:500]}\n")


def record_steer(run_id: str, message: str) -> None:
    job = trail_dir(run_id)
    payload = {"ts": _now(), "steer": message}
    with (job / "steer.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=True) + "\n")
    append_event(run_id, "steer", message)
    state = load_checkpoint(run_id) or {}
    steers = list(state.get("steer") or [])
    steers.append(message)
    state["steer"] = steers
    state["phase"] = "steer"
    save_checkpoint(run_id, state)


def write_truth(run_id: str, body: str) -> Path:
    path = trail_dir(run_id) / "truth.md"
    path.write_text(body.rstrip() + "\n", encoding="utf-8")
    return path


def write_plan(run_id: str, body: str) -> Path:
    path = trail_dir(run_id) / "plan.md"
    path.write_text(body.rstrip() + "\n", encoding="utf-8")
    return path


_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_HOME = re.compile(r"/Users/[^/\s]+|/home/[^/\s]+|C:\\Users\\[^\\s]+", re.I)


def abstract_text(text: str) -> str:
    """Strip personal pointers. Keep the shape of the work."""
    out = _EMAIL.sub("<email>", text or "")
    out = _HOME.sub("<home>", out)
    out = re.sub(r"\b[A-Z]{2,}-\d{2,}\b", "<ticket>", out)
    return out
