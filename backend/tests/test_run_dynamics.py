"""Tests for cascade reconstruction, dynamics and consensus PDF."""

from pathlib import Path

import pytest

from app.services.consensus_report import build_consensus_pdf
from app.services.run_dynamics import build_dynamics
from app.services.trace_reader import read_platform_dynamics, read_simulation_traces


EXAMPLE_SIM = "sim_168d7ecb477b"
UPLOADS = Path(__file__).resolve().parents[1] / "uploads" / "simulations" / EXAMPLE_SIM


@pytest.mark.skipif(not UPLOADS.is_dir(), reason="example simulation not on disk")
def test_twitter_cascades_match_research_ballpark():
    data = read_platform_dynamics(EXAMPLE_SIM, "twitter")
    assert data is not None
    assert data["posts"] == 69
    # Research note: 18 derived (repost/quote), branching ≈ 0.26
    assert data["derived_posts"] == 18
    assert abs(data["branching_factor"] - 0.261) < 0.02
    assert data["roots"] >= 40  # 51 roots in the note; allow small variance if seeds differ
    assert data["orphan_cascades"] >= 30
    assert data["max_depth"] == 1
    assert data["blind_activations"] == 35
    # Top cascade should be a broadcast-ish star, not a deep chain
    top = data["cascades"][0]
    assert top["size"] >= 4
    assert top["shape"] in ("broadcast", "orphan", "chain")
    assert "tree" in top and top["tree"]["children"] is not None


@pytest.mark.skipif(not UPLOADS.is_dir(), reason="example simulation not on disk")
def test_dynamics_health_and_orphans():
    dyn = build_dynamics(EXAMPLE_SIM)
    assert dyn["simulation_id"] == EXAMPLE_SIM
    assert dyn["health"]["overall"] in ("green", "amber", "red")
    assert dyn["health"]["checks"]
    assert dyn["cascades"]["summary"]["branching_factor"] is not None
    assert dyn["orphans"]["cascade_orphans"] >= 0
    assert dyn["consensus"]["verdict"]
    assert dyn["cascades"]["top"]


@pytest.mark.skipif(not UPLOADS.is_dir(), reason="example simulation not on disk")
def test_consensus_pdf_is_valid_pdf():
    pdf = build_consensus_pdf(EXAMPLE_SIM)
    assert pdf[:5] == b"%PDF-"
    assert len(pdf) > 1500


def test_missing_simulation_traces_empty():
    traces = read_simulation_traces("sim_does_not_exist_xyz")
    assert traces["platforms"] == {}
