from types import SimpleNamespace

import pytest
from flask import Flask

from app.api import simulation as simulation_api
from app.services.simulation_manager import SimulationStatus


def _start(monkeypatch, body, default_cap):
    calls = []
    simulation = SimpleNamespace(
        simulation_id="sim-1",
        project_id="proj-1",
        graph_id="graph-1",
        status=SimulationStatus.READY,
    )

    class Simulations:
        def get_simulation(self, _simulation_id):
            return simulation

    def fake_start(_cls, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(to_dict=lambda: {"simulation_id": "sim-1"})

    monkeypatch.setattr(simulation_api, "SimulationManager", Simulations)
    monkeypatch.setattr(simulation_api.SimulationRunner, "start_simulation", classmethod(fake_start))
    monkeypatch.setattr(simulation_api.Config, "OASIS_DEFAULT_MAX_ROUNDS", default_cap)

    app = Flask(__name__)
    with app.test_request_context("/api/simulation/start", method="POST", json={"simulation_id": "sim-1", **body}):
        result = simulation_api.start_simulation()
    response, status = result if isinstance(result, tuple) else (result, result.status_code)
    return status, response.get_json(), calls


@pytest.mark.parametrize(
    "body,default_cap,expected",
    [
        ({}, 10, 10),                     # no max_rounds: configured cap applies
        ({"max_rounds": 25}, 10, 25),     # explicit choice wins over the default
        ({}, 0, None),                    # 0 disables the cap (upstream behaviour)
    ],
)
def test_default_round_cap(monkeypatch, body, default_cap, expected):
    status, data, calls = _start(monkeypatch, body, default_cap)

    assert status == 200
    assert calls[0]["max_rounds"] == expected
    assert data["data"].get("max_rounds_applied") == expected
