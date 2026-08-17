"""Always latest — canonical brain syncs from main, not a frozen install snapshot."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from runforrestrun import __version__

DEFAULT_UPSTREAM = "https://github.com/youtextme/run-forrest-run"
RAW_BASE = "https://raw.githubusercontent.com/youtextme/run-forrest-run/main"

# Files that define behavior for every IDE. Refreshed on install and --sync.
SYNC_FILES = (
    "SKILL.md",
    "AGENTS.md",
    "RUN_FORREST_RUN.md",
    "HOW_TO_BUILD.md",
    "runforrestrun/frontier.json",
    "runforrestrun/model_catalog.json",
)


def upstream_url() -> str:
    return os.environ.get("RUN_FORREST_UPSTREAM", DEFAULT_UPSTREAM).rstrip("/")


def raw_url(path: str, ref: str = "main") -> str:
    base = os.environ.get("RUN_FORREST_RAW_BASE", RAW_BASE).rstrip("/")
    if "{ref}" in base or base.endswith("/main"):
        return f"{base.rsplit('/', 1)[0]}/{ref}/{path.lstrip('/')}"
    return f"{base}/{path.lstrip('/')}"


def _fetch(url: str, timeout: float = 12.0) -> bytes | None:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": f"run-forrest-run/{__version__}", "Accept": "*/*"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            return resp.read()
    except (urllib.error.URLError, TimeoutError, OSError):
        return None


def sync_from_upstream(
    dest_dir: Path,
    *,
    ref: str = "main",
    fallback_dir: Path | None = None,
) -> dict:
    """Pull latest canonical files from GitHub main. Fall back to packaged copy."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    pulled: list[str] = []
    failed: list[str] = []
    for rel in SYNC_FILES:
        url = raw_url(rel, ref=ref)
        data = _fetch(url)
        target = dest_dir / rel
        if data is not None:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            pulled.append(rel)
            continue
        failed.append(rel)
        if fallback_dir is not None:
            src = fallback_dir / rel
            if src.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(src.read_bytes())
                pulled.append(f"{rel} (local)")

    meta = {
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "upstream": upstream_url(),
        "ref": ref,
        "version": __version__,
        "pulled": pulled,
        "failed": failed,
    }
    (dest_dir / "SYNC.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return meta
