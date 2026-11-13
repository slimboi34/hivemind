"""
Client for God's Eye View's local MCP server.

God's Eye View (github.com/bilawalsidhu/gods-eye-view) serves its tools over
stateless Streamable HTTP at ``/mcp``: one JSON-RPC message per POST, answered
with JSON. This client speaks just enough of that protocol for Hivemind's
seed import: ``initialize``, ``tools/list`` and ``tools/call``.

Two plain HTTP routes of the same server are also read, because the MCP
surface leaves them out by design: ``/api/regional-brief`` (the data behind
the ``get_regional_brief`` tool, used for headlines) and
``/api/geocode/status`` (whether God's Eye can resolve place names).

Tools that identify or follow individual people, aircraft or vessels, and
camera or licence-plate tools, are refused here so no caller can reach them
through this client.
"""

from __future__ import annotations

import itertools
import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

DEFAULT_GODSEYE_URL = "http://localhost:4173"
PROTOCOL_VERSION = "2025-06-18"
CLIENT_INFO = {"name": "hivemind", "version": "0.1.0"}

DEFAULT_TIMEOUT_S = 45.0
DEFAULT_CONNECT_TIMEOUT_S = 3.0

# Excluded by design: cameras, licence-plate readers, and anything that finds,
# tracks or describes one aircraft or vessel by identity. military_awareness
# lists individual military contacts by callsign, so it is excluded as well.
EXCLUDED_TOOLS = frozenset({
    "find_cctv_cameras",
    "get_cctv_snapshot",
    "find_alpr_cameras",
    "find_aircraft",
    "get_aircraft_track",
    "get_aircraft_info",
    "find_vessel",
    "get_vessel_track",
    "military_awareness",
})
# Defence in depth for tools a future God's Eye version may add.
_EXCLUDED_NAME = re.compile(
    r"cctv|alpr|camera|surveil|licen[cs]e_?plate|_track$|^find_(aircraft|vessel)",
    re.IGNORECASE,
)


def is_excluded_tool(name: str) -> bool:
    """Whether Hivemind refuses to call this God's Eye tool."""
    return name in EXCLUDED_TOOLS or bool(_EXCLUDED_NAME.search(name or ""))


class GodsEyeError(Exception):
    """A God's Eye request failed. ``code`` says how, for API responses."""

    code = "error"

    def __init__(self, message: str, *, code: Optional[str] = None, detail: Any = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        self.detail = detail


class GodsEyeUnavailable(GodsEyeError):
    """God's Eye is not running, not reachable, or too slow to answer."""

    code = "unreachable"


class GodsEyeToolError(GodsEyeError):
    """A tool ran but reported an error (for example a feed that needs a key)."""

    code = "tool_error"


class GodsEyeExcludedTool(GodsEyeError):
    """The tool is excluded by design (surveillance or identity tracking)."""

    code = "excluded"


@dataclass
class ToolResult:
    name: str
    summary: str
    data: dict = field(default_factory=dict)


class GodsEyeClient:
    """Minimal MCP JSON-RPC client for one God's Eye View server."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        *,
        timeout: float = DEFAULT_TIMEOUT_S,
        connect_timeout: float = DEFAULT_CONNECT_TIMEOUT_S,
        transport: Optional[httpx.BaseTransport] = None,
    ):
        self.base_url = (base_url or DEFAULT_GODSEYE_URL).rstrip("/")
        if not re.match(r"^https?://", self.base_url):
            raise GodsEyeError(
                f"GODSEYE_URL must be an http(s) URL, got {self.base_url!r}",
                code="config",
            )
        self.mcp_url = f"{self.base_url}/mcp"
        self._http = httpx.Client(
            timeout=httpx.Timeout(timeout, connect=connect_timeout),
            transport=transport,
            # The /mcp route refuses forwarded requests, so never use a proxy
            # from the environment for this loopback service.
            trust_env=False,
            follow_redirects=False,
        )
        self._ids = itertools.count(1)
        self._server: Optional[dict] = None
        self._tools: Optional[list[dict]] = None

    # -- lifecycle -----------------------------------------------------

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "GodsEyeClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- transport -----------------------------------------------------

    def _unreachable(self, exc: Exception) -> GodsEyeUnavailable:
        if isinstance(exc, httpx.TimeoutException):
            return GodsEyeUnavailable(
                f"God's Eye View at {self.base_url} did not answer in time.",
                code="timeout",
            )
        return GodsEyeUnavailable(
            f"God's Eye View is not reachable at {self.base_url}. Start it "
            "(npm run dev or npm run preview in its checkout) or set GODSEYE_URL."
        )

    def _rpc(self, method: str, params: Optional[dict] = None) -> Any:
        request_id = next(self._ids)
        payload = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            payload["params"] = params
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if method != "initialize":
            headers["MCP-Protocol-Version"] = (
                (self._server or {}).get("protocolVersion") or PROTOCOL_VERSION
            )
        try:
            response = self._http.post(self.mcp_url, json=payload, headers=headers)
        except httpx.TransportError as exc:
            raise self._unreachable(exc) from exc

        if response.status_code == 403:
            raise GodsEyeError(
                "God's Eye View refused the request: its /mcp route accepts only "
                "local requests (a loopback host, no proxy, sharing off).",
                code="forbidden",
            )
        if response.status_code == 404:
            raise GodsEyeError(
                f"No MCP endpoint at {self.mcp_url}. Is GODSEYE_URL pointing at God's Eye View?",
                code="no_mcp",
            )
        if response.status_code >= 400:
            raise GodsEyeError(
                f"God's Eye View answered HTTP {response.status_code} for {method}.",
                code="http",
            )

        message = self._decode(response)
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
            raise GodsEyeError("God's Eye View sent a malformed JSON-RPC reply.", code="protocol")
        if message.get("id") != request_id:
            raise GodsEyeError("God's Eye View answered a different request id.", code="protocol")
        if "error" in message:
            error = message.get("error") or {}
            raise GodsEyeError(
                f"God's Eye View rejected {method}: {error.get('message', 'unknown error')}",
                code="rpc",
                detail=error,
            )
        if "result" not in message:
            raise GodsEyeError("God's Eye View sent a reply without a result.", code="protocol")
        return message["result"]

    @staticmethod
    def _decode(response: httpx.Response) -> Any:
        content_type = response.headers.get("content-type", "")
        text = response.text
        try:
            if "text/event-stream" in content_type:
                # A server may answer one POST as a short event stream; the
                # reply is the last JSON-RPC message in it.
                events = [
                    line[len("data:"):].strip()
                    for line in text.splitlines()
                    if line.startswith("data:")
                ]
                return json.loads(events[-1]) if events else None
            return json.loads(text)
        except (ValueError, IndexError) as exc:
            raise GodsEyeError(
                "God's Eye View sent a reply that is not JSON.", code="protocol"
            ) from exc

    def _get_json(self, path: str, params: Optional[dict] = None) -> Any:
        try:
            response = self._http.get(f"{self.base_url}{path}", params=params)
        except httpx.TransportError as exc:
            raise self._unreachable(exc) from exc
        if response.status_code >= 400:
            raise GodsEyeError(
                f"God's Eye View answered HTTP {response.status_code} for {path}.",
                code="http",
            )
        try:
            return response.json()
        except ValueError as exc:
            raise GodsEyeError(f"God's Eye View sent non-JSON for {path}.", code="protocol") from exc

    # -- MCP -----------------------------------------------------------

    def initialize(self) -> dict:
        """Run the MCP handshake; returns the server's ``initialize`` result."""
        result = self._rpc(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": CLIENT_INFO,
            },
        )
        if not isinstance(result, dict):
            raise GodsEyeError("God's Eye View sent an invalid initialize result.", code="protocol")
        self._server = result
        try:
            # Stateless HTTP needs no session, but the protocol expects it.
            self._notify("notifications/initialized")
        except GodsEyeError:
            pass
        return result

    def _notify(self, method: str) -> None:
        try:
            self._http.post(
                self.mcp_url,
                json={"jsonrpc": "2.0", "method": method},
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "MCP-Protocol-Version": (self._server or {}).get("protocolVersion") or PROTOCOL_VERSION,
                },
            )
        except httpx.TransportError as exc:
            raise self._unreachable(exc) from exc

    def _ensure_initialized(self) -> dict:
        return self._server if self._server is not None else self.initialize()

    @property
    def server_info(self) -> dict:
        """``serverInfo`` from the handshake (name and version)."""
        return (self._ensure_initialized() or {}).get("serverInfo") or {}

    def list_tools(self, *, include_excluded: bool = False) -> list[dict]:
        """Tools the server offers; excluded tools are dropped unless asked for."""
        if self._tools is None:
            self._ensure_initialized()
            tools: list[dict] = []
            cursor = None
            for _ in range(20):  # pagination guard
                result = self._rpc("tools/list", {"cursor": cursor} if cursor else {})
                tools.extend(t for t in (result or {}).get("tools", []) if isinstance(t, dict))
                cursor = (result or {}).get("nextCursor")
                if not cursor:
                    break
            self._tools = tools
        if include_excluded:
            return list(self._tools)
        return [t for t in self._tools if not is_excluded_tool(t.get("name", ""))]

    def has_tool(self, name: str) -> bool:
        return any(t.get("name") == name for t in self.list_tools())

    def call_tool(self, name: str, arguments: Optional[dict] = None) -> ToolResult:
        """Call a tool. Raises GodsEyeToolError when the tool reports an error."""
        if is_excluded_tool(name):
            raise GodsEyeExcludedTool(
                f"The God's Eye tool {name!r} is excluded by design: Hivemind uses "
                "aggregate situational context only, never cameras or individual tracking."
            )
        self._ensure_initialized()
        result = self._rpc("tools/call", {"name": name, "arguments": arguments or {}})
        if not isinstance(result, dict):
            raise GodsEyeError(f"God's Eye View sent an invalid result for {name}.", code="protocol")

        texts = [
            c.get("text", "")
            for c in result.get("content") or []
            if isinstance(c, dict) and c.get("type") == "text"
        ]
        summary = texts[0] if texts else ""
        data = result.get("structuredContent")
        if not isinstance(data, dict):
            data = {}
            # Older servers carry the data only as a second JSON text block.
            for text in texts[1:]:
                try:
                    parsed = json.loads(text)
                except ValueError:
                    continue
                if isinstance(parsed, dict):
                    data = parsed
                    break
        if result.get("isError"):
            raise GodsEyeToolError(
                summary or f"The God's Eye tool {name} failed.",
                detail=data.get("error") if isinstance(data, dict) else None,
            )
        return ToolResult(name=name, summary=summary, data=data)

    # -- plain HTTP routes ---------------------------------------------

    def regional_brief(self, lat: float, lon: float) -> dict:
        """Place, weather and recent headlines near a point (``/api/regional-brief``)."""
        data = self._get_json(
            "/api/regional-brief",
            {"latitude": f"{lat:.5f}", "longitude": f"{lon:.5f}"},
        )
        if not isinstance(data, dict):
            raise GodsEyeError("God's Eye View sent an invalid regional brief.", code="protocol")
        return data

    def geocode_configured(self) -> Optional[bool]:
        """Whether God's Eye can resolve place names; None when it cannot say."""
        try:
            data = self._get_json("/api/geocode/status")
        except GodsEyeUnavailable:
            raise
        except GodsEyeError:
            return None
        if isinstance(data, dict) and isinstance(data.get("configured"), bool):
            return data["configured"]
        return None

    def geocode(self, name: str) -> Optional[dict]:
        """Resolve a place name through God's Eye; returns ``{label, lat, lon}`` or None."""
        data = self._get_json("/api/geocode", {"q": name})
        results = data.get("results") if isinstance(data, dict) else None
        first = results[0] if isinstance(results, list) and results else None
        location = ((first or {}).get("geometry") or {}).get("location") or {}
        lat, lon = location.get("lat"), location.get("lng")
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            return None
        return {"label": first.get("formatted_address") or name, "lat": float(lat), "lon": float(lon)}

    # -- status --------------------------------------------------------

    def status(self) -> dict:
        """Reachability, version and the tools Hivemind may use."""
        try:
            init = self._ensure_initialized()
            all_tools = self.list_tools(include_excluded=True)
        except GodsEyeError as exc:
            return {
                "reachable": False,
                "url": self.base_url,
                "error": exc.message,
                "error_code": exc.code,
            }
        server = init.get("serverInfo") or {}
        names = [t.get("name") for t in all_tools if t.get("name")]
        try:
            geocode = self.geocode_configured()
        except GodsEyeError:
            geocode = None
        return {
            "reachable": True,
            "url": self.base_url,
            "server": server.get("name"),
            "version": server.get("version"),
            "protocol_version": init.get("protocolVersion"),
            "tools": [n for n in names if not is_excluded_tool(n)],
            "excluded_tools": [n for n in names if is_excluded_tool(n)],
            "place_search": geocode,
        }
