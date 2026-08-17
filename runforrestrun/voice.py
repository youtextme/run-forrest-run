"""Two-line forest voice. Casual, funny, enterprise — never a paragraph."""

from __future__ import annotations

from runforrestrun import ICON, INVOKE
from runforrestrun.session_bootstrap import FIRST_MESSAGE_LINE1, FIRST_MESSAGE_LINE2


def session_opening(*, autonomous: bool = True, need: str = "", run_id: str = "") -> str:
    """Mandatory first message for every session (exact SKILL text when autonomous)."""
    if autonomous:
        return f"{FIRST_MESSAGE_LINE1}\n{FIRST_MESSAGE_LINE2}"
    line2 = (
        f"{ICON} I cannot run this autonomously. I need: {need}. "
        f"Trail `{run_id}` is waiting — nothing already found is wasted."
    )
    return f"{FIRST_MESSAGE_LINE1}\n{line2}"


def opening(*, noun: str, run_id: str, autonomous: bool, need: str = "") -> str:
    """The first thing every prompt hears. Exactly two lines."""
    if autonomous:
        return session_opening(autonomous=True)
    return session_opening(autonomous=False, need=need, run_id=run_id)


def two_lines(line1: str, line2: str) -> str:
    a = " ".join((line1 or "").split())
    b = " ".join((line2 or "").split())
    if len(a) > 220:
        a = a[:217] + "..."
    if len(b) > 220:
        b = b[:217] + "..."
    return f"{ICON} {a}\n{ICON} {b}"


def probe_update(*, noun: str, run_id: str, doing: str) -> str:
    return two_lines(
        f"No warrant on {noun!r} yet. {doing}",
        f"Type anything to course-correct. Trail `{run_id}` keeps every finding — nothing is wasted.",
    )


def autonomous_ok(run_id: str) -> str:
    return two_lines(
        "I'm autonomous here — files, shell, network. Step away if you want.",
        f"Type to steer anytime. Trail `{run_id}` is the memory, not the chat.",
    )


def autonomous_blocked(run_id: str, need: str) -> str:
    return two_lines(
        f"I cannot run this autonomously. I need: {need}",
        f"Fix that out of chat, then say go. Trail `{run_id}` is waiting — nothing already found is lost.",
    )


def steer_invite(run_id: str) -> str:
    return two_lines(
        "This is the trail I'm on to find the truth. Course-correct in one line if I'm wrong.",
        f"Full freedom — type whatever. Trail `{run_id}` stores the rest.",
    )


def learned_capability(*, title: str, why_world: str) -> str:
    return two_lines(
        f"Run, Forrest, Run learned a foundational skill: {title}. It's from how you work, not your work.",
        f"{why_world} Say yes and I'll open a PR with your name as full credit — or say no and it stays local.",
    )


def new_host(title: str) -> str:
    return two_lines(
        f"New runner on this machine: {title}. Installing Run, Forrest, Run as the default.",
        "Same canonical trail as every other IDE and CLI. No second brain.",
    )


def done_update(run_id: str, status: str) -> str:
    return two_lines(
        f"Trail `{run_id}` is {status}. Evidence is on disk, not in my confidence.",
        "Open the trail folder, or type the next objective. I'll keep running.",
    )
