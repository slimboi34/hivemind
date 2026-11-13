"""
God's Eye View connector routes.

GET  /api/godseye/status  whether God's Eye View is reachable, its version and tools
POST /api/godseye/brief   {area, sections?} -> a markdown situation brief for seeding

Neither route calls an LLM or Zep; they only read God's Eye View's local server.
"""

from flask import jsonify, request

from . import godseye_bp
from ..config import Config
from ..services.godseye_client import GodsEyeClient, GodsEyeError, GodsEyeUnavailable
from ..services.godseye_seed import SECTION_KEYS, AreaError, build_brief, suggested_filename
from ..utils.locale import t
from ..utils.logger import get_logger

logger = get_logger('mirofish.api.godseye')

STATUS_TIMEOUT_S = 10.0


def _client(**kwargs) -> GodsEyeClient:
    return GodsEyeClient(Config.GODSEYE_URL, **kwargs)


def _unreachable_response(exc: GodsEyeUnavailable):
    key = 'godseye.errors.timeout' if exc.code == 'timeout' else 'godseye.errors.unreachable'
    return jsonify({
        "success": False,
        "error": t(key, url=Config.GODSEYE_URL),
        "code": f"godseye_{exc.code}",
    }), 503


@godseye_bp.route('/status', methods=['GET'])
def godseye_status():
    """Report whether God's Eye View answers, its version and the tools Hivemind may use."""
    try:
        with _client(timeout=STATUS_TIMEOUT_S) as client:
            info = client.status()
    except GodsEyeError as exc:  # e.g. a malformed GODSEYE_URL
        info = {"reachable": False, "url": Config.GODSEYE_URL,
                "error": exc.message, "error_code": exc.code}
    if not info.get("reachable"):
        key = 'godseye.errors.timeout' if info.get("error_code") == 'timeout' else 'godseye.errors.unreachable'
        info["message"] = t(key, url=Config.GODSEYE_URL)
    info["sections"] = list(SECTION_KEYS)
    return jsonify({"success": True, "data": info})


@godseye_bp.route('/brief', methods=['POST'])
def godseye_brief():
    """Build a markdown situation brief for an area from God's Eye View's live data."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or payload.get("area") in (None, ""):
        return jsonify({"success": False, "error": t('godseye.errors.areaRequired'),
                        "code": "area_required"}), 400

    try:
        with _client() as client:
            brief = build_brief(client, payload["area"], payload.get("sections"))
    except AreaError as exc:
        if exc.code == "area_not_found":
            area = payload["area"]
            name = area.get("place") if isinstance(area, dict) else area
            return jsonify({"success": False, "error": t('godseye.errors.areaNotFound', area=name),
                            "code": exc.code}), 404
        return jsonify({"success": False, "error": t('godseye.errors.invalidRequest', details=exc.message),
                        "code": exc.code}), 400
    except GodsEyeUnavailable as exc:
        return _unreachable_response(exc)
    except GodsEyeError as exc:
        logger.warning(f"God's Eye brief failed ({exc.code}): {exc.message}")
        return jsonify({"success": False, "error": t('godseye.errors.failed', details=exc.message),
                        "code": f"godseye_{exc.code}"}), 502

    brief["filename"] = suggested_filename(brief["area"]["label"], brief["fetched_at"])
    return jsonify({"success": True, "data": brief})
