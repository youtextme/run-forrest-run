"""Recruitment — a generalist finds specialists. The generalist never authors.

Science function: multinomial naive-Bayes likelihood ratio against a
generalist null. Expertise is a peaked distribution over problem atoms.
The solver is the candidate that makes the observed problem most likely,
never the recruiter.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from runforrestrun.signature import (
    GENERALIST_PRIOR,
    content_atoms,
    signature,
    unique_atoms,
)

GENERALIST_ID = "recruiter-generalist"
GENERALIST_TITLE = "generalist consultant"
ALPHA = 0.5  # add-alpha smoothing; never zero, never a hard rule table


@dataclass
class Recruit:
    recruit_id: str
    title: str
    role: str  # recruiter | specialist
    skill_set: list[str]
    question: str
    log_likelihood: float
    likelihood_ratio: float
    why: str
    eligible_solver: bool = True

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Recruitment:
    objective: str
    function: str
    alpha: float
    recruiter: Recruit
    lead: Recruit
    ranked: list[Recruit] = field(default_factory=list)
    specialists: list[Recruit] = field(default_factory=list)
    problem_atoms: list[str] = field(default_factory=list)
    first_slice: str = ""
    later_slices: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "objective": self.objective,
            "function": self.function,
            "alpha": self.alpha,
            "null": GENERALIST_TITLE,
            "note": (
                "Expertise is a peaked distribution over problem atoms. "
                "The generalist only recruits. Specialists author stories."
            ),
            "problem_atoms": self.problem_atoms,
            "first_slice": self.first_slice,
            "later_slices": self.later_slices,
            "recruiter": self.recruiter.as_dict(),
            "lead": self.lead.as_dict(),
            "specialists": [s.as_dict() for s in self.specialists],
            "ranked": [r.as_dict() for r in self.ranked],
        }


def _vocab(bags: list[list[str]]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for bag in bags:
        for tok in bag:
            if tok not in seen:
                seen.add(tok)
                out.append(tok)
    return out


def log_prob(problem: list[str], skills: list[str], vocab: list[str], *, alpha: float = ALPHA) -> float:
    """log P(problem | skill bag) under a multinomial with add-alpha smoothing."""
    if not problem:
        return 0.0
    v = max(len(vocab), 1)
    total = float(len(skills))
    counts: dict[str, int] = {}
    for tok in skills:
        counts[tok] = counts.get(tok, 0) + 1
    denom = total + alpha * v
    acc = 0.0
    for tok in problem:
        tf = counts.get(tok, 0)
        acc += math.log((tf + alpha) / denom)
    return acc


def _slug(parts: list[str], limit: int = 4) -> str:
    core = [p for p in parts if p][:limit]
    if not core:
        return "specialist"
    return "-".join(core)


def _question(*, skills: list[str], target: str) -> str:
    skill_txt = ", ".join(skills[:8]) or "the distinctive atoms of this problem"
    return (
        f"You are the person whose skill set is peaked on: {skill_txt}. "
        f"The only question: {target} — what is required, what is not, "
        "and what MECE stories cover the first slice? You author the stories. "
        "The generalist recruiter does not."
    )


def _candidates(sig: dict) -> list[tuple[str, str, list[str], str, bool]]:
    """Derive personas from the problem. No frozen roster of job titles."""
    atoms: list[str] = list(sig["atoms"])
    cuts: list[str] = list(sig["cuts"] or [sig["objective"]])
    rows: list[tuple[str, str, list[str], str, bool]] = []

    rows.append(
        (
            GENERALIST_ID,
            GENERALIST_TITLE,
            unique_atoms(GENERALIST_PRIOR),
            "recruiter",
            False,
        )
    )

    if atoms:
        rows.append(
            (
                f"recruit-{_slug(atoms)}",
                f"{' '.join(atoms[:3])} specialist",
                list(atoms),
                "specialist",
                True,
            )
        )

    for i, cut in enumerate(cuts):
        cut_atoms = unique_atoms(cut)
        if not cut_atoms:
            continue
        rows.append(
            (
                f"recruit-slice-{i+1}-{_slug(cut_atoms)}",
                f"{' '.join(cut_atoms[:3])} specialist",
                cut_atoms,
                "specialist",
                True,
            )
        )

    # Distinctive long tokens as extra peaked experts (not a job table).
    for tok in atoms:
        if len(tok) < 5:
            continue
        rows.append(
            (
                f"recruit-focus-{tok}",
                f"{tok} specialist",
                [tok] + [a for a in atoms if a != tok][:2],
                "specialist",
                True,
            )
        )

    # De-dupe by recruit_id, first wins (generalist + lead stay first).
    seen: set[str] = set()
    out: list[tuple[str, str, list[str], str, bool]] = []
    for row in rows:
        if row[0] in seen:
            continue
        seen.add(row[0])
        out.append(row)
    return out


def recruit(
    objective: str,
    *,
    project_root: Path | None = None,
) -> Recruitment:
    """Generalist consultant scores specialists. Winner authors the work."""
    sig = signature(objective, project_root=project_root)
    problem = content_atoms(objective) or unique_atoms(objective)
    if sig["world_atoms"]:
        problem = list(problem) + list(sig["world_atoms"])

    raw = _candidates(sig)
    bags = [skills for _, _, skills, _, _ in raw]
    vocab = _vocab(bags + [problem])

    generalist_skills = unique_atoms(GENERALIST_PRIOR)
    ll_null = log_prob(problem, generalist_skills, vocab)

    scored: list[Recruit] = []
    for recruit_id, title, skills, role, eligible in raw:
        ll = log_prob(problem, skills, vocab)
        lr = ll - ll_null
        if recruit_id == GENERALIST_ID:
            why = (
                "Null model: flat prior over generic verbs. Recruits only. "
                f"log P(problem|generalist)={ll:.3f}."
            )
        else:
            why = (
                f"Peaked on {', '.join(skills[:6])}. "
                f"log P={ll:.3f}; likelihood ratio vs generalist {lr:.3f}."
            )
        scored.append(
            Recruit(
                recruit_id=recruit_id,
                title=title,
                role=role,
                skill_set=skills,
                question=_question(skills=skills, target=sig["first_slice"] or objective),
                log_likelihood=ll,
                likelihood_ratio=lr,
                why=why,
                eligible_solver=eligible,
            )
        )

    ranked = sorted(
        scored,
        key=lambda r: (r.eligible_solver, r.likelihood_ratio, r.log_likelihood),
        reverse=True,
    )
    recruiter = next(r for r in scored if r.recruit_id == GENERALIST_ID)
    solvers = [r for r in ranked if r.eligible_solver]
    if not solvers:
        # Pathological empty objective: still do not let the generalist author.
        lead = Recruit(
            recruit_id="recruit-problem-specialist",
            title="problem specialist",
            role="specialist",
            skill_set=unique_atoms(objective) or ["objective"],
            question=_question(skills=["this objective"], target=objective),
            log_likelihood=ll_null,
            likelihood_ratio=0.0,
            why="Empty signature; still a specialist authors, not the recruiter.",
            eligible_solver=True,
        )
        solvers = [lead]
        ranked = [lead, recruiter]
    lead = solvers[0]

    return Recruitment(
        objective=objective,
        function="multinomial-naive-bayes-likelihood-ratio",
        alpha=ALPHA,
        recruiter=recruiter,
        lead=lead,
        ranked=ranked,
        specialists=solvers,
        problem_atoms=list(sig["atoms"]),
        first_slice=str(sig["first_slice"]),
        later_slices=list(sig["later_slices"]),
    )


def best_for_atoms(specialists: list[Recruit], atoms: list[str]) -> Recruit:
    """Assign a story to the specialist whose skills make those atoms most likely."""
    if not specialists:
        raise ValueError("no specialists to assign")
    problem = list(atoms) or ["objective"]
    bags = [s.skill_set for s in specialists]
    vocab = _vocab(bags + [problem])
    best = specialists[0]
    best_ll = float("-inf")
    for spec in specialists:
        ll = log_prob(problem, spec.skill_set, vocab)
        if ll > best_ll:
            best_ll = ll
            best = spec
    return best
