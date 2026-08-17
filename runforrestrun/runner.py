"""Invoke Run, Forrest, Run on an objective."""

from __future__ import annotations

from pathlib import Path

from runforrestrun.assessor import assess_and_attach
from runforrestrun.autonomy import check_autonomy
from runforrestrun.initiative import open_initiative
from runforrestrun.install import watch_once
from runforrestrun.model_aware import consult, remember_run
from runforrestrun.observer import record_observation
from runforrestrun.platform import maybe_propose
from runforrestrun.trail import (
    append_event,
    start_trail,
    write_truth,
)
from runforrestrun.voice import cached_skill_voice, opening


def _noun(objective: str) -> str:
    text = (objective or "").strip()
    return text[:80] if text else "the ask"


def run_objective(
    objective: str,
    *,
    project_root: Path | None = None,
    packaged: Path | None = None,
) -> dict:
    """Start a trail, recruit a specialist, write first-slice stories."""
    watch = watch_once(project_root=project_root, packaged=packaged)
    trail = start_trail(objective)
    run_id = trail["run_id"]
    noun = _noun(objective)
    auto = check_autonomy(objective)

    voice = opening(
        noun=noun,
        run_id=run_id,
        autonomous=auto.ok,
        need=auto.need,
    )
    aware = consult(objective, run_id=run_id)
    remember_run(objective, run_id=run_id, matches=aware)
    assessment = assess_and_attach(run_id, objective)
    write_truth(
        run_id,
        f"# Atoms\n\nObjective: {objective}\n\n"
        f"Model: {assessment.identity.label()} (source: {assessment.identity.source})\n"
        f"Bar: {assessment.bar.get('min_score')} — same model, plug the gaps.\n\n"
        f"Unknown until probed. Designed disconfirmation comes first.\n"
        f"Type to course-correct. This file is the semantic scratch for the run.\n\n"
        f"{aware['instruction']}\n",
    )
    opened = open_initiative(run_id, objective, project_root=project_root)
    opened.pop("recruitment_obj", None)
    append_event(run_id, "laboratory", "trail opened; specialist recruited; first-slice stories ready")
    if aware.get("cheap_ping"):
        append_event(
            run_id,
            "cheap-ping",
            "cached skills: " + ", ".join(s.get("slug") or "" for s in aware.get("skills") or []),
        )
    record_observation(
        kind="run",
        note="objective started with recruitment",
        example=objective,
        foundational_need="",
        run_id=run_id,
    )
    proposal = maybe_propose(objective, run_id=run_id)
    if assessment.voice:
        voice = voice + "\n" + assessment.voice
    if proposal:
        voice = voice + "\n" + str(proposal.get("voice") or "")
    if aware.get("skills"):
        slugs = [str(s.get("slug") or "") for s in aware["skills"] if s.get("slug")]
        best = str((aware["skills"][0].get("best_method") or ""))[:120]
        voice = voice + "\n" + cached_skill_voice(slugs=slugs, run_id=run_id, best=best)
    return {
        "run_id": run_id,
        "job_dir": trail["job_dir"],
        "status": "running" if auto.ok else "blocked",
        "autonomy": auto.ok,
        "need": auto.need,
        "voice": voice,
        "hosts": watch.get("hosts") or [],
        "new_hosts": watch.get("new_hosts") or [],
        "proposal": proposal,
        "canonical": watch.get("canonical"),
        "model_aware": aware,
        "cached_skills": aware.get("skills") or [],
        "model": assessment.identity.label(),
        "bar": assessment.bar,
        "injected": assessment.injected,
        "assessor": assessment.as_dict(),
        "recruitment": opened.get("recruitment"),
        "hypothesis": opened.get("hypothesis"),
        "stories": opened.get("stories"),
    }
