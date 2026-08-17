"""Model assessor — bar raiser for whichever model is at work.

The objective runner is not model-agnostic. From the first lock it knows
which model is running, researches that model's latest strengths and
deficiencies (or reuses a cache that is a few days to a few weeks old),
and injects extra prompts so the *same* model still clears the bar:
more research, more data points, more effort — never a model switch.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable

from runforrestrun import __version__
from runforrestrun.paths import ensure_layout, models_dir
from runforrestrun.trail import append_event, trail_dir
from runforrestrun.voice import two_lines

# --- constants ----------------------------------------------------------------

ENV_KEYS = (
    "RUN_FORREST_MODEL",
    "CURSOR_MODEL",
    "CURSOR_AGENT_MODEL",
    "ANTHROPIC_MODEL",
    "CLAUDE_MODEL",
    "OPENAI_MODEL",
    "AIDER_MODEL",
    "CODEX_MODEL",
    "GEMINI_MODEL",
    "LLM_MODEL",
    "MODEL_NAME",
)

# Bare MODEL is last and ignored when it looks like a framework flag.
ENV_KEYS_WEAK = ("MODEL",)

DEFAULT_TTL_DAYS = 14
MIN_TTL_DAYS = 3
MAX_TTL_DAYS = 21
DEFAULT_BAR = 80
FAST_BAR = 88

FetchFn = Callable[[str, float], str | None]


# --- identity -----------------------------------------------------------------


@dataclass
class ModelIdentity:
    raw: str
    slug: str
    family: str
    variant: str
    source: str
    vendor: str = "unknown"

    def label(self) -> str:
        if self.variant:
            return f"{self.slug} ({self.family}, {self.variant})"
        return f"{self.slug} ({self.family})"


@dataclass
class Assessment:
    identity: ModelIdentity
    cache_hit: bool
    cache_age_days: float | None
    researched: bool
    dossier: dict[str, Any]
    injected: list[str]
    bar: dict[str, Any]
    research_plan: list[str]
    voice: str = ""
    cache_path: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "identity": asdict(self.identity),
            "cache_hit": self.cache_hit,
            "cache_age_days": self.cache_age_days,
            "researched": self.researched,
            "dossier": self.dossier,
            "injected": list(self.injected),
            "bar": dict(self.bar),
            "research_plan": list(self.research_plan),
            "voice": self.voice,
            "cache_path": self.cache_path,
        }


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def ttl_days() -> int:
    raw = os.environ.get("RUN_FORREST_MODEL_CACHE_DAYS", "").strip()
    if raw:
        try:
            days = int(raw)
        except ValueError:
            days = DEFAULT_TTL_DAYS
    else:
        days = DEFAULT_TTL_DAYS
    return max(MIN_TTL_DAYS, min(MAX_TTL_DAYS, days))


def _slugify(name: str) -> str:
    text = (name or "").strip().lower()
    text = text.replace("_", "-").replace(" ", "-")
    text = re.sub(r"[^a-z0-9.+-]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text or "unknown"


def _family_from_slug(slug: str, catalog: dict[str, Any]) -> tuple[str, str]:
    """Return (family_id, vendor) by longest alias match."""
    families = (catalog or {}).get("families") or {}
    best = ("unknown", "unknown", 0)
    for fid, spec in families.items():
        if fid == "unknown":
            continue
        aliases = [fid, *list(spec.get("aliases") or [])]
        for alias in aliases:
            a = _slugify(str(alias))
            if not a:
                continue
            if slug == a or slug.startswith(a + "-") or a in slug:
                if len(a) > best[2]:
                    best = (fid, str(spec.get("vendor") or "unknown"), len(a))
    return best[0], best[1]


def _variant_from_slug(slug: str, catalog: dict[str, Any]) -> str:
    overlays = (catalog or {}).get("variant_overlays") or {}
    found: list[str] = []
    for name, spec in overlays.items():
        tokens = [str(t).lower() for t in (spec.get("tokens") or [])]
        if any(tok in slug.split("-") or tok in slug for tok in tokens):
            found.append(name)
    # Preserve more specific tokens from the slug itself (high-fast, thinking-high).
    parts = slug.split("-")
    interesting = [
        p
        for p in parts
        if p
        in {
            "fast",
            "high-fast",
            "flash",
            "lite",
            "mini",
            "haiku",
            "luna",
            "thinking",
            "xhigh",
            "max",
            "ultra",
            "low",
            "high",
        }
    ]
    if "high" in parts and "fast" in parts and "high-fast" not in interesting:
        interesting.append("high-fast")
    if interesting:
        return "-".join(dict.fromkeys(interesting))
    return found[0] if found else ""


def detect_model(catalog: dict[str, Any] | None = None) -> ModelIdentity:
    """Who is at work. Env first. Never invent a famous name."""
    cat = catalog if catalog is not None else load_catalog()
    for key in ENV_KEYS:
        raw = os.environ.get(key, "").strip()
        if raw:
            return _identity_from_raw(raw, source=key, catalog=cat)
    for key in ENV_KEYS_WEAK:
        raw = os.environ.get(key, "").strip()
        if raw and _looks_like_model_name(raw):
            return _identity_from_raw(raw, source=key, catalog=cat)
    return _identity_from_raw("unknown", source="undetected", catalog=cat)


def _looks_like_model_name(raw: str) -> bool:
    text = raw.strip().lower()
    if not text or len(text) > 80:
        return False
    if text in {"1", "0", "true", "false", "yes", "no", "auto"}:
        return False
    return bool(re.search(r"[a-z]", text)) and bool(
        re.search(r"(grok|claude|gpt|gemini|opus|sonnet|fable|composer|llama|mistral|kimi|sol|luna|terra)", text)
        or re.search(r"\d", text)
    )


def _identity_from_raw(raw: str, *, source: str, catalog: dict[str, Any]) -> ModelIdentity:
    slug = _slugify(raw)
    family, vendor = _family_from_slug(slug, catalog)
    variant = _variant_from_slug(slug, catalog)
    return ModelIdentity(
        raw=raw,
        slug=slug,
        family=family,
        variant=variant,
        source=source,
        vendor=vendor,
    )


# --- catalog / cache ----------------------------------------------------------


def catalog_path() -> Path:
    return Path(__file__).resolve().parent / "model_catalog.json"


def load_catalog() -> dict[str, Any]:
    path = catalog_path()
    if not path.exists():
        return {"families": {}, "variant_overlays": {}, "ttl_days_default": DEFAULT_TTL_DAYS}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"families": {}, "variant_overlays": {}, "ttl_days_default": DEFAULT_TTL_DAYS}
    if not isinstance(data, dict):
        return {"families": {}, "variant_overlays": {}}
    return data


def cache_dir_for(slug: str) -> Path:
    ensure_layout()
    path = models_dir() / _slugify(slug)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _parse_iso(ts: str) -> datetime | None:
    text = (ts or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def load_cached_dossier(slug: str) -> tuple[dict[str, Any] | None, float | None]:
    path = cache_dir_for(slug) / "dossier.json"
    if not path.exists():
        return None, None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None, None
    if not isinstance(data, dict):
        return None, None
    assessed = _parse_iso(str(data.get("assessed_at") or ""))
    if assessed is None:
        return None, None
    age = (_now() - assessed.astimezone(timezone.utc)).total_seconds() / 86400.0
    return data, age


def cache_is_fresh(age_days: float | None, *, ttl: int | None = None) -> bool:
    if age_days is None:
        return False
    limit = ttl if ttl is not None else ttl_days()
    return 0 <= age_days <= limit


def save_dossier(slug: str, dossier: dict[str, Any]) -> Path:
    dest = cache_dir_for(slug)
    payload = dict(dossier)
    payload.setdefault("assessed_at", _now_iso())
    payload["slug"] = _slugify(slug)
    (dest / "dossier.json").write_text(
        json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8"
    )
    (dest / "research.md").write_text(_dossier_markdown(payload), encoding="utf-8")
    sources = payload.get("sources") or []
    if sources:
        lines = [json.dumps(s, default=str) for s in sources]
        (dest / "sources.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dest / "dossier.json"


# --- seed + live research -----------------------------------------------------


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip = False
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip = False

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        text = " ".join(data.split())
        if text:
            self.parts.append(text)


def html_to_text(blob: str) -> str:
    parser = _TextExtractor()
    try:
        parser.feed(blob)
        parser.close()
    except Exception:
        return re.sub(r"<[^>]+>", " ", blob)
    return " ".join(parser.parts)


def default_fetch(url: str, timeout: float = 12.0) -> str | None:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": f"run-forrest-run/{__version__} model-assessor",
            "Accept": "text/html,application/pdf,application/json,text/plain;q=0.9,*/*;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if getattr(resp, "status", 200) not in {200, 301, 302}:
                return None
            content_type = str(resp.headers.get("Content-Type") or "")
            raw = resp.read()[:400_000]
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None
    if "pdf" in content_type.lower() or url.lower().endswith(".pdf"):
        # Keep printable ASCII so we can still keyword-scan a model card.
        return re.sub(rb"[^\x20-\x7e\n\r\t]", b" ", raw).decode("ascii", errors="ignore")
    text = raw.decode("utf-8", errors="replace")
    if "<html" in text.lower() or "<!doctype" in text.lower():
        return html_to_text(text)
    return text


def _offline() -> bool:
    return os.environ.get("RUN_FORREST_OFFLINE", "").strip().lower() in {"1", "true", "yes", "on"}


def _skip_research() -> bool:
    return os.environ.get("RUN_FORREST_SKIP_MODEL_RESEARCH", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _seed_for(identity: ModelIdentity, catalog: dict[str, Any]) -> dict[str, Any]:
    families = catalog.get("families") or {}
    spec = dict(families.get(identity.family) or families.get("unknown") or {})
    deficiencies = list(spec.get("deficiencies") or [])
    overlays = catalog.get("variant_overlays") or {}
    slug = identity.slug
    variant = identity.variant
    hay = f"{slug} {variant}".lower()
    for spec_overlay in overlays.values():
        tokens = [str(t).lower() for t in (spec_overlay.get("tokens") or [])]
        if any(tok in hay.split() or tok in hay for tok in tokens):
            deficiencies.extend(list(spec_overlay.get("deficiencies") or []))
    # De-dupe by id, last write wins so variant overlay can replace.
    by_id: dict[str, dict[str, Any]] = {}
    for item in deficiencies:
        if not isinstance(item, dict):
            continue
        key = str(item.get("id") or item.get("area") or len(by_id))
        by_id[key] = item
    return {
        "family": identity.family,
        "vendor": identity.vendor or spec.get("vendor") or "unknown",
        "released": spec.get("released") or "",
        "cutoff": spec.get("cutoff") or "unknown",
        "latest": list(spec.get("latest") or []),
        "strengths": list(spec.get("strengths") or []),
        "deficiencies": list(by_id.values()),
        "research_gaps": list(spec.get("research_gaps") or []),
        "research_urls": list(spec.get("research_urls") or []),
        "catalog_updated_at": catalog.get("updated_at") or "",
    }


_FINDING_HINTS = re.compile(
    r"(limit|weak|fail|hallucin|cutoff|sycophan|bench|deficien|regess|not intended|do not|don't|underperform|lag)",
    re.I,
)


def _snippets(text: str, limit: int = 6) -> list[str]:
    if not text:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", " ".join(text.split()))
    hits = [s.strip() for s in sentences if _FINDING_HINTS.search(s) and 40 < len(s) < 400]
    # Unique, stable order.
    out: list[str] = []
    seen: set[str] = set()
    for hit in hits:
        key = hit.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(hit)
        if len(out) >= limit:
            break
    return out


def research_queries(identity: ModelIdentity, objective: str = "") -> list[str]:
    name = identity.raw if identity.raw != "unknown" else identity.family
    queries = [
        f"{name} model card official",
        f"{name} limitations known issues",
        f"{name} SWE-bench Terminal-Bench eval",
        f"{name} knowledge cutoff hallucination",
    ]
    obj = " ".join((objective or "").split())[:80]
    if obj:
        queries.append(f"{name} weaknesses for: {obj}")
    return queries


def _search_url(query: str) -> str:
    return "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})


def research_model(
    identity: ModelIdentity,
    *,
    catalog: dict[str, Any] | None = None,
    fetch: FetchFn | None = None,
    objective: str = "",
) -> dict[str, Any]:
    """Independently research the model. Seed is the prior; live fetch updates it."""
    cat = catalog if catalog is not None else load_catalog()
    seed = _seed_for(identity, cat)
    sources: list[dict[str, Any]] = []
    findings: list[str] = []
    did_fetch = False
    fetch_fn = fetch if fetch is not None else default_fetch

    urls = list(seed.get("research_urls") or [])
    if not _offline() and not _skip_research():
        for query in research_queries(identity, objective)[:2]:
            urls.append(_search_url(query))
        seen_url: set[str] = set()
        for url in urls:
            if url in seen_url:
                continue
            seen_url.add(url)
            body = fetch_fn(url, 12.0)
            if not body:
                sources.append({"url": url, "ok": False})
                continue
            did_fetch = True
            snips = _snippets(body)
            sources.append({"url": url, "ok": True, "snippets": snips[:4]})
            findings.extend(snips)

    # De-dupe findings against seed latest.
    existing = {str(x).lower() for x in seed.get("latest") or []}
    extra_latest = []
    for item in findings:
        key = item.lower()
        if key in existing:
            continue
        existing.add(key)
        extra_latest.append(item)

    dossier = {
        **seed,
        "slug": identity.slug,
        "raw": identity.raw,
        "variant": identity.variant,
        "source": identity.source,
        "assessed_at": _now_iso(),
        "ttl_days": ttl_days(),
        "origin": "research" if did_fetch else "seed",
        "latest": list(seed.get("latest") or []) + extra_latest[:8],
        "live_findings": extra_latest[:8],
        "sources": sources,
        "queries": research_queries(identity, objective),
        "same_model_only": True,
    }
    return dossier


# --- bar + injected prompts ---------------------------------------------------


_CODING = re.compile(
    r"\b(code|bug|test|refactor|implement|patch|api|cli|function|class|compile|lint|typeerror|failing)\b",
    re.I,
)
_RESEARCH = re.compile(
    r"\b(research|look up|latest|why|compare|docs?|paper|benchmark|what is)\b",
    re.I,
)
_UI = re.compile(r"\b(ui|ux|css|layout|button|click|design|frontend)\b", re.I)


def _objective_domains(objective: str) -> set[str]:
    text = objective or ""
    domains: set[str] = set()
    if _CODING.search(text):
        domains.add("coding")
    if _RESEARCH.search(text):
        domains.add("research")
    if _UI.search(text):
        domains.add("ui")
    if not domains:
        domains.add("general")
    return domains


def _is_fast(identity: ModelIdentity) -> bool:
    hay = f"{identity.slug} {identity.variant}".lower()
    return any(tok in hay for tok in ("fast", "flash", "lite", "mini", "haiku", "luna", "low"))


def _relevant_deficiencies(
    dossier: dict[str, Any], identity: ModelIdentity, objective: str
) -> list[dict[str, Any]]:
    domains = _objective_domains(objective)
    items = [d for d in (dossier.get("deficiencies") or []) if isinstance(d, dict)]
    if not items:
        return []
    scored: list[tuple[int, dict[str, Any]]] = []
    for item in items:
        area = f"{item.get('area', '')} {item.get('id', '')}".lower()
        score = 1
        if "coding" in domains and any(k in area for k in ("swe", "terminal", "coding", "software")):
            score += 3
        if "research" in domains and any(k in area for k in ("hallucin", "cutoff", "factual")):
            score += 3
        if _is_fast(identity) and "effort" in area:
            score += 3
        if "cutoff" in area or "hallucin" in area:
            score += 1
        scored.append((score, item))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    # Always keep cutoff + hallucination + under-effort when present.
    picked: list[dict[str, Any]] = []
    seen: set[str] = set()
    for _, item in scored:
        key = str(item.get("id") or item.get("area"))
        if key in seen:
            continue
        seen.add(key)
        picked.append(item)
        if len(picked) >= 6:
            break
    return picked


def build_bar(
    identity: ModelIdentity,
    dossier: dict[str, Any],
    objective: str,
    *,
    catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cat = catalog if catalog is not None else load_catalog()
    base = int(cat.get("good_enough_score") or DEFAULT_BAR)
    fast_bar = int(cat.get("fast_variant_score") or FAST_BAR)
    min_score = fast_bar if _is_fast(identity) else base
    domains = sorted(_objective_domains(objective))
    checks = [
        "Evidence on disk (commands, tests, or trail artifacts) — not confidence.",
        "Claims contacted the world. Citation is not already-proven.",
        "Extra research filled this model's sample-set gaps for this objective.",
        "Same model only: gaps were plugged with more probes, not a model switch.",
        "Objective is actually done — never stop at a plan.",
    ]
    if _is_fast(identity):
        checks.append("Fast-variant effort: second pass after the first plausible draft.")
    if "coding" in domains:
        checks.append("Tests or real commands were run against the change.")
    return {
        "min_score": min_score,
        "good_enough": min_score,
        "model": identity.label(),
        "family": identity.family,
        "variant": identity.variant,
        "domains": domains,
        "checks": checks,
        "dimensions": {
            "evidence": 20,
            "research_coverage": 20,
            "disconfirmation": 20,
            "completeness": 20,
            "gap_plugged": 20,
        },
        "cutoff": dossier.get("cutoff") or "unknown",
        "same_model_only": True,
    }


def build_research_plan(
    identity: ModelIdentity, dossier: dict[str, Any], objective: str
) -> list[str]:
    plan: list[str] = []
    cutoff = str(dossier.get("cutoff") or "unknown")
    plan.append(
        f"Knowledge cutoff ({cutoff}): live-fetch anything this objective needs that may post-date training."
    )
    for gap in list(dossier.get("research_gaps") or [])[:4]:
        plan.append(f"Sample-set gap: {gap}. Gather current data points before concluding.")
    domains = _objective_domains(objective)
    if "coding" in domains:
        plan.append(
            "Coding: reproduce with real commands; do not trust remembered APIs; read the files you will change."
        )
    if "research" in domains or "general" in domains:
        plan.append(
            "Research: at least two independent live sources for version, date, and API claims. Expand the sample set."
        )
    if _is_fast(identity):
        plan.append(
            "Fast variant: run an extra research pass after the first draft. The lane will try to skip it."
        )
    plan.append("Stay on this model. Bridge with more work, not a different model.")
    # Dedup while preserving order.
    out: list[str] = []
    seen: set[str] = set()
    for item in plan:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def build_injected_prompts(
    identity: ModelIdentity,
    dossier: dict[str, Any],
    objective: str,
    bar: dict[str, Any],
    research_plan: list[str],
) -> list[str]:
    """Additional prompts that make *this* model spend the effort the bar needs."""
    prompts: list[str] = []
    prompts.append(
        f"You are {identity.label()}. Do not switch models. You are the bar raiser for this model: "
        f"know where it is weak, plug the gaps with the same model, and do not stop until score "
        f">= {bar.get('min_score', DEFAULT_BAR)}."
    )
    latest = list(dossier.get("latest") or [])[:3]
    if latest:
        prompts.append("Latest on this model: " + " ".join(latest))
    for item in _relevant_deficiencies(dossier, identity, objective):
        area = item.get("area") or item.get("id") or "gap"
        evidence = item.get("evidence") or ""
        bridge = item.get("bridge") or "Probe the world and keep working."
        prompts.append(f"Deficiency ({area}): {evidence} Bridge using this model: {bridge}")
    for step in research_plan[:5]:
        prompts.append(f"Research: {step}")
    prompts.append(
        "Expand the sample set: more web research, more data points, more primary sources — "
        "so answers are more accurate and more objective than this model's training prior."
    )
    prompts.append(
        "Effort contract: first plausible answer is not done. Extra pass. Run the check. "
        "Write evidence on the trail. Meet the bar."
    )
    prompts.append(
        "Honesty: if evidence contradicts the user or your first draft, keep the evidence. "
        "Sycophancy is a known failure mode. Warrants beat agreement."
    )
    return prompts


def _dossier_markdown(dossier: dict[str, Any]) -> str:
    lines = [
        f"# Model dossier — {dossier.get('slug') or 'unknown'}",
        "",
        f"Assessed: {dossier.get('assessed_at')}",
        f"Family: {dossier.get('family')}  \nVendor: {dossier.get('vendor')}  \nVariant: {dossier.get('variant') or 'n/a'}",
        f"Origin: {dossier.get('origin')}  \nCutoff: {dossier.get('cutoff')}",
        "",
        "## Latest",
        "",
    ]
    for item in dossier.get("latest") or []:
        lines.append(f"- {item}")
    lines += ["", "## Deficiencies and same-model bridges", ""]
    for item in dossier.get("deficiencies") or []:
        if not isinstance(item, dict):
            continue
        lines.append(f"- **{item.get('area') or item.get('id')}** — {item.get('evidence')}")
        lines.append(f"  - Bridge: {item.get('bridge')}")
    lines += ["", "## Research gaps (sample set)", ""]
    for gap in dossier.get("research_gaps") or []:
        lines.append(f"- {gap}")
    lines += ["", "## Sources", ""]
    for src in dossier.get("sources") or []:
        if isinstance(src, dict):
            flag = "ok" if src.get("ok") else "miss"
            lines.append(f"- ({flag}) {src.get('url')}")
        else:
            lines.append(f"- {src}")
    return "\n".join(lines).rstrip() + "\n"


def bar_markdown(bar: dict[str, Any], research_plan: list[str], injected: list[str]) -> str:
    lines = [
        f"# Bar — good enough for this objective",
        "",
        f"Model: {bar.get('model')}",
        f"Min score: **{bar.get('min_score')}**. Do not stop below this.",
        f"Same model only: {bar.get('same_model_only', True)}",
        f"Cutoff: {bar.get('cutoff')}",
        "",
        "## Checks",
        "",
    ]
    for check in bar.get("checks") or []:
        lines.append(f"- [ ] {check}")
    lines += ["", "## Research plan (fill the sample set)", ""]
    for step in research_plan:
        lines.append(f"- {step}")
    lines += ["", "## Injected prompts", ""]
    for i, prompt in enumerate(injected, 1):
        lines.append(f"{i}. {prompt}")
    return "\n".join(lines).rstrip() + "\n"


def injected_markdown(identity: ModelIdentity, injected: list[str]) -> str:
    lines = [
        f"# Injected prompts — bar raiser for {identity.label()}",
        "",
        "Mandatory extra instructions for this run. Same model. Plug the gaps.",
        "",
    ]
    for prompt in injected:
        lines.append(f"- {prompt}")
    return "\n".join(lines).rstrip() + "\n"


# --- public assess + trail write ---------------------------------------------


def assess_model(
    objective: str = "",
    *,
    force: bool = False,
    identity: ModelIdentity | None = None,
    catalog: dict[str, Any] | None = None,
    fetch: FetchFn | None = None,
) -> Assessment:
    """Detect (unless given), reuse a fresh cache, or independently research."""
    cat = catalog if catalog is not None else load_catalog()
    ident = identity or detect_model(cat)
    cached, age = load_cached_dossier(ident.slug)
    fresh = cache_is_fresh(age) and not force
    researched = False
    if fresh and cached:
        dossier = cached
        cache_hit = True
    else:
        cache_hit = False
        dossier = research_model(ident, catalog=cat, fetch=fetch, objective=objective)
        save_dossier(ident.slug, dossier)
        researched = True

    bar = build_bar(ident, dossier, objective, catalog=cat)
    plan = build_research_plan(ident, dossier, objective)
    injected = build_injected_prompts(ident, dossier, objective, bar, plan)
    if cache_hit:
        line1 = f"Model at work: {ident.label()}. Cache {age:.1f}d old — reusing dossier."
        line2 = (
            f"Plugging {ident.family} gaps with more research and effort. "
            f"Bar {bar['min_score']}. Same model."
        )
    elif force and age is not None:
        line1 = f"Model at work: {ident.label()}. Forced re-research (cache was {age:.1f}d)."
        line2 = f"Bar raiser on. Min score {bar['min_score']}. Extra probes fill this model's sample set."
    elif age is not None:
        line1 = f"Model at work: {ident.label()}. Cache {age:.1f}d stale — re-researched."
        line2 = f"Bar raiser on. Min score {bar['min_score']}. Extra probes fill this model's sample set."
    else:
        line1 = f"Model at work: {ident.label()}. No cache — independently researched."
        line2 = f"Bar raiser on. Min score {bar['min_score']}. Extra probes fill this model's sample set."

    voice = two_lines(line1, line2)
    dest = cache_dir_for(ident.slug)
    return Assessment(
        identity=ident,
        cache_hit=cache_hit,
        cache_age_days=age,
        researched=researched,
        dossier=dossier,
        injected=injected,
        bar=bar,
        research_plan=plan,
        voice=voice,
        cache_path=str(dest),
    )


def write_assessment(run_id: str, assessment: Assessment) -> Path:
    """Write model.json, bar.md, injected.md onto the trail."""
    job = trail_dir(run_id)
    payload = assessment.as_dict()
    (job / "model.json").write_text(
        json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8"
    )
    (job / "bar.md").write_text(
        bar_markdown(assessment.bar, assessment.research_plan, assessment.injected),
        encoding="utf-8",
    )
    (job / "injected.md").write_text(
        injected_markdown(assessment.identity, assessment.injected),
        encoding="utf-8",
    )
    append_event(
        run_id,
        "model",
        f"{assessment.identity.label()} bar={assessment.bar.get('min_score')} "
        f"cache_hit={assessment.cache_hit} researched={assessment.researched}",
    )
    return job / "model.json"


def assess_and_attach(
    run_id: str,
    objective: str,
    *,
    force: bool = False,
    fetch: FetchFn | None = None,
) -> Assessment:
    assessment = assess_model(objective, force=force, fetch=fetch)
    write_assessment(run_id, assessment)
    return assessment
