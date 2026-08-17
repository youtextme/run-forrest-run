"""Did the current slice — and then the objective — actually get met?"""

from __future__ import annotations

from typing import Any


def synthesize(
    *,
    hypothesis: list[dict[str, Any]],
    stories: list[dict[str, Any]],
    mece: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evidence check. Stories pending ⇒ slice unmet. All hypothesis done ⇒ objective met."""
    pending = [s for s in stories if s.get("status") != "done"]
    done = [s for s in stories if s.get("status") == "done"]
    failed = [s for s in done if s.get("failed")]
    mece = mece or {}
    slice_met = bool(stories) and not pending and not failed and mece.get("ok", True)
    remaining = [h for h in hypothesis if h.get("status") in {"active", "hypothesized"}]
    active_done = all(
        h.get("status") == "done" for h in hypothesis if h.get("status") != "dropped"
    ) and bool(hypothesis)
    objective_met = slice_met and (not remaining or active_done)

    missing = [s["id"] for s in pending]
    if failed:
        missing.extend(f"{s['id']}:failed" for s in failed)
    if mece and not mece.get("ok", True):
        missing.append("mece")

    return {
        "sub_objective_met": slice_met,
        "objective_met": bool(objective_met and slice_met and not remaining),
        "stories_done": [s["id"] for s in done],
        "stories_pending": [s["id"] for s in pending],
        "missing": missing,
        "evidence": [
            {
                "story": s["id"],
                "status": s.get("status"),
                "evidence": s.get("evidence") or "",
            }
            for s in stories
        ],
        "mece_ok": mece.get("ok", True),
    }
