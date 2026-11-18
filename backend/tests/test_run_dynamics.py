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


def _trace(rows):
    import sqlite3

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE trace (user_id INT, created_at TEXT, action TEXT)")
    conn.executemany("INSERT INTO trace VALUES (?, ?, ?)", rows)
    return conn


def test_blind_turns_on_a_step_clock():
    from app.services.trace_reader import _blind_activations

    conn = _trace([
        (1, "0", "sign_up"), (1, "0", "create_post"),          # opening post: not a turn
        (1, "1", "refresh"), (1, "1", "create_post"),          # saw a feed
        (2, "1", "create_post"),                                # no refresh: blind
        (2, "2", "refresh"), (2, "2", "like_post"), (2, "2", "create_post"),   # one turn, two actions
        (3, "9", "interview"),                                  # report-time interview: not a turn
    ])
    assert _blind_activations(conn) == (1, 3)


def test_wall_clock_turns_are_not_all_counted_blind():
    """Refresh and action never share a timestamp on this clock, and opening
    posts carry real times. Both used to be counted as blind turns."""
    from app.services.trace_reader import _blind_activations

    t = "2026-11-18 02:{:02d}:{:02d}.000001".format
    conn = _trace([
        (1, t(3, 27), "create_post"), (2, t(3, 27), "create_post"),            # opening posts
        (1, t(8, 18), "refresh"), (2, t(8, 18), "refresh"),                    # round 1
        (1, t(10, 52), "create_comment"), (2, t(11, 23), "create_post"),
        (2, t(11, 30), "like_post"),                                           # same turn, later step
        (1, t(12, 48), "refresh"),                                             # round 2: only agent 1 got a feed
        (1, t(16, 21), "create_comment"), (3, t(16, 22), "create_post"),
    ])
    assert _blind_activations(conn) == (1, 4)


def test_health_levels_have_three_bands():
    """A check that passes its target must be able to come out green."""
    from app.services.run_dynamics import _health_checks

    platforms = {"twitter": {"blind_activations": 0, "activations": 40, "top_slot_share": 0.2,
                             "roots": 20, "orphan_cascades": 8, "derived_posts": 12, "posts": 24}}
    analytics = {"totals": {"agents_active": 9, "support": 20, "post": 24},
                 "agents": [{"name": f"a{i}", "actions": 1} for i in range(9)]}
    state = type("S", (), {"total_rounds": 10, "current_round": 10, "simulation_id": None})()
    health = _health_checks(platforms, analytics, [f"a{i}" for i in range(10)], state)
    assert {c["id"]: c["level"] for c in health["checks"]} == {
        "blind_activations": "green", "participation": "green", "action_mix": "green",
        "feed_degeneracy": "green", "branching": "green", "horizon": "green"}
    assert health["overall"] == "green"

    analytics["totals"]["agents_active"] = 4          # 40% took part: amber, not red
    health = _health_checks(platforms, analytics, [f"a{i}" for i in range(10)], state)
    assert {c["id"]: c["level"] for c in health["checks"]}["participation"] == "amber"
