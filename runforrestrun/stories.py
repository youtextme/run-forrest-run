"""MECE stories for the *first* hypothesis slice. Specialists author them.

Mutual exclusion is on each story's partition (atoms or roles), not on shared
context. Collective exhaustion is of the first slice: either its atoms, or
the probe/change/evidence roles when the slice does not cut further.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from runforrestrun.recruitment import Recruit, Recruitment, best_for_atoms
from runforrestrun.signature import mece_cuts, unique_atoms

ROLES = ("role:probe", "role:change", "role:evidence")
ROLE_TITLES = {
    "role:probe": "Probe what would kill",
    "role:change": "Make the smallest change warranted",
    "role:evidence": "Contact the world and keep or kill",
}


def _story_id(index: int) -> str:
    return f"S{index}"


def _done_when(title: str, partition: list[str]) -> str:
    focus = " ".join(partition[:6]) or title
    return (
        f"A real-world check has contacted {focus!r} and the claim can be killed or kept."
    )


def assert_mece(stories: list[dict], *, slice_atoms: Iterable[str]) -> dict[str, Any]:
    """Mutually exclusive partitions; collectively exhaustive of the slice."""
    owned: dict[str, str] = {}
    overlaps: list[str] = []
    union: set[str] = set()
    role_parts: set[str] = set()
    atom_parts: set[str] = set()
    for story in stories:
        sid = story["id"]
        parts = list(story.get("partition") or story.get("atoms") or [])
        for key in parts:
            union.add(key)
            if key in ROLES:
                role_parts.add(key)
            else:
                atom_parts.add(key)
            if key in owned and owned[key] != sid:
                overlaps.append(f"{key}: {owned[key]} and {sid}")
            else:
                owned[key] = sid
    required = set(slice_atoms)
    missing_atoms = sorted(required - atom_parts) if atom_parts else []
    missing_roles = [r for r in ROLES if r not in role_parts] if role_parts else []
    if role_parts and not atom_parts:
        missing = missing_roles
        exhaustive = not missing_roles
    elif atom_parts and not role_parts:
        missing = missing_atoms
        exhaustive = not missing_atoms
    else:
        # Roles still cover the slice; human stories are extra exclusive partitions.
        missing = missing_roles
        exhaustive = not missing_roles
    ok = not overlaps and exhaustive
    return {
        "ok": ok,
        "mutually_exclusive": not overlaps,
        "collectively_exhaustive": exhaustive,
        "overlaps": overlaps,
        "missing_atoms": missing,
        "extra_atoms": sorted(atom_parts - required),
    }


def _one_story(
    *,
    index: int,
    title: str,
    atoms: list[str],
    partition: list[str],
    author: Recruit,
    assignee: Recruit,
    source: str,
) -> dict[str, Any]:
    sid = _story_id(index)
    return {
        "id": sid,
        "title": title,
        "atoms": list(atoms),
        "partition": list(partition),
        "authored_by": author.recruit_id,
        "authored_by_title": author.title,
        "assigned_to": assignee.recruit_id,
        "assigned_to_title": assignee.title,
        "question": (
            f"You are {assignee.title}. Exclusive partition: {', '.join(partition)}. "
            f"Do only this story: {title}. Pull subvisions/{sid}/payload.json. "
            "Do not author or execute other stories."
        ),
        "done_when": _done_when(title, partition),
        "data_needed": [
            "lock.md",
            "truth.md",
            "recruit.json",
            f"subvisions/{sid}/payload.json",
        ],
        "status": "pending",
        "source": source,
        "evidence": "",
        "failed": False,
    }


def stories_for_first_slice(recruitment: Recruitment) -> dict[str, Any]:
    """Specialist (not generalist) writes MECE stories for hypothesis item 1."""
    author = recruitment.lead
    if author.role == "recruiter" or not author.eligible_solver:
        raise ValueError("generalist recruiter cannot author stories")

    first = recruitment.first_slice or recruitment.objective
    inner = mece_cuts(first)
    specialists = list(recruitment.specialists) or [author]
    slice_atoms = unique_atoms(first)
    stories: list[dict[str, Any]] = []

    if len(inner) > 1:
        used: set[str] = set()
        for part in inner:
            atoms = [a for a in unique_atoms(part) if a not in used]
            if not atoms:
                atoms = unique_atoms(part) or ["slice"]
            used.update(atoms)
            stories.append(
                _one_story(
                    index=len(stories) + 1,
                    title=part,
                    atoms=atoms,
                    partition=atoms,
                    author=author,
                    assignee=best_for_atoms(specialists, atoms),
                    source="specialist",
                )
            )
        leftover = [a for a in slice_atoms if a not in used]
        if leftover:
            stories.append(
                _one_story(
                    index=len(stories) + 1,
                    title="remaining atoms of the first slice",
                    atoms=leftover,
                    partition=leftover,
                    author=author,
                    assignee=best_for_atoms(specialists, leftover),
                    source="specialist",
                )
            )
    else:
        for role in ROLES:
            stories.append(
                _one_story(
                    index=len(stories) + 1,
                    title=f"{ROLE_TITLES[role]}: {first}",
                    atoms=list(slice_atoms),
                    partition=[role],
                    author=author,
                    assignee=best_for_atoms(specialists, slice_atoms),
                    source="specialist",
                )
            )

    mece = assert_mece(stories, slice_atoms=slice_atoms)
    return {
        "authored_by": author.recruit_id,
        "authored_by_title": author.title,
        "slice": first,
        "slice_atoms": slice_atoms,
        "stories": stories,
        "mece": mece,
        "review": (
            "Human may add stories. The specialist re-checks MECE. "
            "Steer with: add these N more stories: ..."
        ),
    }


_HEADER = re.compile(
    r"^\s*(?:add(?:\s+these)?(?:\s+\d+)?(?:\s+more)?(?:\s+stories?)?:?\s*)",
    re.I,
)
_BULLET = re.compile(r"^\s*(?:[-*]|\d+[.)])\s*")


def parse_added_stories(message: str) -> list[str]:
    """Pull story titles out of a steer note. Numbered, dashed, or semicolon lists."""
    text = (message or "").strip()
    if not text:
        return []
    text = _HEADER.sub("", text, count=1).strip()
    if "\n" in text:
        parts = text.splitlines()
    else:
        parts = re.split(r"\s*;\s*|\s*\|\s*", text)
    chunks: list[str] = []
    for part in parts:
        cleaned = _BULLET.sub("", part).strip().strip(":").strip()
        if not cleaned:
            continue
        if unique_atoms(cleaned):
            chunks.append(cleaned)
    return chunks


def looks_like_story_add(message: str) -> bool:
    lower = (message or "").lower()
    return "stor" in lower and any(w in lower for w in ("add", "more", "another", "extra"))


def add_stories(
    bundle: dict[str, Any],
    titles: list[str],
    *,
    recruitment: Recruitment,
    source: str = "human",
) -> dict[str, Any]:
    """User adds stories. New partitions are exclusive; the specialist re-assigns."""
    author = recruitment.lead
    specialists = list(recruitment.specialists) or [author]
    stories = [dict(s) for s in (bundle.get("stories") or [])]
    claimed: set[str] = set()
    new_rows: list[dict[str, Any]] = []
    start = len(stories)
    for i, title in enumerate(titles, start=1):
        atoms = unique_atoms(title) or [f"added-{start + i}"]
        partition = [a for a in atoms if a not in claimed] or atoms
        claimed.update(partition)
        new_rows.append(
            _one_story(
                index=start + i,
                title=title,
                atoms=atoms,
                partition=partition,
                author=author,
                assignee=best_for_atoms(specialists, atoms),
                source=source,
            )
        )

    kept: list[dict[str, Any]] = []
    for story in stories:
        parts = [p for p in (story.get("partition") or []) if p not in claimed]
        if not parts:
            continue
        story["partition"] = parts
        if story.get("atoms"):
            story["atoms"] = [a for a in story["atoms"] if a not in claimed] or story["atoms"]
        kept.append(story)

    merged = kept + new_rows
    for i, story in enumerate(merged, start=1):
        story["id"] = _story_id(i)
        story["data_needed"] = [
            "lock.md",
            "truth.md",
            "recruit.json",
            f"subvisions/{story['id']}/payload.json",
        ]

    slice_atoms = list(bundle.get("slice_atoms") or [])
    for a in claimed:
        if a not in slice_atoms and a not in ROLES:
            slice_atoms.append(a)
    mece = assert_mece(merged, slice_atoms=slice_atoms)
    bundle = dict(bundle)
    bundle["stories"] = merged
    bundle["slice_atoms"] = slice_atoms
    bundle["mece"] = mece
    bundle["human_added"] = titles
    return bundle
