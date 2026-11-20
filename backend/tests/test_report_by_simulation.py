"""A run with several reports resolves to the newest completed one, whatever the folder order."""
import json

from app.services import report_agent
from app.services.report_agent import ReportManager


def _write(root, rid, sim, status, created):
    d = root / rid
    d.mkdir()
    (d / 'meta.json').write_text(json.dumps({
        'report_id': rid, 'simulation_id': sim, 'graph_id': 'g', 'simulation_requirement': 'q',
        'status': status, 'created_at': created, 'completed_at': created if status == 'completed' else '',
    }))


def test_newest_completed_report_wins(monkeypatch, tmp_path):
    monkeypatch.setattr(ReportManager, 'REPORTS_DIR', str(tmp_path))
    _write(tmp_path, 'report_old', 'sim_1', 'completed', '2026-11-15T10:00:00')
    _write(tmp_path, 'report_new', 'sim_1', 'completed', '2026-11-20T01:00:00')
    _write(tmp_path, 'report_failed', 'sim_1', 'failed', '2026-11-20T02:00:00')
    _write(tmp_path, 'report_other', 'sim_2', 'completed', '2026-11-20T03:00:00')
    assert ReportManager.get_report_by_simulation('sim_1').report_id == 'report_new'
    assert ReportManager.get_report_by_simulation('sim_2').report_id == 'report_other'
    assert ReportManager.get_report_by_simulation('sim_3') is None
