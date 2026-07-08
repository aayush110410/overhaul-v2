"""Region intelligence: plain-English prompt → RegionProfile + ScenarioConditions.

Resolution ladder (cheapest first — token efficiency is a hard requirement):
  1. Gazetteer regex over curated + previously-generated region profiles (free).
  2. Place-candidate extraction (capitalized, then filtered lowercase phrases)
     → Nominatim geocode (free, keyless).
  3. One LLM call (via an injected async callable, normally the reasoning
     gateway) that extracts a place name from the prompt — last resort only.
  4. Default region (Delhi NCR).

Unknown-but-geocodable places get a profile generated from
``data/regions/_generic_template.json`` (Indian defaults borrowed from the NCR
profile when the place is in India) and persisted under
``data/regions/generated/`` so the cost is paid at most once per place, ever.
"""

from __future__ import annotations

import copy
import json
import logging
import math
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from llm.geocoding import geocode as _nominatim_geocode

logger = logging.getLogger(__name__)

GeocodeFn = Callable[[str], Awaitable[List[Dict[str, Any]]]]
LlmFn = Callable[[str], Awaitable[Optional[str]]]

_REGIONS_DIR = Path(__file__).resolve().parent.parent / "data" / "regions"
_TEMPLATE_NAME = "_generic_template.json"

DEFAULT_REGION_KEY = "ncr"

# Nominatim result types accepted as simulate-able places.
_PLACE_TYPES = frozenset(
    {
        "city", "town", "village", "hamlet", "suburb", "neighbourhood",
        "quarter", "borough", "municipality", "county", "state", "province",
        "region", "district", "city_district", "locality", "administrative",
    }
)

# Tokens stripped from lowercase place candidates before geocoding.
_STOPWORDS = frozenset(
    {
        "the", "a", "an", "this", "that", "my", "our", "your", "every", "each",
        "morning", "evening", "afternoon", "night", "rush", "hour", "hours",
        "peak", "time", "today", "tomorrow", "week", "month", "year",
        "traffic", "congestion", "rain", "rains", "raining", "rainfall",
        "storm", "smog", "winter", "summer", "monsoon", "diwali", "downtown",
    }
)

_MAX_GEOCODE_CANDIDATES = 3


# ── Scenario conditions ──


@dataclass(frozen=True)
class ScenarioConditions:
    """Weather/time/date context extracted from the prompt (not interventions)."""

    precip_mm_h: Optional[float] = None
    time_of_day: Optional[str] = None
    date_context: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


_PRECIP_PATTERNS: List[Tuple[str, float]] = [
    (r"heavy rain|downpour|cloudburst|torrential|thunderstorm|\bstorm\b", 15.0),
    (r"drizzle|light rain", 2.0),
    (r"\brain(s|ing|fall|y)?\b|\bshowers?\b", 8.0),
    (r"\bsnow(s|ing|fall|storm)?\b", 5.0),
]

_TIME_PATTERNS: List[Tuple[str, str]] = [
    (r"evening rush|rush hours? (in|of)? ?the evening|pm rush", "rush_hour_pm"),
    (r"morning rush|rush hours? (in|of)? ?the morning|am rush", "rush_hour_am"),
    (r"rush hours?|peak hours?|peak traffic", "rush_hour_am"),
    (r"\bnight\b|midnight", "night"),
    (r"\bmorning\b", "morning"),
    (r"\bevening\b", "evening"),
    (r"\bafternoon\b", "afternoon"),
]

_DATE_PATTERNS: List[Tuple[str, str]] = [
    (r"diwali|deepavali", "diwali"),
    (r"holi\b", "holi"),
    (r"\bwinter\b|\bsmog\b|december|january", "winter"),
    (r"monsoon", "monsoon"),
    (r"\bsummer\b|heat ?wave", "summer"),
]


def parse_conditions(prompt: str) -> ScenarioConditions:
    """Extract weather/time/date context from a plain-English prompt."""
    low = prompt.lower()
    precip = next((v for pat, v in _PRECIP_PATTERNS if re.search(pat, low)), None)
    time_of_day = next((v for pat, v in _TIME_PATTERNS if re.search(pat, low)), None)
    date_context = next((v for pat, v in _DATE_PATTERNS if re.search(pat, low)), None)
    return ScenarioConditions(precip, time_of_day, date_context)


# ── Region profile ──


@dataclass
class RegionProfile:
    """Everything the engines need to behave like a specific place."""

    key: str
    display_name: str
    country: str
    center: List[float]  # [lon, lat]
    bbox: List[float]  # [west, south, east, north]
    timezone: str
    rush_hours: List[List[int]]
    driving_style: Dict[str, float]
    signals: Dict[str, float]
    income_distribution: Dict[str, float]
    mode_split: Dict[str, float]
    aqi_baseline: Dict[str, float]
    cultural_calendar: List[Dict[str, Any]] = field(default_factory=list)
    policy_pack: Optional[str] = None
    gazetteer: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    generated: bool = False

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "RegionProfile":
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in raw.items() if k in known})

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _extract_candidates(prompt: str) -> List[str]:
    """Place-name candidates, most reliable first, capped for token efficiency."""
    cands: List[str] = []
    # Capitalized phrase after a locative preposition: "in New York", "near Cyber City".
    for m in re.finditer(
        r"\b(?:in|at|near|around|across|inside|for)\s+"
        r"((?:[A-Z][\w'&-]*)(?:\s+(?:of\s+)?[A-Z][\w'&-]*){0,3})",
        prompt,
    ):
        cands.append(m.group(1))
    # Lowercase fallback ("in new york"), filtered through stopwords.
    for m in re.finditer(r"\b(?:in|at|near|around)\s+([a-z][\w' -]{2,40})", prompt):
        tokens = [t for t in re.split(r"[^\w']+", m.group(1)) if t and t not in _STOPWORDS]
        if 1 <= len(tokens) <= 4:
            cands.append(" ".join(tokens[:4]))
    seen: set = set()
    unique = [c for c in cands if not (c.lower() in seen or seen.add(c.lower()))]
    return unique[:_MAX_GEOCODE_CANDIDATES]


class RegionResolver:
    """Resolves prompts to regions; generates + persists profiles for new places."""

    def __init__(
        self,
        regions_dir: Optional[Path] = None,
        geocode_fn: Optional[GeocodeFn] = None,
        llm_fn: Optional[LlmFn] = None,
    ):
        self.regions_dir = Path(regions_dir) if regions_dir else _REGIONS_DIR
        self._geocode: GeocodeFn = geocode_fn or _nominatim_geocode
        self._llm = llm_fn
        self.profiles: Dict[str, RegionProfile] = {}
        self._gazetteer: List[Tuple[str, str]] = []  # (term, key), longest first
        self._template: Dict[str, Any] = {}
        self._load()

    # ── loading ──

    def _load(self) -> None:
        paths = sorted(self.regions_dir.glob("*.json")) + sorted(
            self.regions_dir.glob("generated/*.json")
        )
        for path in paths:
            raw = json.loads(path.read_text())
            if path.name == _TEMPLATE_NAME:
                self._template = raw
                continue
            self._register(RegionProfile.from_dict(raw))
        if not self._template:
            raise FileNotFoundError(f"{self.regions_dir / _TEMPLATE_NAME} is required")
        if DEFAULT_REGION_KEY not in self.profiles:
            raise FileNotFoundError(
                f"default region '{DEFAULT_REGION_KEY}' missing from {self.regions_dir}"
            )

    def _register(self, profile: RegionProfile) -> None:
        self.profiles[profile.key] = profile
        terms = {t.lower() for t in profile.gazetteer} | {profile.key.replace("_", " ")}
        self._gazetteer.extend((t, profile.key) for t in terms)
        self._gazetteer.sort(key=lambda tk: -len(tk[0]))

    # ── resolution ──

    async def resolve(self, prompt: str) -> Tuple[RegionProfile, ScenarioConditions]:
        conditions = parse_conditions(prompt)
        low = prompt.lower()

        for term, key in self._gazetteer:
            if re.search(rf"\b{re.escape(term)}\b", low):
                return self.profiles[key], conditions

        for candidate in _extract_candidates(prompt):
            profile = await self._resolve_place(candidate)
            if profile:
                return profile, conditions

        if self._llm is not None:
            try:
                name = await self._llm(prompt)
            except Exception:  # gateway down ≠ resolution failure
                logger.warning("region LLM fallback failed", exc_info=True)
                name = None
            if name:
                profile = await self._resolve_place(name)
                if profile:
                    return profile, conditions

        return self.profiles[DEFAULT_REGION_KEY], conditions

    async def _resolve_place(self, name: str) -> Optional[RegionProfile]:
        slug = _slugify(name)
        if not slug:
            return None
        if slug in self.profiles:
            return self.profiles[slug]
        cached = self.regions_dir / "generated" / f"{slug}.json"
        if cached.exists():
            profile = RegionProfile.from_dict(json.loads(cached.read_text()))
            self._register(profile)
            return profile
        try:
            hits = await self._geocode(name)
        except Exception:
            logger.warning("geocode failed for %r", name, exc_info=True)
            return None
        hit = next((h for h in hits or [] if h.get("type") in _PLACE_TYPES), None)
        if hit is None:
            return None
        profile = self._build_generated(name, slug, hit)
        self._persist_generated(profile)
        self._register(profile)
        return profile

    # ── generated profiles ──

    def _build_generated(self, name: str, slug: str, hit: Dict[str, Any]) -> RegionProfile:
        base = copy.deepcopy(self._template)
        lat, lon = float(hit["lat"]), float(hit["lon"])
        country = str(hit.get("address", {}).get("country_code") or base["country"]).upper()
        # Indian places inherit NCR behavioral priors instead of generic ones.
        if country == "IN" and DEFAULT_REGION_KEY in self.profiles:
            ncr = self.profiles[DEFAULT_REGION_KEY]
            base.update(
                driving_style=dict(ncr.driving_style),
                income_distribution=dict(ncr.income_distribution),
                mode_split=dict(ncr.mode_split),
                aqi_baseline=dict(ncr.aqi_baseline),
                cultural_calendar=copy.deepcopy(ncr.cultural_calendar),
                rush_hours=[list(r) for r in ncr.rush_hours],
                timezone=ncr.timezone,
            )
        d_lat = 0.045  # ≈5 km half-height
        d_lon = 0.045 / max(math.cos(math.radians(lat)), 0.2)
        display = hit.get("display_name", "").split(",")[0].strip() or name.title()
        base.update(
            key=slug,
            display_name=display,
            country=country,
            center=[round(lon, 4), round(lat, 4)],
            bbox=[
                round(lon - d_lon, 4), round(lat - d_lat, 4),
                round(lon + d_lon, 4), round(lat + d_lat, 4),
            ],
            gazetteer=sorted({name.lower(), display.lower(), slug.replace("_", " ")}),
            sources=[f"generated from Nominatim hit: {hit.get('display_name', name)}"],
            generated=True,
        )
        return RegionProfile.from_dict(base)

    def _persist_generated(self, profile: RegionProfile) -> None:
        out_dir = self.regions_dir / "generated"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{profile.key}.json").write_text(
            json.dumps(profile.to_dict(), indent=2, ensure_ascii=False)
        )
