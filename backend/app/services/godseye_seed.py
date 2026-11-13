"""
Build a markdown situation brief from God's Eye View for use as a seed document.

The brief covers one area: recent headlines, natural hazards (earthquakes,
fires, tropical cyclones), current weather, and aggregate air and sea
traffic. It ends with an attribution section naming every data source used
and its licence or terms.

Only aggregate situational context is used. Cameras, licence-plate readers and
anything that identifies or follows a single aircraft or vessel are never
requested (see ``godseye_client.EXCLUDED_TOOLS``), and no callsign,
registration, MMSI or track appears in the output.

Place names are resolved with a bundled public-domain gazetteer derived from
Natural Earth (cities and countries), because God's Eye's own place search is
off unless its operator configures a Nominatim endpoint. When it is
configured, God's Eye resolves names the gazetteer does not know.
"""

from __future__ import annotations

import json
import math
import os
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Callable, Optional

from .godseye_client import (
    GodsEyeClient,
    GodsEyeError,
    GodsEyeUnavailable,
    ToolResult,
)

SECTION_KEYS = ("headlines", "hazards", "weather", "air", "sea")
SECTION_TITLES = {
    "headlines": "Headlines",
    "hazards": "Hazards",
    "weather": "Weather",
    "air": "Air traffic (aggregate)",
    "sea": "Sea traffic (aggregate)",
}
DEFAULT_RADIUS_KM = 100.0
MAX_RADIUS_KM = 2000.0
MAX_PLACE_LENGTH = 200
HEADLINE_LIMIT = 10
TOP_GROUPS = 6

GAZETTEER_PATH = os.path.join(os.path.dirname(__file__), "natural_earth_places.json")

# Every source the brief can draw on, with its licence or terms as God's Eye
# View documents them in DATA_SOURCES.md.
SOURCES: dict[str, dict[str, str]] = {
    "godseye": {
        "name": "God's Eye View",
        "used_for": "Retrieval of every live feed below",
        "terms": "Code under the MIT licence. The MIT grant does not extend to the "
                 "third-party data, which keeps its own terms as listed here.",
        "url": "https://github.com/bilawalsidhu/gods-eye-view",
    },
    "google_news": {
        "name": "Google News RSS",
        "used_for": "Headlines",
        "terms": "Google News Terms of Service: personal, non-commercial use only. "
                 "Linked articles remain the publishers' content under their own terms.",
        "url": "https://www.google.com/intl/en_us/terms_google_news.html",
    },
    "gdelt": {
        "name": "GDELT Project",
        "used_for": "Headlines",
        "terms": "GDELT Terms of Use: free for academic, commercial and governmental "
                 "use with citation of and a link to the GDELT Project. Linked articles "
                 "remain the publishers' content.",
        "url": "https://www.gdeltproject.org/about.html#termsofuse",
    },
    "usgs": {
        "name": "U.S. Geological Survey (USGS) earthquake feed",
        "used_for": "Earthquakes",
        "terms": "U.S. public domain. Data courtesy of the U.S. Geological Survey.",
        "url": "https://earthquake.usgs.gov/",
    },
    "firms": {
        "name": "NASA FIRMS",
        "used_for": "Active fires",
        "terms": "NASA open data (U.S. public domain). We acknowledge the use of data "
                 "from NASA's Fire Information for Resource Management System (FIRMS), "
                 "part of NASA's Earth Observing System Data and Information System (EOSDIS).",
        "url": "https://earthdata.nasa.gov/firms",
    },
    "nhc": {
        "name": "NOAA/NWS National Hurricane Center and Central Pacific Hurricane Center",
        "used_for": "Tropical cyclones",
        "terms": "NWS public data (U.S. public domain); no endorsement implied.",
        "url": "https://www.weather.gov/disclaimer",
    },
    "open_meteo": {
        "name": "Open-Meteo",
        "used_for": "Weather",
        "terms": "CC BY 4.0. Weather data by Open-Meteo.com.",
        "url": "https://open-meteo.com/en/licence",
    },
    "opensky": {
        "name": "OpenSky Network",
        "used_for": "Air traffic",
        "terms": "OpenSky Network terms: non-commercial research and education use. "
                 "Cite Schäfer et al., \"Bringing Up OpenSky\", IPSN 2014.",
        "url": "https://opensky-network.org/",
    },
    "adsb_lol": {
        "name": "adsb.lol",
        "used_for": "Air traffic",
        "terms": "Open Database License (ODbL 1.0).",
        "url": "https://adsb.lol/",
    },
    "aisstream": {
        "name": "AISStream.io",
        "used_for": "Sea traffic",
        "terms": "Free beta service without formal terms; AIS is a public broadcast.",
        "url": "https://aisstream.io/",
    },
    "natural_earth": {
        "name": "Natural Earth",
        "used_for": "Place names and areas",
        "terms": "Public domain. Made with Natural Earth.",
        "url": "https://www.naturalearthdata.com/about/terms-of-use/",
    },
    "openstreetmap": {
        "name": "OpenStreetMap (Nominatim)",
        "used_for": "Place names and areas",
        "terms": "Open Database License (ODbL 1.0). © OpenStreetMap contributors.",
        "url": "https://www.openstreetmap.org/copyright",
    },
}
_SOURCE_PATTERNS = [
    (re.compile(r"google news", re.I), "google_news"),
    (re.compile(r"gdelt", re.I), "gdelt"),
    (re.compile(r"opensky", re.I), "opensky"),
    (re.compile(r"adsb\.?lol", re.I), "adsb_lol"),
    (re.compile(r"aisstream", re.I), "aisstream"),
    (re.compile(r"usgs", re.I), "usgs"),
    (re.compile(r"firms", re.I), "firms"),
    (re.compile(r"nhc|cphc|hurricane", re.I), "nhc"),
    (re.compile(r"natural earth", re.I), "natural_earth"),
    (re.compile(r"openstreetmap|nominatim|\bosm\b", re.I), "openstreetmap"),
]


class AreaError(ValueError):
    """The area could not be understood or found."""

    def __init__(self, message: str, code: str = "invalid_area"):
        super().__init__(message)
        self.message = message
        self.code = code


@dataclass
class ResolvedArea:
    argument: dict          # God's Eye `area` argument
    label: str              # short name, e.g. "Taipei"
    description: str        # extent, e.g. "within 100 km of 25.036°N, 121.568°E"
    lat: Optional[float]    # centre, for headlines
    lon: Optional[float]
    method: str             # coordinates | bbox | gazetteer | godseye


# ---------------------------------------------------------------- places

def _normalize(name: str) -> str:
    text = unicodedata.normalize("NFKD", name)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[.,'’]", "", text.casefold())
    return re.sub(r"[\s\-_]+", " ", text).strip()


def _clean_label(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip()


_COUNTRY_ALIASES = {"uk": "GBR", "britain": "GBR", "great britain": "GBR", "america": "USA"}


@lru_cache(maxsize=1)
def _gazetteer() -> tuple[dict, dict]:
    with open(GAZETTEER_PATH, "r", encoding="utf-8") as fh:
        doc = json.load(fh)
    countries: dict[str, tuple[str, list]] = {}
    by_iso: dict[str, tuple[str, list]] = {}
    for names, iso3, iso2, box in doc["countries"]:
        entry = (_clean_label(names[0]), box)
        for name in names:
            countries.setdefault(_normalize(name), entry)
        for code in (iso3, iso2):
            if code and code != "-99":
                by_iso.setdefault(code.upper(), entry)
                countries.setdefault(_normalize(code), entry)
    for alias, iso3 in _COUNTRY_ALIASES.items():
        if iso3 in by_iso:
            countries.setdefault(alias, by_iso[iso3])
    places: dict[str, tuple[str, float, float, int]] = {}
    for name, lat, lon, rank in doc["places"]:
        key = _normalize(name)
        best = places.get(key)
        if best is None or rank > best[3]:
            places[key] = (_clean_label(name), lat, lon, rank)
    return countries, places


def _fmt_lat(lat: float) -> str:
    return f"{abs(lat):.3f}°{'N' if lat >= 0 else 'S'}"


def _fmt_lon(lon: float) -> str:
    return f"{abs(lon):.3f}°{'E' if lon >= 0 else 'W'}"


def _point_area(label: str, lat: float, lon: float, radius_km: float, method: str) -> ResolvedArea:
    return ResolvedArea(
        argument={"lat": lat, "lon": lon, "radius_km": radius_km},
        label=label,
        description=f"within {radius_km:g} km of {_fmt_lat(lat)}, {_fmt_lon(lon)}",
        lat=lat,
        lon=lon,
        method=method,
    )


def _bbox_area(label: str, box: list, method: str) -> ResolvedArea:
    west, south, east, north = (float(v) for v in box)
    centre_lon = (west + east) / 2 if west <= east else ((west + east + 360) / 2)
    if centre_lon > 180:
        centre_lon -= 360
    return ResolvedArea(
        argument={"bbox": [west, south, east, north]},
        label=label,
        description=(
            f"bounding box {_fmt_lon(west)} to {_fmt_lon(east)}, "
            f"{_fmt_lat(south)} to {_fmt_lat(north)}"
        ),
        lat=(south + north) / 2,
        lon=centre_lon,
        method=method,
    )


def _check_radius(value: Any) -> float:
    if value is None:
        return DEFAULT_RADIUS_KM
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise AreaError("radius_km must be a number.")
    if not 0.1 <= value <= MAX_RADIUS_KM:
        raise AreaError(f"radius_km must be between 0.1 and {MAX_RADIUS_KM:g}.")
    return float(value)


def _check_point(lat: Any, lon: Any) -> tuple[float, float]:
    for value in (lat, lon):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise AreaError("lat and lon must be numbers.")
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise AreaError("lat must be within ±90 and lon within ±180.")
    return float(lat), float(lon)


_COORDS = re.compile(
    r"^\s*(-?\d{1,3}(?:\.\d+)?)\s*[,;\s]\s*(-?\d{1,3}(?:\.\d+)?)"
    r"(?:\s*[,;\s]\s*(\d+(?:\.\d+)?)\s*(?:km)?)?\s*$",
    re.IGNORECASE,
)


def _lookup_gazetteer(name: str, radius_km: float) -> Optional[ResolvedArea]:
    countries, places = _gazetteer()
    candidates = [name]
    if "," in name:
        candidates.append(name.split(",", 1)[0])
    for candidate in candidates:
        key = _normalize(candidate)
        if not key:
            continue
        if key in countries:
            label, box = countries[key]
            return _bbox_area(label, box, "gazetteer")
        if key in places:
            label, lat, lon, _rank = places[key]
            return _point_area(label, lat, lon, radius_km, "gazetteer")
    return None


def resolve_area(area: Any, client: Optional[GodsEyeClient] = None) -> ResolvedArea:
    """Turn a place name, ``"lat, lon[, radius km]"`` or a God's Eye area dict into an area."""
    radius_km = DEFAULT_RADIUS_KM
    if isinstance(area, dict):
        given = [k for k in ("place", "bbox", "lat") if area.get(k) is not None]
        unknown = set(area) - {"place", "bbox", "lat", "lon", "radius_km"}
        if unknown:
            raise AreaError(f"Unknown area fields: {', '.join(sorted(unknown))}.")
        if len(given) != 1:
            raise AreaError("Give exactly one of place, bbox, or lat and lon.")
        radius_km = _check_radius(area.get("radius_km"))
        if "bbox" in given:
            box = area["bbox"]
            if (
                not isinstance(box, (list, tuple)) or len(box) != 4
                or any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in box)
            ):
                raise AreaError("bbox must be [west, south, east, north] in degrees.")
            west, south, east, north = box
            _check_point(south, west)
            _check_point(north, east)
            if south >= north:
                raise AreaError("bbox south must be below north.")
            return _bbox_area(
                f"{_fmt_lat(south)}–{_fmt_lat(north)}, {_fmt_lon(west)}–{_fmt_lon(east)}",
                box,
                "bbox",
            )
        if "lat" in given:
            lat, lon = _check_point(area.get("lat"), area.get("lon"))
            return _point_area(f"{lat:.4f}, {lon:.4f}", lat, lon, radius_km, "coordinates")
        area = area["place"]

    if not isinstance(area, str) or not area.strip():
        raise AreaError("Enter a place name or coordinates.")
    text = area.strip()
    if len(text) > MAX_PLACE_LENGTH:
        raise AreaError(f"Place names are limited to {MAX_PLACE_LENGTH} characters.")

    match = _COORDS.match(text)
    if match:
        lat, lon = _check_point(float(match.group(1)), float(match.group(2)))
        if match.group(3):
            radius_km = _check_radius(float(match.group(3)))
        return _point_area(f"{lat:.4f}, {lon:.4f}", lat, lon, radius_km, "coordinates")

    found = _lookup_gazetteer(text, radius_km)
    if found:
        return found

    if client is not None and client.geocode_configured():
        place = client.geocode(text)
        if place:
            return ResolvedArea(
                argument={"place": text},
                label=place["label"],
                description=f"as resolved by God's Eye View near {_fmt_lat(place['lat'])}, {_fmt_lon(place['lon'])}",
                lat=place["lat"],
                lon=place["lon"],
                method="godseye",
            )

    raise AreaError(
        f"Could not find a place called {text!r}. Try a major city or a country, "
        "or enter coordinates such as \"25.03, 121.56\".",
        code="area_not_found",
    )


# --------------------------------------------------------------- helpers

def _iso_minute(value: Any) -> Optional[str]:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _num(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def _fmt_int(value: Any) -> str:
    number = _num(value)
    return f"{number:,.0f}" if number is not None else "unknown"


_COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]


def _compass(degrees: Any) -> Optional[str]:
    number = _num(degrees)
    if number is None:
        return None
    return _COMPASS[int((number % 360) / 22.5 + 0.5) % 16]


def _md(text: Any) -> str:
    """Feed text made safe for one markdown line: no line breaks, links, HTML or emphasis."""
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    return re.sub(r"([\\`*_\[\]<>])", r"\\\1", value)


def _source_key(name: Any) -> Optional[str]:
    if not isinstance(name, str):
        return None
    for pattern, key in _SOURCE_PATTERNS:
        if pattern.search(name):
            return key
    return None


class _Sources:
    def __init__(self):
        self._used: dict[str, set[str]] = {}
        self._extra: dict[str, dict] = {}

    def use(self, key_or_name: Any, used_for: str) -> None:
        if not key_or_name:
            return
        key = key_or_name if key_or_name in SOURCES else _source_key(key_or_name)
        if key is None:
            name = str(key_or_name)
            key = f"other:{name}"
            self._extra.setdefault(key, {
                "name": name,
                "terms": "Terms as listed for this source in God's Eye View's DATA_SOURCES.md.",
                "url": "https://github.com/bilawalsidhu/gods-eye-view/blob/main/DATA_SOURCES.md",
            })
        self._used.setdefault(key, set()).add(used_for)

    def listing(self) -> list[dict]:
        out = []
        for key, used_for in self._used.items():
            base = SOURCES.get(key) or self._extra[key]
            out.append({
                "id": key,
                "name": base["name"],
                "used_for": ", ".join(sorted(used_for)) if key != "godseye" else base["used_for"],
                "terms": base["terms"],
                "url": base["url"],
            })
        return out


# -------------------------------------------------------------- collect

@dataclass
class _Outcome:
    ok: bool
    value: Any = None
    reason: Optional[str] = None


def _run(job: Callable[[], Any]) -> _Outcome:
    try:
        return _Outcome(True, job())
    except GodsEyeUnavailable as exc:
        if exc.code == "unreachable":
            raise
        return _Outcome(False, reason=exc.message)
    except GodsEyeError as exc:
        return _Outcome(False, reason=exc.message)


def _regional_job(client: GodsEyeClient, area: ResolvedArea, offered: set[str]) -> Callable[[], dict]:
    def job() -> dict:
        if area.lat is None or area.lon is None:
            raise GodsEyeError("No centre point for headlines.")
        if "get_regional_brief" in offered:
            data = client.call_tool(
                "get_regional_brief", {"location": {"lat": area.lat, "lon": area.lon}}
            ).data
            return {
                "place": (data.get("place") or {}).get("label"),
                "place_source": None,
                "news_source": data.get("news_source"),
                "window_hours": None,
                "articles": [
                    {"title": a.get("title"), "source": a.get("source"), "published_at": a.get("published_at")}
                    for a in data.get("articles") or [] if isinstance(a, dict)
                ],
            }
        # God's Eye leaves get_regional_brief off its MCP surface, so read the
        # same data from the route behind that tool.
        data = client.regional_brief(area.lat, area.lon)
        place = data.get("place") or {}
        return {
            "place": place.get("label"),
            "place_source": place.get("source"),
            "news_source": data.get("newsSource") if data.get("newsStatus", "ready") == "ready" else None,
            "window_hours": data.get("newsWindowHours"),
            "articles": [
                {"title": a.get("title"), "source": a.get("domain"), "published_at": a.get("publishedAt")}
                for a in data.get("articles") or [] if isinstance(a, dict)
            ],
        }
    return job


def _collect(client: GodsEyeClient, area: ResolvedArea, sections: list[str]) -> dict[str, _Outcome]:
    offered = {t.get("name") for t in client.list_tools()}
    jobs: dict[str, Callable[[], Any]] = {}

    def tool(name: str, args: dict) -> Callable[[], ToolResult]:
        def job() -> ToolResult:
            if name not in offered:
                raise GodsEyeError(f"This God's Eye View does not offer {name}.", code="missing_tool")
            return client.call_tool(name, args)
        return job

    where = {"area": area.argument}
    if "hazards" in sections or "weather" in sections:
        jobs["situation"] = tool("situation_brief", where)
    if "air" in sections:
        jobs["aircraft"] = tool("aircraft_in_area", {**where, "group_by": "origin_country", "stats": True, "limit": 1})
        jobs["military"] = tool("aircraft_in_area", {**where, "military": True, "limit": 1})
    if "sea" in sections:
        jobs["vessels"] = tool("vessels_in_area", {**where, "group_by": "type", "stats": True, "limit": 1})
    if "headlines" in sections:
        jobs["regional"] = _regional_job(client, area, offered)

    with ThreadPoolExecutor(max_workers=max(1, len(jobs))) as pool:
        futures = {key: pool.submit(_run, job) for key, job in jobs.items()}
        return {key: future.result() for key, future in futures.items()}


# -------------------------------------------------------------- sections

def _unavailable(reason: Optional[str]) -> dict:
    return {"status": "unavailable", "reason": reason or "unavailable right now"}


def _situation_part(outcomes: dict, key: str) -> tuple[Optional[dict], Optional[str]]:
    """One section of situation_brief: (answer, reason it is missing)."""
    situation = outcomes.get("situation")
    if situation is None:
        return None, "not requested"
    if not situation.ok:
        return None, situation.reason
    part = (situation.value.data.get("sections") or {}).get(key)
    if not isinstance(part, dict):
        return None, "not reported"
    if part.get("unavailable"):
        return None, part.get("reason") or "unavailable right now"
    return part, None


def _headlines(outcomes: dict, sources: _Sources) -> tuple[dict, list[str]]:
    outcome = outcomes["regional"]
    if not outcome.ok:
        return _unavailable(outcome.reason), ["Headlines could not be retrieved for this area."]
    value = outcome.value
    if value.get("place_source"):
        sources.use(value["place_source"], "Region name")
    articles = []
    for article in value["articles"][:HEADLINE_LIMIT]:
        title = (article.get("title") or "").strip()
        source = (article.get("source") or "").strip()
        if not title:
            continue
        if source and title.endswith(f" - {source}"):
            title = title[: -len(f" - {source}")].rstrip()
        articles.append({"title": title, "source": source or None,
                         "published_at": article.get("published_at")})
    region = value.get("place")
    news_source = value.get("news_source")
    section = {"status": "ok" if articles else "empty", "region": region,
               "source": news_source, "count": len(articles), "items": articles}
    if not articles:
        return section, [f"No recent headlines were found for {_md(region or 'this area')}."]
    sources.use(news_source or "Google News RSS", "Headlines")
    window = value.get("window_hours")
    intro = f"Recent headlines for {_md(region or 'the area')}"
    intro += f" (last {window:g} hours)" if _num(window) else ""
    lines = [intro + ":", ""]
    for index, article in enumerate(articles, 1):
        meta = [m for m in (_md(article["source"]) if article["source"] else None,
                            _iso_minute(article["published_at"])) if m]
        lines.append(f"{index}. {_md(article['title'])}" + (f" ({'; '.join(meta)})" if meta else ""))
    return section, lines


def _earthquakes(outcomes: dict, sources: _Sources) -> tuple[dict, list[str]]:
    part, reason = _situation_part(outcomes, "earthquakes")
    if part is None:
        return _unavailable(reason), ["Earthquake data was not available for this brief."]
    data = part.get("data") or {}
    rows = [r for r in data.get("rows") or [] if isinstance(r, dict)]
    total = int(_num(data.get("total")) or len(rows))
    sources.use("usgs", "Earthquakes")
    items = [{"magnitude": r.get("magnitude"), "place": r.get("place"),
              "time": r.get("time"), "depth_km": r.get("depth_km")} for r in rows]
    section = {"status": "ok" if total else "empty", "total": total, "items": items}
    if not total:
        return section, ["No earthquakes of magnitude 2.5 or more in the last 24 hours."]
    lines = [f"{total} earthquake{'s' if total != 1 else ''} of magnitude 2.5 or more in the last 24 hours"
             + (f"; the {len(items)} largest:" if total > len(items) else ":")]
    for item in items:
        bits = [f"M{_num(item['magnitude']):.1f}" if _num(item["magnitude"]) is not None else "M?"]
        if item["place"]:
            bits.append(_md(item["place"]))
        when = _iso_minute(item["time"])
        if when:
            bits.append(when)
        if _num(item["depth_km"]) is not None:
            bits.append(f"depth {_num(item['depth_km']):.0f} km")
        lines.append("- " + ", ".join(bits))
    return section, lines


def _fires(outcomes: dict, sources: _Sources) -> tuple[dict, list[str]]:
    part, reason = _situation_part(outcomes, "fires")
    if part is None:
        return _unavailable(reason), ["Satellite fire detections were not available for this brief."]
    data = part.get("data") or {}
    rows = [r for r in data.get("rows") or [] if isinstance(r, dict)]
    total = int(_num(data.get("total")) or len(rows))
    sources.use("firms", "Active fires")
    frps = [_num(r.get("frp_mw")) for r in rows if _num(r.get("frp_mw")) is not None]
    section = {"status": "ok" if total else "empty", "total": total,
               "max_frp_mw": max(frps) if frps else None,
               "high_confidence_in_sample": sum(1 for r in rows if r.get("confidence") == "high")}
    if not total:
        return section, ["No satellite fire detections in the last 24 hours."]
    line = f"{total} satellite fire detection{'s' if total != 1 else ''} in the last 24 hours"
    if frps:
        line += f"; the strongest at {max(frps):.0f} MW fire radiative power"
    return section, [line + "."]


def _cyclones(outcomes: dict, sources: _Sources) -> tuple[dict, list[str]]:
    part, reason = _situation_part(outcomes, "cyclones")
    if part is None:
        return _unavailable(reason), ["Tropical cyclone advisories were not available for this brief."]
    data = part.get("data") or {}
    storms = [s for s in data.get("storms") or [] if isinstance(s, dict)]
    sources.use("nhc", "Tropical cyclones")
    coverage = data.get("coverage")
    items = [{"name": s.get("name"), "classification": s.get("classification")} for s in storms]
    section = {"status": "ok" if storms else "empty", "total": len(storms),
               "items": items, "coverage": coverage}
    note = f" Advisory coverage: {_md(coverage)}" if coverage else ""
    if not storms:
        return section, [f"No active tropical cyclones in the area.{note}"]
    lines = [f"{len(storms)} active tropical cyclone{'s' if len(storms) != 1 else ''}:"]
    for storm in items:
        lines.append(f"- {_md(storm['name'] or 'Unnamed')}"
                     + (f" ({_md(storm['classification'])})" if storm["classification"] else ""))
    if note:
        lines.append(note.strip())
    return section, lines


def _hazards(outcomes: dict, sources: _Sources) -> tuple[dict, list[str]]:
    quakes, quake_lines = _earthquakes(outcomes, sources)
    fires, fire_lines = _fires(outcomes, sources)
    storms, storm_lines = _cyclones(outcomes, sources)
    parts = [quakes, fires, storms]
    if all(p["status"] == "unavailable" for p in parts):
        status = "unavailable"
    elif any(p["status"] == "ok" for p in parts):
        status = "ok"
    else:
        status = "empty"
    section = {"status": status, "earthquakes": quakes, "fires": fires, "cyclones": storms}
    lines = (["### Earthquakes", ""] + quake_lines
             + ["", "### Active fires", ""] + fire_lines
             + ["", "### Tropical cyclones", ""] + storm_lines)
    return section, lines


def _weather(outcomes: dict, sources: _Sources) -> tuple[dict, list[str]]:
    part, reason = _situation_part(outcomes, "weather")
    weather = ((part or {}).get("data") or {}).get("weather") if part else None
    if not isinstance(weather, dict):
        return _unavailable(reason or "not reported"), ["Current weather was not available for this brief."]
    sources.use("open_meteo", "Weather")
    section = {
        "status": "ok",
        "conditions": weather.get("conditions"),
        "temperature_c": weather.get("temperature_c"),
        "feels_like_c": weather.get("feels_like_c"),
        "precipitation_mm": weather.get("precipitation_mm"),
        "cloud_cover_pct": weather.get("cloud_cover_pct"),
        "wind_kph": weather.get("wind_kph"),
        "wind_direction_deg": weather.get("wind_direction_deg"),
        "visibility_m": weather.get("visibility_m"),
        "observed_at": weather.get("observed_at"),
    }
    lines = []
    if section["conditions"]:
        lines.append(f"- Conditions: {_md(section['conditions'])}")
    temp, feels = _num(section["temperature_c"]), _num(section["feels_like_c"])
    if temp is not None:
        lines.append(f"- Temperature: {temp:.1f} °C" + (f" (feels like {feels:.1f} °C)" if feels is not None else ""))
    wind = _num(section["wind_kph"])
    if wind is not None:
        direction = _compass(section["wind_direction_deg"])
        lines.append(f"- Wind: {wind:.0f} km/h" + (f" from the {direction}" if direction else ""))
    extras = []
    if _num(section["precipitation_mm"]) is not None:
        extras.append(f"precipitation {_num(section['precipitation_mm']):g} mm")
    if _num(section["cloud_cover_pct"]) is not None:
        extras.append(f"cloud cover {_num(section['cloud_cover_pct']):.0f}%")
    if _num(section["visibility_m"]) is not None:
        extras.append(f"visibility {_num(section['visibility_m']) / 1000:.0f} km")
    if extras:
        lines.append("- " + "; ".join(extras).capitalize())
    when = _iso_minute(section["observed_at"])
    if when:
        lines.append(f"- Observed: {when}")
    return section, lines or ["Current weather was not available for this brief."]


def _groups(breakdown: Any) -> list[dict]:
    if not isinstance(breakdown, dict):
        return []
    return [
        {"value": g.get("value"), "count": g.get("count")}
        for g in breakdown.get("groups") or []
        if isinstance(g, dict) and g.get("value") not in (None, "")
    ][:TOP_GROUPS]


def _air(outcomes: dict, sources: _Sources) -> tuple[dict, list[str]]:
    outcome = outcomes["aircraft"]
    if not outcome.ok:
        return _unavailable(outcome.reason), ["Aircraft positions were not available for this brief."]
    data = outcome.value.data
    total = int(_num(data.get("total")) or 0)
    stats = data.get("stats") or {}
    altitude, speed = stats.get("altitude_m") or {}, stats.get("speed_mps") or {}
    airborne = int(_num(altitude.get("count")) or 0)
    countries = _groups(data.get("breakdown"))
    sources.use(data.get("source") or "OpenSky Network", "Air traffic")
    military = outcomes.get("military")
    military_total = None
    if military is not None and military.ok:
        military_total = int(_num(military.value.data.get("total")) or 0)
        sources.use(military.value.data.get("source") or "adsb.lol", "Air traffic")
    section = {
        "status": "ok" if total else "empty",
        "total": total,
        "airborne": airborne,
        "on_ground": max(0, total - airborne) if altitude else None,
        "median_altitude_m": _num(altitude.get("median")),
        "max_altitude_m": _num(altitude.get("max")),
        "median_speed_kmh": round(_num(speed.get("median")) * 3.6) if _num(speed.get("median")) is not None else None,
        "registration_countries": countries,
        "military_total": military_total,
        "feed": data.get("source"),
        "coverage": data.get("coverage"),
        "observed_at": data.get("observed_at"),
        "freshness": data.get("freshness"),
    }
    lines = [f"- Aircraft reported in the area: {_fmt_int(total)}"
             + (f" ({airborne} airborne, {section['on_ground']} on the ground)" if altitude else "")]
    if section["median_altitude_m"] is not None:
        lines.append(
            f"- Airborne altitude: median {_fmt_int(section['median_altitude_m'])} m, "
            f"highest {_fmt_int(section['max_altitude_m'])} m"
            + (f"; median ground speed {section['median_speed_kmh']} km/h"
               if section["median_speed_kmh"] is not None else "")
        )
    if countries:
        lines.append("- Countries of registration: "
                     + ", ".join(f"{_md(g['value'])} {g['count']}" for g in countries))
    if military_total is not None:
        feed = military.value.data.get("source")
        lines.append(f"- Military aircraft in the area: {military_total}"
                     + (f" (from the {_md(feed)} military feed)" if feed else ""))
    feed_bits = [b for b in (_md(data.get("source")) if data.get("source") else None,
                             _md(data.get("coverage")) if data.get("coverage") else None) if b]
    when = _iso_minute(data.get("observed_at"))
    if feed_bits or when:
        lines.append("- Feed: " + ", ".join(feed_bits) + (f"; observed {when}" if when else ""))
    if data.get("freshness") == "stale":
        lines.append("- Note: the aircraft feed reported stale data.")
    lines.append("")
    lines.append("Counts only: individual aircraft identities and tracks are deliberately left out.")
    return section, lines


def _sea(outcomes: dict, sources: _Sources) -> tuple[dict, list[str]]:
    outcome = outcomes["vessels"]
    if not outcome.ok:
        return _unavailable(outcome.reason), ["Live ship positions (AIS) were not available for this brief."]
    data = outcome.value.data
    total = int(_num(data.get("total")) or 0)
    speed = (data.get("stats") or {}).get("speed_mps") or {}
    types = _groups(data.get("breakdown"))
    sources.use(data.get("source") or "AISStream.io", "Sea traffic")
    section = {
        "status": "ok" if total else "empty",
        "total": total,
        "types": types,
        "median_speed_kmh": round(_num(speed.get("median")) * 3.6) if _num(speed.get("median")) is not None else None,
        "feed": data.get("source"),
        "observed_at": data.get("observed_at"),
        "freshness": data.get("freshness"),
    }
    lines = [f"- Ships reported in the area: {_fmt_int(total)}"]
    if types:
        lines.append("- By type: " + ", ".join(f"{_md(g['value'])} {g['count']}" for g in types))
    if section["median_speed_kmh"] is not None:
        lines.append(f"- Median speed: {section['median_speed_kmh']} km/h")
    when = _iso_minute(data.get("observed_at"))
    if data.get("source") or when:
        lines.append("- Feed: " + (_md(data.get("source")) if data.get("source") else "AIS")
                     + (f"; observed {when}" if when else ""))
    lines.append("")
    lines.append("Counts only: individual vessel identities and tracks are deliberately left out.")
    return section, lines


_BUILDERS = {
    "headlines": _headlines,
    "hazards": _hazards,
    "weather": _weather,
    "air": _air,
    "sea": _sea,
}


# ------------------------------------------------------------------ main

def normalize_sections(sections: Any) -> list[str]:
    """Validate the requested sections, keeping the canonical order."""
    if sections is None:
        return list(SECTION_KEYS)
    if isinstance(sections, str):
        sections = [s for s in re.split(r"[,\s]+", sections) if s]
    if not isinstance(sections, (list, tuple)) or not sections:
        raise AreaError(f"sections must be a non-empty list drawn from: {', '.join(SECTION_KEYS)}.",
                        code="invalid_sections")
    unknown = [s for s in sections if s not in SECTION_KEYS]
    if unknown:
        raise AreaError(
            f"Unknown sections: {', '.join(map(str, unknown))}. Use: {', '.join(SECTION_KEYS)}.",
            code="invalid_sections",
        )
    return [key for key in SECTION_KEYS if key in sections]


def build_brief(
    client: GodsEyeClient,
    area: Any,
    sections: Any = None,
    *,
    now: Optional[datetime] = None,
) -> dict:
    """Fetch God's Eye data for an area and render the seed brief.

    Returns ``{markdown, sections, fetched_at, sources, area}``.
    """
    wanted = normalize_sections(sections)
    client.list_tools()  # handshake first; raises GodsEyeUnavailable when down
    resolved = resolve_area(area, client)
    outcomes = _collect(client, resolved, wanted)
    fetched = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    fetched_at = fetched.strftime("%Y-%m-%dT%H:%M:%SZ")

    sources = _Sources()
    sources.use("godseye", "Retrieval")
    if resolved.method == "gazetteer":
        sources.use("natural_earth", "Place names and areas")
    elif resolved.method == "godseye":
        sources.use("openstreetmap", "Place names and areas")

    rendered: dict[str, dict] = {}
    body: list[str] = []
    for key in wanted:
        section, lines = _BUILDERS[key](outcomes, sources)
        section["title"] = SECTION_TITLES[key]
        rendered[key] = section
        body += [f"## {SECTION_TITLES[key]}", ""] + lines + [""]

    server = client.server_info
    version = server.get("version")
    header = [
        f"# Situation brief: {_md(resolved.label)}",
        "",
        f"- Area: {_md(resolved.label)}, {_md(resolved.description)}",
        f"- Fetched: {fetched.strftime('%Y-%m-%d %H:%M:%S')} UTC",
        f"- Retrieved through: God's Eye View{f' {_md(version)}' if version else ''} (live public data feeds)",
        "",
        "This is a snapshot of public open data, aggregated for scenario seeding. Figures are what "
        "the feeds reported at fetch time. Where a feed was not available, it could not be read; "
        "that does not mean nothing is happening.",
        "",
    ]
    listing = sources.listing()
    footer = [
        "---",
        "",
        "## Sources and terms",
        "",
        "Each data source keeps its own licence or terms; check them before reusing this document.",
        "",
    ]
    for source in listing:
        footer.append(
            f"- **{_md(source['name'])}** ({_md(source['used_for'])}): "
            f"{_md(source['terms'])} <{source['url']}>"
        )
    markdown = "\n".join(header + body + footer).rstrip() + "\n"
    return {
        "markdown": markdown,
        "sections": rendered,
        "fetched_at": fetched_at,
        "sources": listing,
        "area": {
            "label": resolved.label,
            "description": resolved.description,
            "argument": resolved.argument,
            "lat": resolved.lat,
            "lon": resolved.lon,
            "resolved_by": resolved.method,
        },
    }


def suggested_filename(label: str, fetched_at: str) -> str:
    """A safe ``.md`` file name for a brief, e.g. ``godseye-taipei-20261113T1530Z.md``."""
    text = unicodedata.normalize("NFKD", label or "area")
    slug = re.sub(r"[^a-z0-9]+", "-", text.encode("ascii", "ignore").decode().lower()).strip("-")[:40] or "area"
    stamp = re.sub(r"[^0-9T]", "", fetched_at)[:13]
    return f"godseye-{slug}-{stamp}Z.md"
