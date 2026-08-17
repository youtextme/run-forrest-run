"""CLI: run-forrest-run / python -m runforrestrun"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from runforrestrun import BRAND


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="run-forrest-run",
        description=f"{BRAND} — one install, every prompt, shared trail.",
    )
    p.add_argument("objective", nargs="?", help="Objective to run")
    p.add_argument("--install", action="store_true", help="Detect hosts and install as the default")
    p.add_argument("--install-github", action="store_true", help="Install GitHub PAT for Cursor, Devin, OpenClaw, and all agents")
    p.add_argument("--verify-bootstrap", action="store_true", help="Verify Cursor/Devin/OpenClaw session bootstrap (TDD check)")
    p.add_argument("--watch", action="store_true", help="Re-scan for newly installed IDEs/CLIs")
    p.add_argument("--sync", action="store_true", help="Pull latest canonical from GitHub main and re-default all hosts")
    p.add_argument("--status", action="store_true", help="Show canonical home and hosts")
    p.add_argument("--steer", metavar="RUN_ID", help="Append a course-correction to a trail")
    p.add_argument("--message", default="", help="Steer text (with --steer)")
    p.add_argument("--json", action="store_true", help="Machine-readable output")
    p.add_argument("--consent", metavar="SLUG", help="Record yes/no for a community capability PR")
    p.add_argument("--yes", action="store_true", help="Consent yes (with --consent)")
    p.add_argument("--credit", default="", help="Name for PR credit")
    return p


def _packaged() -> Path:
    return Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    packaged = _packaged()

    if args.verify_bootstrap:
        from runforrestrun.session_bootstrap import verify_session_bootstrap

        result = verify_session_bootstrap(Path.cwd())
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            if result["ok"]:
                print("OK — Cursor, Devin, OpenClaw bootstrap verified.")
                print(result["first_message"])
            else:
                print("FAIL — bootstrap errors:")
                for err in result["errors"]:
                    print(f"  - {err}")
        return 0 if result["ok"] else 1

    if args.install_github:
        from runforrestrun.github_credentials import install_github_credentials
        from runforrestrun.voice import two_lines

        result = install_github_credentials(project_root=Path.cwd())
        voice = two_lines(
            f"GitHub PAT installed for Cursor, Devin, OpenClaw. Account: {result.get('account', 'youtextme')}.",
            "Source ~/.config/agent/github.env before gh or git push. Never commit the token.",
        )
        if args.json:
            print(json.dumps({**result, "voice": voice}, indent=2, default=str))
        else:
            print(voice)
        return 0 if result.get("ok") else 1

    if args.install or args.watch or args.sync:
        from runforrestrun.install import install_into_hosts, watch_once
        from runforrestrun.voice import two_lines

        if args.sync:
            result = install_into_hosts(packaged=packaged)
            result["voice"] = two_lines(
                "Synced canonical brain from GitHub main. Every host got the latest skill.",
                f"Hosts: {', '.join(result.get('hosts') or [])}. Reload your IDE.",
            )
        elif args.watch:
            result = watch_once(packaged=packaged)
            if result.get("voice"):
                voice = result["voice"]
            else:
                hosts = ", ".join(result.get("hosts") or []) or "this machine"
                voice = two_lines(
                    f"Run, Forrest, Run! — invoked. Canonical brain at {result.get('canonical')}.",
                    f"Default on: {hosts}. Reload the IDE. Any prompt is a trail. Type to steer.",
                )
        else:
            result = install_into_hosts(packaged=packaged)
            hosts = ", ".join(result.get("hosts") or []) or "this machine"
            sync_info = (result.get("sync") or {}).get("pulled") or []
            sync_note = f" Synced: {len(sync_info)} files from main." if sync_info else ""
            voice = two_lines(
                f"Run, Forrest, Run! — invoked. Canonical brain at {result.get('canonical')}.{sync_note}",
                f"Default on: {hosts}. Reload the IDE. Any prompt is a trail. Type to steer.",
            )
        if result.get("voices"):
            voice = voice + "\n" + "\n".join(result["voices"])
        if args.json:
            print(json.dumps({**result, "voice": voice}, indent=2, default=str))
        else:
            print(voice)
        return 0 if result.get("ok") else 1

    if args.status:
        from runforrestrun.hosts import detect
        from runforrestrun.paths import home, hosts_state_path

        payload = {
            "home": str(home()),
            "hosts_file": str(hosts_state_path()),
            "detected": [h.id for h in detect()],
        }
        if hosts_state_path().exists():
            payload["state"] = json.loads(hosts_state_path().read_text(encoding="utf-8"))
        print(json.dumps(payload, indent=2, default=str))
        return 0

    if args.steer:
        from runforrestrun.trail import record_steer
        from runforrestrun.voice import two_lines

        record_steer(args.steer, args.message or "course-correct")
        print(
            two_lines(
                f"Steer recorded on trail `{args.steer}`. Nothing earlier is wasted.",
                "I'll take that heading. Keep typing if you want another turn.",
            )
        )
        return 0

    if args.consent:
        from runforrestrun.platform import consent_receipt, pr_draft
        from runforrestrun.voice import two_lines

        credit = args.credit or "anonymous operator"
        consent_receipt(args.consent, yes=args.yes, credit_name=credit)
        if args.yes:
            print(
                two_lines(
                    f"You get full credit as {credit}. I'll draft the community PR — your private work stays private.",
                    pr_draft(args.consent, credit).splitlines()[0][:200],
                )
            )
        else:
            print(
                two_lines(
                    "Kept local. No PR. Your trail is still yours.",
                    "Say yes later if you want the world to get the foundational skill.",
                )
            )
        return 0

    objective = args.objective or ""
    if not objective:
        build_parser().print_help()
        return 2

    from runforrestrun.runner import run_objective

    result = run_objective(objective, packaged=packaged)
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(result.get("voice") or "")
        print(f"\ntrail: {result.get('job_dir')}")
    return 0 if result.get("status") in {"running", "done", "partial"} else 1


if __name__ == "__main__":
    sys.exit(main())
