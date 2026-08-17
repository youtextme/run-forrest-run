"""Invoke Run, Forrest, Run on an objective."""

from __future__ import annotations

from pathlib import Path

from runforrestrun.assessor import assess_and_attach
from runforrestrun.autonomy import check_autonomy
from runforrestrun.install import watch_once
from runforrestrun.observer import record_observation
from runforrestrun.platform import maybe_propose
from runforrestrun.trail import (
    append_event,
    start_trail,
    write_plan,
    write_truth,
)
from runforrestrun.voice import opening


def _noun(objective: str) -> str:
    text = (objective or "").strip()
    return text[:80] if text else "the ask"


def run_objective(
    objective: str,
    *,
    project_root: Path | None = None,
    packaged: Path | None = None,
) -> dict:
    """Start a trail, speak two lines, keep everything under one ID."""
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
    assessment = assess_and_attach(run_id, objective)
    write_truth(
        run_id,
        f"# Atoms\n\nObjective: {objective}\n\n"
        f"Model: {assessment.identity.label()} (source: {assessment.identity.source})\n"
        f"Bar: {assessment.bar.get('min_score')} — same model, plug the gaps.\n\n"
        f"Unknown until probed. Designed disconfirmation comes first.\n"
        f"Type to course-correct. This file is the semantic scratch for the run.\n",
    )
    write_plan(
        run_id,
        f"# Plan\n\n"
        f"1. Lock the noun. Know the model ({assessment.identity.label()}).\n"
        f"2. Apply injected bar-raiser prompts — extra research, extra data points.\n"
        f"3. Probe unknowns.\n"
        f"4. Do the work. Never stop at a plan.\n"
        f"5. Check evidence against bar {assessment.bar.get('min_score')}.\n",
    )
    append_event(run_id, "laboratory", "trail opened; waiting on probes")
    record_observation(
        kind="run",
        note="objective started",
        example=objective,
        foundational_need="",
        run_id=run_id,
    )
    proposal = maybe_propose(objective, run_id=run_id)
    if assessment.voice:
        voice = voice + "\n" + assessment.voice
    if proposal:
        voice = voice + "\n" + str(proposal.get("voice") or "")
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
        "model": assessment.identity.label(),
        "bar": assessment.bar,
        "injected": assessment.injected,
        "assessor": assessment.as_dict(),
    }
