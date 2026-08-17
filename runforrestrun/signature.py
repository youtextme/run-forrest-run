"""Problem signature — atoms and MECE cuts from the objective, not a job table.

Coordinating cuts (and / then / sentence boundaries) are candidate MECE
siblings. Further splitting stops when it would not change the world.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

# Function words and prompt-filler. Not expertise.
STOP = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "to",
        "of",
        "in",
        "on",
        "for",
        "with",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "is",
        "are",
        "be",
        "been",
        "was",
        "were",
        "as",
        "at",
        "by",
        "from",
        "into",
        "about",
        "please",
        "help",
        "me",
        "my",
        "we",
        "our",
        "you",
        "your",
        "i",
        "need",
        "want",
        "make",
        "sure",
        "also",
        "just",
        "can",
        "could",
        "should",
        "would",
        "will",
        "do",
        "does",
        "doing",
        "done",
        "so",
        "if",
        "then",
        "than",
        "but",
        "not",
        "no",
        "yes",
        "how",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "all",
        "any",
        "each",
        "every",
        "more",
        "most",
        "some",
        "such",
        "very",
        "too",
        "via",
        "using",
        "use",
        "used",
        "ensure",
        "whatever",
        "thing",
        "things",
        "something",
        "everything",
    }
)

# Generic verbs the null generalist is allowed to "know." Distinctive nouns
# are not here — that is how the likelihood ratio punishes a flat prior.
GENERALIST_PRIOR = (
    "do make help work create implement fix write build check look try "
    "handle manage review change update add remove run test plan think "
    "solve decide organize coordinate communicate"
)

_TOKEN = re.compile(r"[a-z][a-z0-9_+-]*", re.I)
_CUT = re.compile(
    r"(?:"
    r"\n+"
    r"|;+"
    r"|\.(?:\s|$)"
    r"|\s+and then\s+"
    r"|\s+and\s+"
    r"|\s+then\s+"
    r"|\s+plus\s+"
    r"|\s+as well as\s+"
    r"|(?:^|\s)\d+[.)]\s+"
    r"|(?:^|\n)\s*[-*]\s+"
    r")",
    re.I,
)


def tokenize(text: str) -> list[str]:
    return [m.group(0).lower() for m in _TOKEN.finditer(text or "")]


def content_atoms(text: str) -> list[str]:
    """Order-preserving distinctive tokens. Duplicates kept as evidence of weight."""
    return [tok for tok in tokenize(text) if tok not in STOP and len(tok) > 1]


def unique_atoms(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for tok in content_atoms(text):
        if tok not in seen:
            seen.add(tok)
            out.append(tok)
    return out


def mece_cuts(text: str) -> list[str]:
    """Split an objective into sibling slices. Empty / stop-only parts drop."""
    raw = (text or "").strip()
    if not raw:
        return []
    parts = [p.strip(" \t:-") for p in _CUT.split(raw) if p and p.strip()]
    kept: list[str] = []
    for part in parts:
        if unique_atoms(part):
            kept.append(part)
    return kept or [raw]


def world_atoms(project_root: Path | None) -> list[str]:
    """Cheap-ping the workspace for contact tokens. Filenames, not job titles."""
    if project_root is None:
        return []
    root = Path(project_root)
    if not root.exists():
        return []
    found: list[str] = []
    probes = (
        ("pyproject.toml", "python"),
        ("pytest.ini", "pytest"),
        ("setup.py", "python"),
        ("package.json", "javascript"),
        ("Cargo.toml", "rust"),
        ("go.mod", "go"),
        ("Dockerfile", "docker"),
        ("SKILL.md", "skill"),
        ("AGENTS.md", "agents"),
    )
    for name, token in probes:
        if (root / name).exists() and token not in found:
            found.append(token)
    tests_dir = root / "tests"
    if tests_dir.is_dir() and "pytest" not in found:
        found.append("tests")
    return found


def signature(
    objective: str,
    *,
    project_root: Path | None = None,
) -> dict:
    """Measurable shape of the problem. This is the input to recruitment."""
    cuts = mece_cuts(objective)
    world = world_atoms(project_root)
    atoms = unique_atoms(objective)
    for tok in world:
        if tok not in atoms:
            atoms.append(tok)
    return {
        "objective": objective,
        "atoms": atoms,
        "cuts": cuts,
        "world_atoms": world,
        "first_slice": cuts[0] if cuts else objective,
        "later_slices": cuts[1:],
    }


def atom_set(texts: Iterable[str]) -> set[str]:
    out: set[str] = set()
    for text in texts:
        out.update(unique_atoms(text))
    return out
