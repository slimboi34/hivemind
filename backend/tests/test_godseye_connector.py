"""God's Eye View connector: MCP client, seed brief builder and API routes.

All HTTP is mocked with httpx.MockTransport; nothing here needs a running
God's Eye View.
"""

import json
from datetime import datetime, timezone

import httpx
import pytest

from app import create_app
from app.api import godseye as godseye_api
from app.services import godseye_seed
from app.services.godseye_client import (
    EXCLUDED_TOOLS,
    GodsEyeClient,
    GodsEyeError,
    GodsEyeExcludedTool,
    GodsEyeToolError,
    GodsEyeUnavailable,
    is_excluded_tool,
)
from app.services.godseye_seed import AreaError, build_brief, resolve_area

BASE = "http://localhost:4173"
FIXED_NOW = datetime(2026, 11, 13, 15, 30, 0, tzinfo=timezone.utc)

SURVEILLANCE_TOOLS = [
    "find_cctv_cameras", "get_cctv_snapshot", "find_alpr_cameras",
    "find_aircraft", "get_aircraft_track", "get_aircraft_info",
    "find_vessel", "get_vessel_track", "military_awareness",
]
SITUATION_TOOLS = [
    "get_earthquakes", "get_active_fires", "aircraft_in_area", "vessels_in_area",
    "get_cyclones", "situation_brief", "show_in_gods_eye_view",
]


def _tool_result(summary, data, is_error=False):
    return {
        "content": [{"type": "text", "text": summary}, {"type": "text", "text": json.dumps(data)}],
        "structuredContent": data,
        "isError": is_error,
    }


def _situation_brief():
    return _tool_result(
        "Situation in Taipei: ...",
        {
            "area": "Taipei",
            "sections": {
                "weather": {
                    "summary": "Weather at Taipei: overcast, 22°C.",
                    "data": {"weather": {
                        "observed_at": "2026-11-13T15:15:00.000Z", "conditions": "overcast",
                        "temperature_c": 22.1, "feels_like_c": 25.2, "precipitation_mm": 0,
                        "cloud_cover_pct": 96, "wind_kph": 3.1, "wind_direction_deg": 103,
                        "visibility_m": 21960,
                    }},
                },
                "earthquakes": {
                    "summary": "2 earthquakes.",
                    "data": {"total": 2, "returned": 2, "truncated": False, "rows": [
                        {"id": "us7000aaaa", "magnitude": 4.6, "place": "30 km E of Hualien City, Taiwan",
                         "time": "2026-11-13T09:01:00.000Z", "lat": 24.0, "lon": 121.9, "depth_km": 18},
                        {"id": "us7000bbbb", "magnitude": 3.1, "place": "Taiwan region",
                         "time": "2026-11-13T04:00:00.000Z", "lat": 24.5, "lon": 121.8, "depth_km": 9},
                    ]},
                },
                "fires": {"unavailable": True,
                          "reason": "Fire detections need a NASA FIRMS key configured for this server"},
                "aircraft": {"summary": "18 aircraft.", "data": {"total": 18, "rows": [
                    {"id": "7583ed", "callsign": "PAL895", "registration": "RP-C1234"}]}},
                "vessels": {"unavailable": True, "reason": "AISSTREAM_API_KEY not set"},
                "cyclones": {"summary": "0 cyclones.", "data": {
                    "storms": [], "coverage": "Atlantic and eastern/central North Pacific",
                    "source": "NOAA NHC / CPHC"}},
            },
        },
    )


def _aircraft(args):
    if args.get("military"):
        return _tool_result("1 military aircraft.", {
            "total": 1, "returned": 1, "truncated": False,
            "rows": [{"id": "ae1234", "callsign": "RCH123", "registration": "05-5140"}],
            "source": "adsb.lol", "coverage": "military upstream snapshot",
            "observed_at": "2026-11-13T15:29:00.000Z", "freshness": "current",
        })
    return _tool_result("18 aircraft in Taipei.", {
        "total": 18, "returned": 1, "truncated": True,
        "rows": [{"id": "89909d", "callsign": "EVA195", "lat": 25.25, "lon": 121.46,
                  "registration": "B-16701", "on_ground": False}],
        "breakdown": {"field": "origin_country", "groups": [
            {"value": "Taiwan", "count": 8}, {"value": "Republic of Korea", "count": 5},
            {"value": "Japan", "count": 2}], "other_count": 0, "unknown_count": 3},
        "stats": {"altitude_m": {"count": 12, "min": 8, "median": 3569.5, "mean": 5099.7, "max": 10980},
                  "speed_mps": {"count": 12, "min": 76.2, "median": 160.7, "mean": 159.7, "max": 213.4}},
        "source": "OpenSky Network", "coverage": "worldwide upstream snapshot",
        "observed_at": "2026-11-13T15:28:00.000Z", "freshness": "current",
    })


REGIONAL = {
    "status": "ready",
    "place": {"label": "Taiwan", "source": "Natural Earth", "kind": "natural"},
    "newsStatus": "ready", "newsSource": "Google News RSS", "newsWindowHours": 24,
    "articles": [
        {"title": "Typhoon season ends quietly - Taipei Times", "domain": "Taipei Times",
         "url": "https://news.google.com/rss/articles/abc", "publishedAt": "2026-11-13T14:00:00.000Z"},
        {"title": "Chip exports *surge* [report]", "domain": "Focus Taiwan",
         "url": "https://news.google.com/rss/articles/def", "publishedAt": "2026-11-13T12:30:00.000Z"},
    ],
}


class FakeGodsEye:
    """A scripted God's Eye View: /mcp JSON-RPC plus the two plain routes."""

    def __init__(self, tools=None, geocode_configured=False, overrides=None):
        self.tools = tools if tools is not None else SITUATION_TOOLS + SURVEILLANCE_TOOLS
        self.geocode_configured = geocode_configured
        self.overrides = overrides or {}
        self.rpc = []        # every JSON-RPC message received
        self.requests = []   # every httpx.Request received

    @property
    def tool_calls(self):
        return [(m["params"]["name"], m["params"]["arguments"])
                for m in self.rpc if m.get("method") == "tools/call"]

    def transport(self):
        return httpx.MockTransport(self.handle)

    def client(self, **kwargs):
        return GodsEyeClient(BASE, transport=self.transport(), **kwargs)

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.path == "/mcp":
            message = json.loads(request.content)
            self.rpc.append(message)
            if "id" not in message:
                return httpx.Response(202)
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": message["id"], **self.answer(message)})
        if request.url.path == "/api/regional-brief":
            assert request.url.params["latitude"] and request.url.params["longitude"]
            return httpx.Response(200, json=REGIONAL)
        if request.url.path == "/api/geocode/status":
            return httpx.Response(200, json={"configured": self.geocode_configured})
        if request.url.path == "/api/geocode":
            return httpx.Response(200, json={"status": "ready", "results": [{
                "formatted_address": "Hualien City, Taiwan",
                "geometry": {"location": {"lat": 23.98, "lng": 121.6}},
            }]})
        return httpx.Response(404, json={"error": "Not Found"})

    def answer(self, message):
        method, params = message["method"], message.get("params") or {}
        if method == "initialize":
            return {"result": {
                "protocolVersion": params.get("protocolVersion", "2025-06-18"),
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "gods-eye-view", "version": "0.3.0"},
            }}
        if method == "tools/list":
            return {"result": {"tools": [{"name": n, "inputSchema": {"type": "object"}} for n in self.tools]}}
        if method == "tools/call":
            name, args = params["name"], params.get("arguments") or {}
            if name not in self.tools:
                return {"error": {"code": -32602, "message": f"Unknown tool: {name}"}}
            if name in self.overrides:
                return {"result": self.overrides[name](args)}
            if name == "situation_brief":
                return {"result": _situation_brief()}
            if name == "aircraft_in_area":
                return {"result": _aircraft(args)}
            if name == "vessels_in_area":
                return {"result": _tool_result("The tool failed", {"error": "unavailable"}, is_error=True)}
            if name == "get_regional_brief":
                return {"result": _tool_result("Taiwan: overcast; 1 recent headline.", {
                    "place": {"label": "Taiwan (via MCP)"}, "news_source": "Google News RSS",
                    "articles": [{"title": "MCP headline", "source": "CNA",
                                  "published_at": "2026-11-13T10:00:00.000Z"}],
                })}
            return {"result": _tool_result(f"{name} ok", {"total": 0, "rows": []})}
        return {"error": {"code": -32601, "message": f"Method not found: {method}"}}


def _failing_transport(exc):
    def handler(request):
        raise exc
    return httpx.MockTransport(handler)


# ------------------------------------------------------------------ client

def test_client_speaks_mcp_json_rpc_over_http():
    fake = FakeGodsEye()
    with fake.client() as client:
        init = client.initialize()
        tools = client.list_tools()

    assert init["serverInfo"] == {"name": "gods-eye-view", "version": "0.3.0"}
    methods = [m["method"] for m in fake.rpc]
    assert methods == ["initialize", "notifications/initialized", "tools/list"]
    first = fake.rpc[0]
    assert first["jsonrpc"] == "2.0" and isinstance(first["id"], int)
    assert first["params"]["clientInfo"]["name"] == "hivemind"
    assert first["params"]["protocolVersion"] == "2025-06-18"
    ids = [m["id"] for m in fake.rpc if "id" in m]
    assert len(set(ids)) == len(ids)

    mcp_requests = [r for r in fake.requests if r.url.path == "/mcp"]
    assert all(r.method == "POST" for r in mcp_requests)
    assert all("application/json" in r.headers["accept"] and "text/event-stream" in r.headers["accept"]
               for r in mcp_requests)
    assert mcp_requests[-1].headers["mcp-protocol-version"] == "2025-06-18"

    names = [t["name"] for t in tools]
    assert "situation_brief" in names
    assert not set(names) & set(SURVEILLANCE_TOOLS)


def test_call_tool_returns_summary_and_structured_data():
    fake = FakeGodsEye()
    with fake.client() as client:
        result = client.call_tool("aircraft_in_area", {"area": {"place": "Taipei"}, "limit": 1})
    assert result.summary == "18 aircraft in Taipei."
    assert result.data["total"] == 18
    assert fake.tool_calls == [("aircraft_in_area", {"area": {"place": "Taipei"}, "limit": 1})]


def test_call_tool_reads_data_from_text_when_structured_content_is_missing():
    def no_structured(args):
        return {"content": [{"type": "text", "text": "ok"}, {"type": "text", "text": '{"total": 7}'}]}

    fake = FakeGodsEye(overrides={"get_earthquakes": no_structured})
    with fake.client() as client:
        assert client.call_tool("get_earthquakes", {}).data == {"total": 7}


def test_tool_error_and_rpc_error_raise():
    fake = FakeGodsEye()
    with fake.client() as client:
        with pytest.raises(GodsEyeToolError) as tool_error:
            client.call_tool("vessels_in_area", {"area": {"place": "Taipei"}})
        assert tool_error.value.detail == "unavailable"
        with pytest.raises(GodsEyeError) as rpc_error:
            client.call_tool("get_regional_brief", {"location": {"lat": 1, "lon": 2}})
    assert rpc_error.value.code == "rpc"
    assert "Unknown tool" in rpc_error.value.message


def test_event_stream_replies_are_parsed():
    def handler(request):
        message = json.loads(request.content)
        if "id" not in message:
            return httpx.Response(202)
        body = "event: message\ndata: " + json.dumps({
            "jsonrpc": "2.0", "id": message["id"],
            "result": {"protocolVersion": "2025-06-18", "serverInfo": {"name": "gods-eye-view", "version": "9"}},
        }) + "\n\n"
        return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

    with GodsEyeClient(BASE, transport=httpx.MockTransport(handler)) as client:
        assert client.server_info["version"] == "9"


def test_surveillance_tools_are_refused_without_a_request():
    fake = FakeGodsEye()
    with fake.client() as client:
        for name in sorted(EXCLUDED_TOOLS) + ["get_alpr_hits", "find_cameras_nearby", "get_ship_track"]:
            with pytest.raises(GodsEyeExcludedTool):
                client.call_tool(name, {})
    assert fake.rpc == []
    assert is_excluded_tool("find_cctv_cameras") and not is_excluded_tool("aircraft_in_area")


def test_unreachable_server_gives_a_clear_error():
    client = GodsEyeClient(BASE, transport=_failing_transport(httpx.ConnectError("Connection refused")))
    with pytest.raises(GodsEyeUnavailable) as err:
        client.initialize()
    assert err.value.code == "unreachable"
    assert BASE in err.value.message and "npm run dev" in err.value.message

    status = client.status()
    assert status["reachable"] is False and status["error_code"] == "unreachable"


def test_timeout_is_reported_as_unavailable():
    client = GodsEyeClient(BASE, transport=_failing_transport(httpx.ReadTimeout("slow")))
    with pytest.raises(GodsEyeUnavailable) as err:
        client.list_tools()
    assert err.value.code == "timeout"


def test_forbidden_and_missing_endpoint_are_explained():
    forbidden = GodsEyeClient(BASE, transport=httpx.MockTransport(lambda r: httpx.Response(403, json={})))
    with pytest.raises(GodsEyeError) as err:
        forbidden.initialize()
    assert err.value.code == "forbidden" and "local requests" in err.value.message

    missing = GodsEyeClient(BASE, transport=httpx.MockTransport(lambda r: httpx.Response(404, text="nope")))
    with pytest.raises(GodsEyeError) as err:
        missing.initialize()
    assert err.value.code == "no_mcp"


def test_status_reports_version_and_usable_tools():
    fake = FakeGodsEye()
    with fake.client() as client:
        status = client.status()
    assert status["reachable"] is True
    assert status["version"] == "0.3.0"
    assert "situation_brief" in status["tools"]
    assert set(status["excluded_tools"]) == set(SURVEILLANCE_TOOLS)
    assert status["place_search"] is False


# -------------------------------------------------------------------- area

def test_resolve_area_from_names_coordinates_and_boxes():
    city = resolve_area("Taipei")
    assert city.method == "gazetteer"
    assert city.argument["radius_km"] == godseye_seed.DEFAULT_RADIUS_KM
    assert abs(city.lat - 25.04) < 0.1 and abs(city.lon - 121.57) < 0.1

    assert resolve_area("sao paulo").label == "São Paulo"
    assert resolve_area("Johannesburg, South Africa").label == "Johannesburg"
    assert resolve_area("Washington DC").label == "Washington, D.C."

    country = resolve_area("Taiwan")
    assert "bbox" in country.argument and country.label == "Taiwan"
    assert resolve_area("United Kingdom").label == "United Kingdom"

    coords = resolve_area("-26.2, 28.05, 50 km")
    assert coords.argument == {"lat": -26.2, "lon": 28.05, "radius_km": 50.0}

    box = resolve_area({"bbox": [170, -50, -170, -30]})
    assert box.lon == 180 and box.lat == -40

    assert resolve_area({"place": "Kyiv", "radius_km": 25}).argument["radius_km"] == 25


@pytest.mark.parametrize("bad", ["", "   ", {"lat": 95, "lon": 0}, {"bbox": [1, 2, 3]},
                                 {"place": "Taipei", "lat": 1, "lon": 2}, {"lat": 1, "lon": 2, "radius_km": 0},
                                 {"town": "Taipei"}, 42])
def test_resolve_area_rejects_bad_input(bad):
    with pytest.raises(AreaError):
        resolve_area(bad)


def test_unknown_place_uses_godseye_geocoding_only_when_configured():
    with pytest.raises(AreaError) as err:
        resolve_area("Zzyzx Springs", FakeGodsEye(geocode_configured=False).client())
    assert err.value.code == "area_not_found"

    resolved = resolve_area("Zzyzx Springs", FakeGodsEye(geocode_configured=True).client())
    assert resolved.method == "godseye"
    assert resolved.argument == {"place": "Zzyzx Springs"}
    assert (resolved.lat, resolved.lon) == (23.98, 121.6)


# ------------------------------------------------------------------- brief

def test_brief_has_header_sections_and_attribution():
    fake = FakeGodsEye()
    with fake.client() as client:
        brief = build_brief(client, "Taipei", now=FIXED_NOW)
    md = brief["markdown"]

    assert md.startswith("# Situation brief: Taipei\n")
    assert "- Fetched: 2026-11-13 15:30:00 UTC" in md
    assert brief["fetched_at"] == "2026-11-13T15:30:00Z"
    assert "within 100 km of 25.036°N, 121.568°E" in md
    for heading in ["## Headlines", "## Hazards", "### Earthquakes", "### Active fires",
                    "### Tropical cyclones", "## Weather", "## Air traffic (aggregate)",
                    "## Sea traffic (aggregate)", "## Sources and terms"]:
        assert heading in md

    assert "Typhoon season ends quietly (Taipei Times; 2026-11-13 14:00 UTC)" in md
    assert r"Chip exports \*surge\* \[report\]" in md
    assert "news.google.com" not in md
    assert "M4.6, 30 km E of Hualien City, Taiwan" in md
    assert "Temperature: 22.1 °C (feels like 25.2 °C)" in md
    assert "Wind: 3 km/h from the ESE" in md
    assert "Aircraft reported in the area: 18 (12 airborne, 6 on the ground)" in md
    assert "Countries of registration: Taiwan 8, Republic of Korea 5, Japan 2" in md
    assert "Military aircraft in the area: 1 (from the adsb.lol military feed)" in md

    footer = md.split("## Sources and terms", 1)[1]
    assert "Google News RSS" in footer and "personal, non-commercial use only" in footer
    assert "MIT" in footer and "does not extend to the third-party data" in footer
    for name in ["U.S. Geological Survey", "Open-Meteo", "CC BY 4.0", "OpenSky Network",
                 "adsb.lol", "ODbL", "National Hurricane Center", "Natural Earth"]:
        assert name in footer
    source_names = {s["name"] for s in brief["sources"]}
    assert "Google News RSS" in source_names and "God's Eye View" in source_names
    assert all(s["terms"] and s["url"] for s in brief["sources"])
    # Fires and ships were unavailable, so their sources are not credited.
    assert "FIRMS" not in footer and "AISStream" not in footer

    assert set(brief["sections"]) == {"headlines", "hazards", "weather", "air", "sea"}
    assert brief["sections"]["sea"]["status"] == "unavailable"
    assert brief["sections"]["hazards"]["fires"]["status"] == "unavailable"
    assert brief["sections"]["air"]["total"] == 18


def test_brief_excludes_surveillance_and_individual_identities():
    fake = FakeGodsEye()
    with fake.client() as client:
        brief = build_brief(client, "Taipei", now=FIXED_NOW)

    called = {name for name, _ in fake.tool_calls}
    assert called <= {"situation_brief", "aircraft_in_area", "vessels_in_area"}
    assert not called & set(SURVEILLANCE_TOOLS)

    everything = brief["markdown"] + json.dumps(brief["sections"]) + json.dumps(brief["sources"])
    for identity in ["PAL895", "7583ed", "RP-C1234", "EVA195", "89909d", "B-16701",
                     "RCH123", "ae1234", "05-5140"]:
        assert identity not in everything
    lowered = brief["markdown"].lower()
    for word in ["cctv", "camera", "alpr", "licence plate", "license plate", "callsign", "mmsi"]:
        assert word not in lowered
    # Raw feed errors stay out of the seed text but are reported in the JSON.
    assert "AISSTREAM_API_KEY" not in brief["markdown"]
    assert "FIRMS key" not in brief["markdown"]
    assert "Live ship positions (AIS) were not available for this brief." in brief["markdown"]


def test_brief_only_requests_what_the_sections_need():
    fake = FakeGodsEye()
    with fake.client() as client:
        brief = build_brief(client, "Taipei", ["headlines"], now=FIXED_NOW)
    assert fake.tool_calls == []
    assert list(brief["sections"]) == ["headlines"]
    assert "## Weather" not in brief["markdown"]
    assert any(r.url.path == "/api/regional-brief" for r in fake.requests)

    fake = FakeGodsEye()
    with fake.client() as client:
        build_brief(client, {"lat": 25.0, "lon": 121.5, "radius_km": 50}, ["air"], now=FIXED_NOW)
    assert [n for n, _ in fake.tool_calls] == ["aircraft_in_area", "aircraft_in_area"]
    assert all(a["area"] == {"lat": 25.0, "lon": 121.5, "radius_km": 50.0} for _, a in fake.tool_calls)


def test_brief_uses_the_regional_brief_tool_when_god_s_eye_offers_it():
    fake = FakeGodsEye(tools=SITUATION_TOOLS + ["get_regional_brief"])
    with fake.client() as client:
        brief = build_brief(client, "Taipei", ["headlines"], now=FIXED_NOW)
    assert fake.tool_calls == [("get_regional_brief", {"location": {"lat": 25.036, "lon": 121.568}})]
    assert "MCP headline" in brief["markdown"]
    assert not any(r.url.path == "/api/regional-brief" for r in fake.requests)


def test_brief_rejects_unknown_sections():
    with pytest.raises(AreaError) as err:
        build_brief(FakeGodsEye().client(), "Taipei", ["weather", "cctv"])
    assert err.value.code == "invalid_sections"


def test_brief_raises_when_god_s_eye_is_down():
    client = GodsEyeClient(BASE, transport=_failing_transport(httpx.ConnectError("refused")))
    with pytest.raises(GodsEyeUnavailable):
        build_brief(client, "Taipei")


# --------------------------------------------------------------- endpoints

@pytest.fixture
def api(monkeypatch):
    state = {"fake": FakeGodsEye(), "transport": None}

    def make_client(**kwargs):
        transport = state["transport"] or state["fake"].transport()
        return GodsEyeClient(BASE, transport=transport, **kwargs)

    monkeypatch.setattr(godseye_api, "_client", make_client)
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client(), state


def test_status_endpoint_reports_reachable_server(api):
    client, _ = api
    response = client.get("/api/godseye/status")
    assert response.status_code == 200
    data = response.json["data"]
    assert data["reachable"] is True and data["version"] == "0.3.0"
    assert "situation_brief" in data["tools"]
    assert "find_cctv_cameras" not in data["tools"]
    assert data["sections"] == ["headlines", "hazards", "weather", "air", "sea"]


def test_status_endpoint_explains_when_god_s_eye_is_not_running(api):
    client, state = api
    state["transport"] = _failing_transport(httpx.ConnectError("refused"))
    response = client.get("/api/godseye/status", headers={"Accept-Language": "en"})
    assert response.status_code == 200
    data = response.json["data"]
    assert data["reachable"] is False
    assert "not running" in data["message"] and "npm run dev" in data["message"]


def test_brief_endpoint_returns_markdown_and_metadata(api):
    client, _ = api
    response = client.post("/api/godseye/brief", json={"area": "Taipei", "sections": ["weather", "air"]})
    assert response.status_code == 200
    assert response.json["success"] is True
    data = response.json["data"]
    assert {"markdown", "sections", "fetched_at", "sources"} <= set(data)
    assert set(data["sections"]) == {"weather", "air"}
    assert data["markdown"].startswith("# Situation brief: Taipei")
    assert data["filename"].startswith("godseye-taipei-") and data["filename"].endswith(".md")
    assert any(s["name"] == "Open-Meteo" for s in data["sources"])


def test_brief_endpoint_validates_input(api):
    client, _ = api
    assert client.post("/api/godseye/brief", json={}).status_code == 400
    assert client.post("/api/godseye/brief", data="nope", content_type="text/plain").status_code == 400
    bad_sections = client.post("/api/godseye/brief", json={"area": "Taipei", "sections": ["cctv"]})
    assert bad_sections.status_code == 400
    missing = client.post("/api/godseye/brief", json={"area": "Atlantis Prime"},
                          headers={"Accept-Language": "en"})
    assert missing.status_code == 404
    assert "Atlantis Prime" in missing.json["error"]


def test_brief_endpoint_returns_503_when_god_s_eye_is_not_running(api):
    client, state = api
    state["transport"] = _failing_transport(httpx.ConnectError("refused"))
    response = client.post("/api/godseye/brief", json={"area": "Taipei"}, headers={"Accept-Language": "en"})
    assert response.status_code == 503
    assert response.json["success"] is False
    assert response.json["code"] == "godseye_unreachable"
    assert "npm run dev" in response.json["error"]
