"""Living hypothesis. After every slice, the specialist may rethink the rest."""

from __future__ import annotations

from typing import Any

from runforrestrun.recruitment import Recruitment
from runforrestrun.signature import unique_atoms


def initial_hypothesis(recruitment: Recruitment) -> list[dict[str, Any]]:
    """Specialist's first bet: first MECE cut is active; the rest is hypothesized."""
    items: list[dict[str, Any]] = []
    first = recruitment.first_slice or recruitment.objective
    rest = list(recruitment.later_slices)
    slices = [first, *rest]
    for i, title in enumerate(slices, start=1):
        items.append(
            {
                "id": f"H{i}",
                "title": title,
                "atoms": unique_atoms(title),
                "status": "active" if i == 1 else "hypothesized",
                "author": recruitment.lead.recruit_id,
            }
        )
    if not items:
        items.append(
            {
                "id": "H1",
                "title": recruitment.objective,
                "atoms": unique_atoms(recruitment.objective),
                "status": "active",
                "author": recruitment.lead.recruit_id,
            }
        )
    return items


def _rethink_requested(steer: str) -> bool:
    lower = (steer or "").lower()
    return any(
        tok in lower
        for tok in ("rethink", "start over", "wrong plan", "throw out the plan", "from scratch")
    )


def revise(
    hypothesis: list[dict[str, Any]],
    *,
    recruitment: Recruitment,
    synthesis: dict[str, Any] | None = None,
    steer: str = "",
    evidence_atoms: list[str] | None = None,
    unnecessary: list[str] | None = None,
) -> dict[str, Any]:
    """Re-score the remaining bet. Allowed until the last atom.

    The specialist — not the generalist — owns the revision. New evidence can
    drop, insert, reorder, or throw out the rest of the list.
    """
    prior = [dict(item) for item in hypothesis]
    evidence_atoms = list(evidence_atoms or [])
    unnecessary = set(unnecessary or [])
    synthesis = synthesis or {}
    rethink = _rethink_requested(steer)

    posterior: list[dict[str, Any]] = []
    if rethink:
        # Keep only uncovered atoms as a fresh first slice authored by the lead.
        leftover = []
        seen: set[str] = set()
        for item in prior:
            if item.get("status") == "done":
                continue
            for atom in item.get("atoms") or []:
                if atom not in seen:
                    seen.add(atom)
                    leftover.append(atom)
        title = steer.strip() or "rethought first slice"
        posterior.append(
            {
                "id": "H1",
                "title": title,
                "atoms": leftover or unique_atoms(recruitment.objective),
                "status": "active",
                "author": recruitment.lead.recruit_id,
                "revision": "rethink_all",
            }
        )
        reason = "Steer asked to rethink the whole remaining hypothesis."
    else:
        met = bool(synthesis.get("sub_objective_met"))
        advanced = False
        for item in prior:
            row = dict(item)
            atoms = [a for a in (row.get("atoms") or []) if a not in unnecessary]
            if not atoms and row.get("status") != "done":
                row["status"] = "dropped"
                row["revision"] = "atoms no longer required"
                posterior.append(row)
                continue
            row["atoms"] = atoms or row.get("atoms") or []
            if met and row.get("status") == "active" and not advanced:
                row["status"] = "done"
                row["revision"] = "first slice met"
                posterior.append(row)
                advanced = True
                continue
            if advanced and row.get("status") == "hypothesized":
                row["status"] = "active"
                row["revision"] = "became first remaining slice"
                advanced = False
            posterior.append(row)

        # Evidence atoms that no remaining active/hypothesized item owns.
        owned: set[str] = set()
        for row in posterior:
            if row.get("status") in {"active", "hypothesized"}:
                owned.update(row.get("atoms") or [])
        novel = [a for a in evidence_atoms if a not in owned and a not in unnecessary]
        if novel:
            posterior.append(
                {
                    "id": f"H{len(posterior)+1}",
                    "title": "new atoms from evidence: " + ", ".join(novel[:6]),
                    "atoms": novel,
                    "status": "hypothesized",
                    "author": recruitment.lead.recruit_id,
                    "revision": "inserted from evidence",
                }
            )
        reason = "Updated from synthesis, steer, and evidence atoms."

    # Guarantee exactly one active slice when work remains.
    actives = [r for r in posterior if r.get("status") == "active"]
    remaining = [r for r in posterior if r.get("status") in {"active", "hypothesized"}]
    if not actives and remaining:
        remaining[0]["status"] = "active"
        remaining[0]["revision"] = remaining[0].get("revision") or "promoted to active"

    changed = [p.get("id") for p in posterior] != [p.get("id") for p in prior] or [
        (p.get("id"), p.get("status"), tuple(p.get("atoms") or [])) for p in posterior
    ] != [(p.get("id"), p.get("status"), tuple(p.get("atoms") or [])) for p in prior]

    return {
        "author": recruitment.lead.recruit_id,
        "recruiter_did_not_author": True,
        "rethink_all": rethink,
        "changed": changed,
        "reason": reason,
        "prior": prior,
        "hypothesis": posterior,
    }
