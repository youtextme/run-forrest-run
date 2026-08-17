"""One initiative: recruit → specialist stories → subvisions → synthesize → revise."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from runforrestrun.recruitment import Recruitment, recruit
from runforrestrun.revision import initial_hypothesis, revise
from runforrestrun.stories import (
    add_stories,
    looks_like_story_add,
    parse_added_stories,
    stories_for_first_slice,
)
from runforrestrun.trail import (
    append_event,
    load_checkpoint,
    record_steer,
    save_checkpoint,
    trail_dir,
    write_plan,
)
from runforrestrun.synthesis import synthesize


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _who_md(recruitment: Recruitment, stories: list[dict[str, Any]]) -> str:
    lines = [
        "# Who did what",
        "",
        "## Recruiter (generalist consultant)",
        f"- id: `{recruitment.recruiter.recruit_id}`",
        "- did: scored specialists with the likelihood-ratio function; asked the question",
        "- did **not**: write the plan, write stories, or assign themselves the work",
        "",
        f"## Lead specialist: {recruitment.lead.title}",
        f"- id: `{recruitment.lead.recruit_id}`",
        f"- likelihood ratio vs generalist: {recruitment.lead.likelihood_ratio:.3f}",
        f"- skill set: {', '.join(recruitment.lead.skill_set[:12])}",
        f"- question: {recruitment.lead.question}",
        "- did: authored the hypothesis and the MECE stories for the first slice",
        "",
        "## Specialists considered",
    ]
    for spec in recruitment.specialists:
        mark = " ← lead" if spec.recruit_id == recruitment.lead.recruit_id else ""
        lines.append(
            f"- `{spec.recruit_id}` {spec.title} LR={spec.likelihood_ratio:.3f}{mark}"
        )
    lines += ["", "## Stories"]
    for story in stories:
        lines.append(
            f"- `{story['id']}` {story['title']} — assigned to "
            f"`{story['assigned_to']}` ({story['assigned_to_title']}); "
            f"authored by `{story['authored_by']}`"
        )
    lines.append("")
    return "\n".join(lines) + "\n"


def _plan_md(
    recruitment: Recruitment,
    hypothesis: list[dict[str, Any]],
    bundle: dict[str, Any],
) -> str:
    lines = [
        "# Plan (living hypothesis)",
        "",
        "Authored by the recruited specialist. The generalist only recruited.",
        "After each slice this file is allowed to change — including a full rethink.",
        "",
        f"**Recruiter:** {recruitment.recruiter.title} (`{recruitment.recruiter.recruit_id}`)",
        f"**Lead:** {recruitment.lead.title} (`{recruitment.lead.recruit_id}`)",
        f"**Science:** {recruitment.function} (α={recruitment.alpha})",
        "",
        "## Hypothesis",
        "",
    ]
    for item in hypothesis:
        mark = {"active": "→", "done": "✓", "dropped": "×"}.get(item.get("status") or "", "·")
        lines.append(f"{mark} `{item['id']}` ({item.get('status')}) {item['title']}")
    lines += ["", "## First-slice stories (MECE)", ""]
    for story in bundle.get("stories") or []:
        lines.append(
            f"- `{story['id']}` [{story.get('status')}] {story['title']} "
            f"— `{story['assigned_to_title']}`"
        )
    mece = bundle.get("mece") or {}
    lines += [
        "",
        f"MECE: exclusive={mece.get('mutually_exclusive')} "
        f"exhaustive={mece.get('collectively_exhaustive')}",
        "",
        "Human review: add stories via steer (`add these N more stories: ...`).",
        "",
    ]
    return "\n".join(lines)


def write_subvisions(run_id: str, bundle: dict[str, Any], recruitment: Recruitment) -> list[str]:
    """One isolated worker folder per story. Agents pull only their payload."""
    job = trail_dir(run_id)
    root = job / "subvisions"
    root.mkdir(parents=True, exist_ok=True)
    live_ids = {s["id"] for s in bundle.get("stories") or []}
    written: list[str] = []
    for story in bundle.get("stories") or []:
        sid = story["id"]
        folder = root / sid
        folder.mkdir(parents=True, exist_ok=True)
        payload = {
            "run_id": run_id,
            "story": story,
            "assigned_to": {
                "recruit_id": story["assigned_to"],
                "title": story["assigned_to_title"],
                "question": story["question"],
            },
            "exclusive_partition": story.get("partition") or [],
            "context_atoms": story.get("atoms") or [],
            "pull": story.get("data_needed") or [],
            "do_not_pull": [
                f"subvisions/{other}/"
                for other in live_ids
                if other != sid
            ],
            "lead": recruitment.lead.as_dict(),
            "done_when": story.get("done_when"),
        }
        _write_json(folder / "payload.json", payload)
        (folder / "brief.md").write_text(
            (
                f"# Subvision `{sid}`\n\n"
                f"Assigned: {story['assigned_to_title']} (`{story['assigned_to']}`)\n\n"
                f"Question: {story['question']}\n\n"
                f"## Exclusive partition\n\n"
                + ", ".join(story.get("partition") or story.get("atoms") or [])
                + "\n\n## Done when\n\n"
                + str(story.get("done_when"))
                + "\n\nPull only `payload.json` in this folder plus lock/truth/recruit. "
                "Other subvisions are mutually exclusive — do not read them.\n"
            ),
            encoding="utf-8",
        )
        written.append(str(folder))
    return written


def _persist(
    run_id: str,
    *,
    recruitment: Recruitment,
    hypothesis: list[dict[str, Any]],
    bundle: dict[str, Any],
    synthesis: dict[str, Any] | None = None,
    extra_checkpoint: dict[str, Any] | None = None,
) -> dict[str, Any]:
    job = trail_dir(run_id)
    rec = recruitment.as_dict()
    _write_json(job / "recruit.json", rec)
    _write_json(job / "stories.json", bundle)
    _write_json(job / "hypothesis.json", {"hypothesis": hypothesis})
    (job / "who.md").write_text(_who_md(recruitment, bundle.get("stories") or []), encoding="utf-8")
    write_plan(run_id, _plan_md(recruitment, hypothesis, bundle))
    write_subvisions(run_id, bundle, recruitment)
    if synthesis is not None:
        _write_json(job / "synthesis.json", synthesis)
    state = load_checkpoint(run_id) or {}
    state.update(
        {
            "phase": "initiative",
            "next_action": "run first-slice subvisions, then synthesize and revise",
            "recruit_lead": recruitment.lead.recruit_id,
            "story_ids": [s["id"] for s in bundle.get("stories") or []],
        }
    )
    if extra_checkpoint:
        state.update(extra_checkpoint)
    save_checkpoint(run_id, state)
    return {
        "run_id": run_id,
        "job_dir": str(job),
        "recruitment": rec,
        "hypothesis": hypothesis,
        "stories": bundle,
        "synthesis": synthesis,
    }


def open_initiative(
    run_id: str,
    objective: str,
    *,
    project_root: Path | None = None,
) -> dict[str, Any]:
    """Default opening of an objective: recruit, then first-slice stories."""
    recruitment = recruit(objective, project_root=project_root)
    hypothesis = initial_hypothesis(recruitment)
    bundle = stories_for_first_slice(recruitment)
    append_event(
        run_id,
        "recruit",
        f"{recruitment.recruiter.title} recruited {recruitment.lead.title} "
        f"(LR={recruitment.lead.likelihood_ratio:.3f})",
    )
    append_event(
        run_id,
        "stories",
        f"{recruitment.lead.title} authored {len(bundle['stories'])} MECE stories "
        f"for first slice; mece_ok={bundle['mece']['ok']}",
    )
    result = _persist(
        run_id,
        recruitment=recruitment,
        hypothesis=hypothesis,
        bundle=bundle,
    )
    result["recruitment_obj"] = recruitment
    return result


def load_initiative(run_id: str) -> dict[str, Any]:
    job = trail_dir(run_id)
    rec_raw = _read_json(job / "recruit.json")
    from runforrestrun.recruitment import Recruit, Recruitment

    def _r(d: dict) -> Recruit:
        return Recruit(
            recruit_id=d["recruit_id"],
            title=d["title"],
            role=d["role"],
            skill_set=list(d.get("skill_set") or []),
            question=d.get("question") or "",
            log_likelihood=float(d.get("log_likelihood") or 0.0),
            likelihood_ratio=float(d.get("likelihood_ratio") or 0.0),
            why=d.get("why") or "",
            eligible_solver=bool(d.get("eligible_solver", True)),
        )

    recruitment = Recruitment(
        objective=rec_raw.get("objective") or "",
        function=rec_raw.get("function") or "",
        alpha=float(rec_raw.get("alpha") or 0.5),
        recruiter=_r(rec_raw["recruiter"]),
        lead=_r(rec_raw["lead"]),
        ranked=[_r(x) for x in rec_raw.get("ranked") or []],
        specialists=[_r(x) for x in rec_raw.get("specialists") or []],
        problem_atoms=list(rec_raw.get("problem_atoms") or []),
        first_slice=rec_raw.get("first_slice") or "",
        later_slices=list(rec_raw.get("later_slices") or []),
    )
    bundle = _read_json(job / "stories.json")
    hypo = _read_json(job / "hypothesis.json").get("hypothesis") or []
    synthesis = None
    if (job / "synthesis.json").exists():
        synthesis = _read_json(job / "synthesis.json")
    return {
        "recruitment": recruitment,
        "bundle": bundle,
        "hypothesis": hypo,
        "synthesis": synthesis,
        "job_dir": str(job),
    }


def complete_story(
    run_id: str,
    story_id: str,
    *,
    evidence: str,
    failed: bool = False,
) -> dict[str, Any]:
    data = load_initiative(run_id)
    bundle = data["bundle"]
    found = False
    for story in bundle["stories"]:
        if story["id"] == story_id:
            story["status"] = "done"
            story["failed"] = failed
            story["evidence"] = evidence
            found = True
            folder = trail_dir(run_id) / "subvisions" / story_id
            folder.mkdir(parents=True, exist_ok=True)
            _write_json(
                folder / "result.json",
                {"story_id": story_id, "failed": failed, "evidence": evidence},
            )
            break
    if not found:
        raise KeyError(f"no story {story_id} on trail {run_id}")
    story_status = "failed" if failed else "done"
    append_event(run_id, "story", f"{story_id} {story_status}: {evidence[:200]}")
    syn = synthesize(
        hypothesis=data["hypothesis"],
        stories=bundle["stories"],
        mece=bundle.get("mece"),
    )
    result = _persist(
        run_id,
        recruitment=data["recruitment"],
        hypothesis=data["hypothesis"],
        bundle=bundle,
        synthesis=syn,
    )
    if syn.get("sub_objective_met"):
        advanced = advance_initiative(run_id, evidence_atoms=[], steer="")
        advanced["auto_advanced"] = True
        advanced["slice_synthesis"] = syn
        return advanced
    result["synthesis"] = syn
    return result


def add_user_stories(run_id: str, message: str) -> dict[str, Any]:
    titles = parse_added_stories(message)
    if not titles:
        titles = [message.strip()] if message.strip() else []
    data = load_initiative(run_id)
    bundle = add_stories(data["bundle"], titles, recruitment=data["recruitment"], source="human")
    append_event(run_id, "stories", f"human added {len(titles)} stories; mece_ok={bundle['mece']['ok']}")
    return _persist(
        run_id,
        recruitment=data["recruitment"],
        hypothesis=data["hypothesis"],
        bundle=bundle,
        synthesis=data.get("synthesis"),
    )


def advance_initiative(
    run_id: str,
    *,
    evidence_atoms: list[str] | None = None,
    steer: str = "",
    unnecessary: list[str] | None = None,
) -> dict[str, Any]:
    """After a slice (or new info): revise the hypothesis; restory if the first slice moved."""
    data = load_initiative(run_id)
    recruitment: Recruitment = data["recruitment"]
    syn = data.get("synthesis") or synthesize(
        hypothesis=data["hypothesis"],
        stories=data["bundle"].get("stories") or [],
        mece=data["bundle"].get("mece"),
    )
    revision = revise(
        data["hypothesis"],
        recruitment=recruitment,
        synthesis=syn,
        steer=steer,
        evidence_atoms=evidence_atoms,
        unnecessary=unnecessary,
    )
    hypothesis = revision["hypothesis"]
    job = trail_dir(run_id)
    with (job / "revisions.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(revision, default=str) + "\n")
    append_event(run_id, "revise", revision["reason"])

    # If the active slice changed, the specialist writes a new MECE story set.
    active = next((h for h in hypothesis if h.get("status") == "active"), None)
    bundle = data["bundle"]
    restory = bool(
        active
        and (
            revision.get("rethink_all")
            or active.get("revision")
            in {"became first remaining slice", "promoted to active", "rethink_all"}
            or str(active.get("title") or "") != str(recruitment.first_slice or "")
        )
    )
    if restory and active:
        job = trail_dir(run_id)
        with (job / "slices.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"closed": bundle, "synthesis": syn}, default=str) + "\n")
        recruitment.first_slice = str(active.get("title") or recruitment.first_slice)
        recruitment.later_slices = [
            str(h.get("title"))
            for h in hypothesis
            if h.get("status") == "hypothesized"
        ]
        bundle = stories_for_first_slice(recruitment)
        append_event(
            run_id,
            "stories",
            f"specialist restoryed active slice {active.get('id')} "
            f"into {len(bundle['stories'])} MECE stories",
        )
        syn = synthesize(
            hypothesis=hypothesis,
            stories=bundle.get("stories") or [],
            mece=bundle.get("mece"),
        )

    still_open = any(h.get("status") in {"active", "hypothesized"} for h in hypothesis)
    objective_met = (not still_open) and bool(syn.get("sub_objective_met"))
    extra = {"phase": "done" if objective_met else "initiative"}
    if objective_met:
        extra["status"] = "done"
        extra["next_action"] = "objective evidenced"
    result = _persist(
        run_id,
        recruitment=recruitment,
        hypothesis=hypothesis,
        bundle=bundle,
        synthesis=syn,
        extra_checkpoint=extra,
    )
    result["revision"] = revision
    result["objective_met"] = bool(objective_met)
    return result


def apply_steer(run_id: str, message: str) -> dict[str, Any]:
    """Course-correct: add stories, rethink the plan, or just record the heading."""
    record_steer(run_id, message)
    if looks_like_story_add(message):
        return add_user_stories(run_id, message)
    lower = (message or "").lower()
    if any(tok in lower for tok in ("rethink", "start over", "wrong plan", "from scratch")):
        return advance_initiative(run_id, steer=message)
    return {"run_id": run_id, "steer": message, "applied": "recorded"}
