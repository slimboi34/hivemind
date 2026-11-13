import json

from flask import Flask

from app.api import simulation as simulation_api
from app.services.simulation_analytics import build_analytics
from app.services.simulation_runner import SimulationRunner


def act(round_num, name, action_type, platform="twitter", agent_id=None, ts=None, **args):
    return {
        "round_num": round_num,
        "timestamp": ts or f"2026-11-13T00:{round_num:02d}:00",
        "platform": platform,
        "agent_id": agent_id if agent_id is not None else abs(hash(name)) % 1000,
        "agent_name": name,
        "action_type": action_type,
        "action_args": args,
        "result": None,
        "success": True,
    }


def sample_actions():
    return [
        act(0, "Thandi", "CREATE_POST", content="Taxi fares up again"),
        act(1, "Sipho", "CREATE_POST", content="Load shedding stage 4", post_id=2),
        act(1, "Sipho", "LIKE_POST", post_id=1, post_author_name="Thandi", post_content="Taxi fares up again"),
        act(1, "Lerato", "REPOST", original_author_name="Thandi", original_content="Taxi fares up again"),
        act(2, "Lerato", "QUOTE_POST", quoted_id=2, original_author_name="Sipho", original_content="Load shedding stage 4"),
        act(2, "Sipho", "DISLIKE_POST", platform="reddit", post_id=9,
            post_author_name="Thandi", post_content="Reddit-only post"),
        act(2, "Thandi", "CREATE_COMMENT", content="Agreed", post_id=2,
            post_author_name="Sipho", post_content="Load shedding stage 4"),
        act(3, "Thandi", "LIKE_POST", post_id=1, post_author_name="Thandi", post_content="Taxi fares up again"),
        act(3, "Lerato", "FOLLOW", target_user_name="Thandi"),
        act(3, "Sipho", "MUTE", platform="reddit", target_user_name="Lerato"),
        act(3, "Lerato", "DO_NOTHING"),
        act(4, "Thandi", "INTERVIEW", prompt="How do you feel?"),
    ]


def test_rounds_cover_planned_run_and_categories_add_up():
    data = build_analytics(sample_actions(), total_rounds=6)

    assert [r["round"] for r in data["rounds"]] == list(range(6))
    assert data["totals"]["actions"] == 11  # INTERVIEW excluded
    r1 = data["rounds"][1]
    assert (r1["post"], r1["support"], r1["total"], r1["active_agents"]) == (1, 2, 3, 2)
    assert data["rounds"][5]["total"] == 0
    for r in data["rounds"]:
        assert r["total"] == sum(r[c] for c in data["categories"])
        assert r["total"] == r["twitter"] + r["reddit"]
    t = data["totals"]
    assert (t["support"], t["reply"], t["oppose"], t["post"], t["passive"]) == (5, 1, 2, 2, 1)


def test_interaction_edges_point_at_content_author_and_skip_self():
    data = build_analytics(sample_actions())
    edges = {(e["source"], e["target"], e["kind"]): e for e in data["edges"]}

    assert edges[("Lerato", "Thandi", "support")]["weight"] == 2  # repost + follow
    assert edges[("Lerato", "Thandi", "support")]["by_round"] == {"1": 1, "3": 1}
    assert edges[("Lerato", "Thandi", "support")]["first_round"] == 1
    assert edges[("Thandi", "Sipho", "reply")]["weight"] == 1
    assert edges[("Sipho", "Thandi", "oppose")]["weight"] == 1
    assert ("Thandi", "Thandi", "support") not in edges
    assert data["totals"]["self_interactions"] == 1
    assert data["totals"]["interactions"] == sum(e["weight"] for e in data["edges"])


def test_influence_ranking_reach_and_approval():
    data = build_analytics(sample_actions())
    agents = {a["name"]: a for a in data["agents"]}

    thandi = agents["Thandi"]
    assert thandi["received"] == {"support": 3, "reply": 0, "oppose": 1}
    assert thandi["reach"] == 2
    assert thandi["approval"] == 0.75
    assert data["agents"][0]["name"] == "Thandi"
    assert agents["Lerato"]["received"]["oppose"] == 1
    assert agents["Lerato"]["approval"] == 0.0
    assert agents["Lerato"]["first_round"] == 1


def test_posts_match_by_id_or_content_and_rank_by_engagement():
    data = build_analytics(sample_actions())
    posts = {(p["platform"], p["author"], p["content"]): p for p in data["top_posts"]}

    taxi = posts[("twitter", "Thandi", "Taxi fares up again")]
    assert (taxi["likes"], taxi["reposts"], taxi["engagement"]) == (2, 1, 3)
    load = posts[("twitter", "Sipho", "Load shedding stage 4")]
    assert (load["quotes"], load["comments"]) == (1, 1)
    assert posts[("reddit", "Thandi", "Reddit-only post")]["dislikes"] == 1
    assert data["top_posts"][0]["content"] == "Taxi fares up again"


def test_empty_simulation():
    data = build_analytics([], total_rounds=0)
    assert data["totals"]["actions"] == 0
    assert data["totals"]["rounds"] == 0
    assert data["edges"] == [] and data["agents"] == [] and data["top_posts"] == []


def test_analytics_endpoint_reads_platform_logs(tmp_path, monkeypatch):
    sim_dir = tmp_path / "sim-a"
    for platform, rows in {
        "twitter": [
            {"round": 0, "timestamp": "t0", "agent_id": 0, "agent_name": "Thandi",
             "action_type": "CREATE_POST", "action_args": {"content": "Hello Jozi"}},
            {"event_type": "round_end", "round": 0},
        ],
        "reddit": [
            {"round": 1, "timestamp": "t1", "agent_id": 1, "agent_name": "Sipho",
             "action_type": "LIKE_POST",
             "action_args": {"post_author_name": "Thandi", "post_content": "Hello Jozi"}},
        ],
    }.items():
        (sim_dir / platform).mkdir(parents=True)
        (sim_dir / platform / "actions.jsonl").write_text(
            "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
        )
    monkeypatch.setattr(SimulationRunner, "RUN_STATE_DIR", str(tmp_path))
    monkeypatch.setattr(SimulationRunner, "get_run_state", classmethod(lambda _cls, _sid: None))

    app = Flask(__name__)
    app.register_blueprint(simulation_api.simulation_bp, url_prefix="/api/simulation")
    res = app.test_client().get("/api/simulation/sim-a/analytics")

    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["simulation_id"] == "sim-a"
    assert data["totals"]["actions"] == 2
    assert data["totals"]["twitter"] == 1 and data["totals"]["reddit"] == 1
    assert data["edges"][0]["source"] == "Sipho" and data["edges"][0]["target"] == "Thandi"
