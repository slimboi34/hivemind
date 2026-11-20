"""The public-site guard (app/public_mode.py): what visitors may and may not do.

The guard runs before routing, so in this bare app a request it lets through ends in 404
(no route), and one it refuses ends in its own 403/409/429.
"""
import pytest
from flask import Flask

from app import public_mode
from app.api import simulation as simulation_api

LET_THROUGH = 404


@pytest.fixture
def client(monkeypatch, tmp_path):
    sims = tmp_path / 'simulations'
    (sims / 'sim_hist').mkdir(parents=True)
    (sims / 'sim_new').mkdir(parents=True)
    monkeypatch.setenv('HIVEMIND_PUBLIC', '1')
    monkeypatch.setenv('HIVEMIND_RUNS_PER_DAY', '2')
    monkeypatch.setenv('HIVEMIND_RUNS_PER_VISITOR', '1')
    monkeypatch.setenv('HIVEMIND_CHATS_PER_VISITOR', '3')
    monkeypatch.setenv('HIVEMIND_ADMIN_TOKEN', 'owner-token')
    monkeypatch.setattr(public_mode, '_QUOTA_PATH', str(tmp_path / 'public_quota.json'))
    monkeypatch.setattr(public_mode.Config, 'OASIS_SIMULATION_DATA_DIR', str(sims))
    monkeypatch.setattr(public_mode, '_simulation_running', lambda: False)
    monkeypatch.setattr(public_mode, '_run_finished', lambda sid: sid == 'sim_hist')
    monkeypatch.setattr(simulation_api, '_check_simulation_prepared', lambda sid: (sid == 'sim_hist', {}))
    app = Flask(__name__)
    public_mode.register(app)
    return app.test_client()


def visitor(ip):
    return {'X-Real-IP': ip}


def test_destructive_and_owner_only_endpoints_are_refused(client):
    assert client.delete('/api/graph/project/proj_x').status_code == 403
    assert client.post('/api/graph/project/proj_x/reset').status_code == 403
    assert client.post('/api/godseye/brief', json={}).status_code == 403
    assert client.post('/api/simulation/stop', json={}).status_code == 403
    assert client.post('/api/report/tools/search', json={}).status_code == 403


def test_forced_regeneration_is_refused_except_on_start(client):
    assert client.post('/api/simulation/sim_hist/briefing', json={'force': True}).status_code == 403
    assert client.post('/api/simulation/prepare',
                       json={'simulation_id': 'sim_hist', 'force_regenerate': True}).status_code == 403


def test_daily_and_per_visitor_run_caps(client):
    url = '/api/graph/ontology/generate'
    assert client.post(url, headers=visitor('1.1.1.1')).status_code == LET_THROUGH
    assert client.post(url, headers=visitor('1.1.1.1')).status_code == 429   # one per visitor
    assert client.post(url, headers=visitor('2.2.2.2')).status_code == LET_THROUGH
    assert client.post(url, headers=visitor('3.3.3.3')).status_code == 429   # two a day in total


def test_spoofed_forwarded_for_does_not_change_the_visitor(client):
    url = '/api/graph/ontology/generate'
    assert client.post(url, headers=visitor('1.1.1.1')).status_code == LET_THROUGH
    spoofed = {**visitor('1.1.1.1'), 'X-Forwarded-For': '9.9.9.9'}
    assert client.post(url, headers=spoofed).status_code == 429


def test_earlier_runs_are_read_only_but_their_setup_page_still_opens(client):
    # An already prepared run: prepare just returns it, so it is allowed through.
    assert client.post('/api/simulation/prepare', json={'simulation_id': 'sim_hist'}).status_code == LET_THROUGH
    # A run this site didn't create and that isn't prepared would cost money: refused.
    assert client.post('/api/simulation/prepare', json={'simulation_id': 'sim_new'}).status_code == 403
    assert client.post('/api/simulation/start', json={'simulation_id': 'sim_hist'}).status_code == 403
    assert client.post('/api/graph/build', json={'project_id': 'proj_hist'}).status_code == 403


def test_briefing_and_recap_are_written_once_a_run_finishes_and_capped(client):
    assert client.post('/api/simulation/sim_new/briefing', json={}).status_code == 409  # still running
    assert client.post('/api/simulation/nope/briefing', json={}).status_code == 404
    for _ in range(public_mode._WRITES_PER_RUN):
        assert client.post('/api/simulation/sim_hist/briefing', json={}).status_code == LET_THROUGH
    assert client.post('/api/simulation/sim_hist/briefing', json={}).status_code == 403
    assert client.post('/api/simulation/sim_hist/recap', json={}).status_code == LET_THROUGH  # counted apart


def test_chat_cap_per_visitor(client):
    for _ in range(3):
        assert client.post('/api/report/chat', json={}, headers=visitor('4.4.4.4')).status_code == LET_THROUGH
    assert client.post('/api/report/chat', json={}, headers=visitor('4.4.4.4')).status_code == 429
    # a batch interview costs one question per person asked
    assert client.post('/api/simulation/interview/batch', json={'interviews': [{}, {}, {}, {}]},
                       headers=visitor('5.5.5.5')).status_code == 429


def test_reads_are_always_allowed(client):
    assert client.get('/api/simulation/sim_hist/briefing').status_code == LET_THROUGH
    assert client.get('/api/simulation/history').status_code == LET_THROUGH
    status = client.get('/api/public/status', headers=visitor('6.6.6.6')).get_json()['data']
    assert status['public'] is True and status['runs_left_today'] == 2 and status['visitor_runs_left_today'] == 1


def test_owner_can_give_todays_runs_back(client):
    url = '/api/graph/ontology/generate'
    assert client.post(url, headers=visitor('1.1.1.1')).status_code == LET_THROUGH
    assert client.post(url, headers=visitor('1.1.1.1')).status_code == 429
    assert client.post('/api/admin/quota/reset').status_code == 404  # hidden without the token
    assert client.post(url, headers=visitor('1.1.1.1')).status_code == 429
    res = client.post('/api/admin/quota/reset', headers={'X-Admin-Token': 'owner-token'})
    assert res.status_code == 200 and res.get_json()['data']['cleared']['runs'] == 1
    assert client.post(url, headers=visitor('1.1.1.1')).status_code == LET_THROUGH


def test_existing_report_is_returned_not_counted(client, monkeypatch):
    monkeypatch.setattr(public_mode, '_has_report', lambda sid: sid == 'sim_hist')
    for _ in range(3):  # asking for an existing report is free, however often
        assert client.post('/api/report/generate', json={'simulation_id': 'sim_hist'}).status_code == LET_THROUGH
    # a run without a report gets exactly one
    assert client.post('/api/report/generate', json={'simulation_id': 'sim_new'}).status_code == LET_THROUGH
    assert client.post('/api/report/generate', json={'simulation_id': 'sim_new'}).status_code == 403
    # forcing a rewrite stays off
    assert client.post('/api/report/generate',
                       json={'simulation_id': 'sim_hist', 'force_regenerate': True}).status_code == 403


def test_visitor_addresses_are_not_stored(client, tmp_path):
    client.post('/api/graph/ontology/generate', headers=visitor('203.0.113.7'))
    assert '203.0.113.7' not in (tmp_path / 'public_quota.json').read_text()


def test_tracebacks_are_not_sent_to_visitors(monkeypatch, tmp_path):
    monkeypatch.setenv('HIVEMIND_PUBLIC', '1')
    monkeypatch.setattr(public_mode, '_QUOTA_PATH', str(tmp_path / 'q.json'))
    app = Flask(__name__)
    public_mode.register(app)

    @app.route('/api/boom')
    def boom():
        from flask import jsonify
        return jsonify({'success': False, 'error': 'broke', 'traceback': 'File "/app/x.py", line 1'}), 500

    body = app.test_client().get('/api/boom').get_json()
    assert body == {'success': False, 'error': 'broke'}


def test_finished_rounds_do_not_block_the_next_run(monkeypatch):
    from types import SimpleNamespace
    from app.services.simulation_runner import SimulationRunner, RunnerStatus
    proc = SimpleNamespace(poll=lambda: None)  # process still alive (agents kept up for interviews)
    monkeypatch.setattr(SimulationRunner, '_processes', {'s1': proc})
    state = SimpleNamespace(runner_status=RunnerStatus.RUNNING, ready_for_report=True)
    monkeypatch.setattr(SimulationRunner, '_run_states', {'s1': state})
    assert public_mode._simulation_running() is False
    state.ready_for_report = False
    monkeypatch.setattr(SimulationRunner, '_check_all_platforms_completed', classmethod(lambda cls, s: False))
    assert public_mode._simulation_running() is True
