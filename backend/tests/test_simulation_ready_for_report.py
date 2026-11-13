import pytest

from app.services import simulation_runner as runner_module
from app.services.simulation_runner import RunnerStatus, SimulationRunner, SimulationRunState


@pytest.fixture
def saved(monkeypatch):
    calls = []
    monkeypatch.setattr(SimulationRunner, "_save_run_state", classmethod(lambda _cls, st: calls.append(st.ready_for_report)))
    yield calls
    SimulationRunner._graph_memory_enabled.pop("sim-r", None)


def _state():
    return SimulationRunState(simulation_id="sim-r", runner_status=RunnerStatus.RUNNING,
                              twitter_completed=True, reddit_completed=True)


def test_drains_graph_memory_then_marks_ready(monkeypatch, saved):
    stopped = []
    monkeypatch.setattr(runner_module.ZepGraphMemoryManager, "stop_updater",
                        classmethod(lambda _cls, sid: stopped.append(sid)))
    SimulationRunner._graph_memory_enabled["sim-r"] = True
    state = _state()

    SimulationRunner._finish_rounds_keep_env(state)

    assert stopped == ["sim-r"]
    assert state.ready_for_report is True
    assert saved == [True]
    assert "sim-r" not in SimulationRunner._graph_memory_enabled


def test_failed_drain_keeps_report_blocked(monkeypatch, saved):
    def boom(_cls, _sid):
        raise RuntimeError("zep down")
    monkeypatch.setattr(runner_module.ZepGraphMemoryManager, "stop_updater", classmethod(boom))
    SimulationRunner._graph_memory_enabled["sim-r"] = True
    state = _state()

    SimulationRunner._finish_rounds_keep_env(state)

    assert state.ready_for_report is False
    assert saved == []
    assert SimulationRunner._graph_memory_enabled.get("sim-r") is True  # finalization retries


def test_without_graph_memory_marks_ready_immediately(monkeypatch, saved):
    stopped = []
    monkeypatch.setattr(runner_module.ZepGraphMemoryManager, "stop_updater",
                        classmethod(lambda _cls, sid: stopped.append(sid)))
    state = _state()

    SimulationRunner._finish_rounds_keep_env(state)

    assert stopped == []
    assert state.ready_for_report is True


def test_ready_for_report_survives_save_and_load(tmp_path, monkeypatch):
    monkeypatch.setattr(SimulationRunner, "RUN_STATE_DIR", str(tmp_path))
    state = _state()
    state.ready_for_report = True
    SimulationRunner._save_run_state(state)

    loaded = SimulationRunner._load_run_state("sim-r")

    assert loaded.ready_for_report is True
    assert loaded.to_dict()["ready_for_report"] is True
