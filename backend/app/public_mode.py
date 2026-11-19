"""
Public mode: limits for running Hivemind as an open website on the owner's API keys.

Enabled with HIVEMIND_PUBLIC=1. Every rule here protects spend or shared history:

- New runs: at most HIVEMIND_RUNS_PER_DAY across all visitors (UTC day) and
  HIVEMIND_RUNS_PER_VISITOR per visitor IP per day, and none while a simulation is running.
- Each paid step (graph build, simulation create/prepare/start, report) works only on runs
  started on this site under that quota, and only once. Earlier runs are read-only.
- Round count is capped at OASIS_DEFAULT_MAX_ROUNDS (enforced in the start endpoint).
- Chat with agents or the report agent: HIVEMIND_CHATS_PER_VISITOR per IP per day and
  HIVEMIND_CHATS_PER_DAY in total.
- Destructive or local-only endpoints are disabled: deletes, resets, stop/close, the
  God's Eye View connector, the report tool endpoints, and forced regeneration.

Usage is stored in uploads/public_quota.json so a restart does not reset it.
"""

import hashlib
import json
import os
import re
import tarfile
import threading
from datetime import datetime, timezone

from flask import jsonify, request, send_file

from .config import Config
from .utils.logger import get_logger

logger = get_logger('hivemind.public')

_lock = threading.Lock()
_QUOTA_PATH = os.path.join(Config.UPLOAD_FOLDER, 'public_quota.json')


def enabled() -> bool:
    return os.environ.get('HIVEMIND_PUBLIC', '').lower() in ('1', 'true', 'yes')


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def runs_per_day() -> int:
    return _int_env('HIVEMIND_RUNS_PER_DAY', 5)


def runs_per_visitor() -> int:
    return _int_env('HIVEMIND_RUNS_PER_VISITOR', 1)


def chats_per_visitor() -> int:
    return _int_env('HIVEMIND_CHATS_PER_VISITOR', 20)


def chats_per_day() -> int:
    return _int_env('HIVEMIND_CHATS_PER_DAY', 150)


# --------------------------------------------------------------------------- state

def _today() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%d')


def _load() -> dict:
    try:
        with open(_QUOTA_PATH, encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    data.setdefault('days', {})
    data.setdefault('projects', {})      # project_id -> {ip, created, built, simulations: []}
    data.setdefault('simulations', {})   # simulation_id -> {project_id, started, reported}
    return data


def _save(data: dict) -> None:
    os.makedirs(os.path.dirname(_QUOTA_PATH), exist_ok=True)
    days = sorted(data['days'])
    for old in days[:-7]:  # keep a week of daily counters
        data['days'].pop(old, None)
    tmp = _QUOTA_PATH + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, _QUOTA_PATH)


def _day(data: dict) -> dict:
    day = data['days'].setdefault(_today(), {})
    day.setdefault('runs', 0)
    day.setdefault('chats', 0)
    day.setdefault('runs_by_ip', {})
    day.setdefault('chats_by_ip', {})
    return day


def client_ip() -> str:
    # Railway's edge discards client-sent X-Real-IP and X-Forwarded-For and rebuilds them:
    # X-Real-IP is the visitor, X-Forwarded-For is "<visitor>, <edge node>" (checked
    # 2026-11-19 with spoofed headers). The last X-Forwarded-For entry is the edge node,
    # which many visitors share, so it must not be used.
    real = request.headers.get('X-Real-IP', '').strip()
    if real:
        return real
    fwd = request.headers.get('X-Forwarded-For', '')
    parts = [p.strip() for p in fwd.split(',') if p.strip()]
    return parts[0] if parts else (request.remote_addr or 'unknown')


def _simulation_running() -> bool:
    from .services.simulation_runner import SimulationRunner, RunnerStatus
    active = (RunnerStatus.STARTING, RunnerStatus.RUNNING, RunnerStatus.STOPPING)
    for sim_id, proc in list(SimulationRunner._processes.items()):
        if proc.poll() is not None:
            continue
        state = SimulationRunner._run_states.get(sim_id)
        if state is None or state.runner_status in active:
            return True
    return False


def _sim_project(simulation_id: str) -> str:
    path = os.path.join(Config.OASIS_SIMULATION_DATA_DIR, simulation_id, 'state.json')
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f).get('project_id') or ''
    except (OSError, ValueError):
        return ''


def status() -> dict:
    with _lock:
        data = _load()
        day = _day(data)
        ip = client_ip()
        return {
            'public': True,
            'runs_today': day['runs'],
            'runs_per_day': runs_per_day(),
            'runs_left_today': max(0, runs_per_day() - day['runs']),
            'visitor_runs_left_today': max(0, runs_per_visitor() - day['runs_by_ip'].get(ip, 0)),
            'busy': _simulation_running(),
            'max_rounds': Config.OASIS_DEFAULT_MAX_ROUNDS,
            # Non-reversible tag for checking that visitors are told apart correctly
            'visitor': hashlib.sha256(ip.encode()).hexdigest()[:8],
        }


# --------------------------------------------------------------------------- rules

def _deny(message: str, code: int = 403):
    return jsonify({'success': False, 'error': message, 'public_limit': True}), code


_BLOCKED = [
    ('POST', re.compile(r'^/api/graph/project/[^/]+/reset$')),
    ('*', re.compile(r'^/api/godseye/')),
    ('POST', re.compile(r'^/api/simulation/(stop|close-env|generate-profiles|interview/all)$')),
    ('POST', re.compile(r'^/api/simulation/[^/]+/(briefing|recap)$')),
    ('POST', re.compile(r'^/api/report/tools/')),
    ('GET', re.compile(r'^/api/simulation/script/')),
]

_RUN_LIMIT_MSG = (
    "Today's free simulations on this site are used up ({n} a day, shared by everyone). "
    "Browse the earlier runs below, or come back tomorrow."
)


def _check() -> object:
    path, method = request.path, request.method
    if not path.startswith('/api/'):
        return None
    if path.startswith('/api/admin/'):
        return None  # token-checked by the admin route itself

    if method == 'DELETE':
        return _deny('Deleting is turned off on the public site.')
    for m, rx in _BLOCKED:
        if (m == '*' or m == method) and rx.match(path):
            return _deny('This action is turned off on the public site.')

    if method != 'POST':
        return None

    body = request.get_json(silent=True) or {}
    forced = body.get('force') is True or body.get('force_regenerate') is True
    if forced and path != '/api/simulation/start':  # the run page always sends force=true
        return _deny('Regenerating is turned off on the public site.')

    with _lock:
        data = _load()
        day = _day(data)
        ip = client_ip()

        if path == '/api/graph/ontology/generate':
            if _simulation_running():
                return _deny('Another simulation is running right now. Hivemind runs one at a time '
                             'on this site; please try again in about half an hour.', 429)
            if day['runs'] >= runs_per_day():
                return _deny(_RUN_LIMIT_MSG.format(n=runs_per_day()), 429)
            if day['runs_by_ip'].get(ip, 0) >= runs_per_visitor():
                return _deny('You have used your free simulation for today. Browse the earlier '
                             'runs below, or come back tomorrow.', 429)
            day['runs'] += 1
            day['runs_by_ip'][ip] = day['runs_by_ip'].get(ip, 0) + 1
            _save(data)
            request.environ['hivemind.public_run'] = True
            logger.info(f'public run accepted ({day["runs"]}/{runs_per_day()} today)')
            return None

        if path == '/api/graph/build':
            pid = body.get('project_id', '')
            rec = data['projects'].get(pid)
            if not rec:
                return _deny('Earlier runs are read-only on the public site.')
            if rec.get('built'):
                return _deny('This run already has its knowledge graph.')
            rec['built'] = True
            _save(data)
            return None

        if path == '/api/simulation/create':
            pid = body.get('project_id', '')
            rec = data['projects'].get(pid)
            if not rec:
                return _deny('Earlier runs are read-only on the public site.')
            if len(rec.get('simulations', [])) >= 1:
                return _deny('This run already has a simulation.')
            request.environ['hivemind.public_project'] = pid
            return None

        if path == '/api/simulation/prepare':
            sid = body.get('simulation_id', '')
            if sid not in data['simulations']:
                return _deny('Earlier runs are read-only on the public site.')
            return None

        if path == '/api/simulation/start':
            sid = body.get('simulation_id', '')
            rec = data['simulations'].get(sid)
            if not rec:
                return _deny('Earlier runs are read-only on the public site.')
            if rec.get('started'):
                return _deny('This simulation has already run.')
            if _simulation_running():
                return _deny('Another simulation is running right now; please try again shortly.', 429)
            rec['started'] = True
            _save(data)
            return None

        if path == '/api/report/generate':
            sid = body.get('simulation_id', '')
            rec = data['simulations'].setdefault(sid, {'project_id': _sim_project(sid), 'history': True})
            if rec.get('reported'):
                return _deny('This simulation already has its report.')
            if not os.path.isdir(os.path.join(Config.OASIS_SIMULATION_DATA_DIR, sid)):
                return _deny('Unknown simulation.', 404)
            rec['reported'] = True
            _save(data)
            return None

        if path in ('/api/report/chat', '/api/simulation/interview', '/api/simulation/interview/batch'):
            cost = 1
            if path.endswith('/batch'):
                cost = max(1, len(body.get('interviews') or []))
            if day['chats'] + cost > chats_per_day():
                return _deny('Chat is resting for today on the public site. Come back tomorrow.', 429)
            if day['chats_by_ip'].get(ip, 0) + cost > chats_per_visitor():
                return _deny(f'You have used today\'s {chats_per_visitor()} free questions. '
                             'Come back tomorrow.', 429)
            day['chats'] += cost
            day['chats_by_ip'][ip] = day['chats_by_ip'].get(ip, 0) + cost
            _save(data)
            return None

    return None


def _record(response):
    """Remember which projects and simulations were started on this site."""
    try:
        if response.status_code != 200 or request.method != 'POST':
            return response
        if request.path == '/api/graph/ontology/generate' and request.environ.get('hivemind.public_run'):
            pid = ((response.get_json(silent=True) or {}).get('data') or {}).get('project_id')
            if pid:
                with _lock:
                    data = _load()
                    data['projects'][pid] = {'ip': client_ip(), 'created': _today(), 'simulations': []}
                    _save(data)
        elif request.path == '/api/simulation/create' and request.environ.get('hivemind.public_project'):
            pid = request.environ['hivemind.public_project']
            sid = ((response.get_json(silent=True) or {}).get('data') or {}).get('simulation_id')
            if sid:
                with _lock:
                    data = _load()
                    data['projects'].setdefault(pid, {'simulations': []}).setdefault('simulations', []).append(sid)
                    data['simulations'][sid] = {'project_id': pid}
                    _save(data)
    except Exception as e:  # never break a response over bookkeeping
        logger.warning(f'public-mode bookkeeping failed: {e}')
    return response


# --------------------------------------------------------------------------- wiring

def register(app) -> None:
    """Install the guard, the status endpoint, the AGPL source download and the admin import."""
    if enabled():
        app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024
        app.before_request(_check)
        app.after_request(_record)
        logger.info(f'Public mode on: {runs_per_day()} runs/day, {runs_per_visitor()}/visitor, '
                    f'{Config.OASIS_DEFAULT_MAX_ROUNDS} rounds max')

    @app.route('/api/public/status')
    def public_status():
        if not enabled():
            return jsonify({'success': True, 'data': {'public': False}})
        return jsonify({'success': True, 'data': status()})

    source = os.environ.get('HIVEMIND_SOURCE_ARCHIVE', '')

    @app.route('/source.tar.gz')
    def source_archive():
        # AGPL-3.0 section 13: users of a network service are offered its source.
        if source and os.path.isfile(source):
            return send_file(source, mimetype='application/gzip', as_attachment=True,
                             download_name='hivemind-source.tar.gz')
        return jsonify({'success': False, 'error': 'Source archive not built into this deployment.'}), 404

    token = os.environ.get('HIVEMIND_ADMIN_TOKEN', '')

    @app.route('/api/admin/headers')
    def admin_headers():
        """Owner-only: show the forwarding headers the platform's edge sends (for client_ip)."""
        if not token or request.headers.get('X-Admin-Token') != token:
            return jsonify({'success': False, 'error': 'Not found'}), 404
        keep = ('forwarded', 'real', 'client', 'envoy', 'cf-', 'fly-', 'true-')
        seen = {k: v for k, v in request.headers.items() if any(s in k.lower() for s in keep)}
        return jsonify({'success': True, 'data': {'headers': seen, 'remote_addr': request.remote_addr,
                                                  'client_ip_used': client_ip()}})

    @app.route('/api/admin/import', methods=['POST'])
    def admin_import():
        """Unpack a tar.gz of projects/, simulations/ and reports/ into uploads (owner only)."""
        if not token or request.headers.get('X-Admin-Token') != token:
            return jsonify({'success': False, 'error': 'Not found'}), 404
        f = request.files.get('archive')
        if not f:
            return jsonify({'success': False, 'error': 'archive missing'}), 400
        allowed = ('projects/', 'simulations/', 'reports/')
        with tarfile.open(fileobj=f.stream, mode='r:gz') as tar:
            members = [m for m in tar.getmembers() if m.name.startswith(allowed)]
            tar.extractall(Config.UPLOAD_FOLDER, members=members, filter='data')
        from .services.simulation_runner import SimulationRunner
        SimulationRunner._run_states.clear()
        return jsonify({'success': True, 'data': {'imported': len(members)}})
