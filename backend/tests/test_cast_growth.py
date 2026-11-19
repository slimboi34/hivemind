"""Growing the cast: the circle around key actors and accounts that join mid-run."""

import asyncio
import json
import sys
from pathlib import Path

import pytest

from app.services import cast_growth as growth
from app.services.run_cast import build_cast_tree

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

CAST = [
    {"agent_id": 0, "name": "Acme Corp", "entity_type": "PublicCompany", "degree": 9, "summary": "Maker"},
    {"agent_id": 1, "name": "Jo Lee", "entity_type": "CompanyExecutive", "degree": 4, "summary": "CEO"},
    {"agent_id": 2, "name": "The Ledger", "entity_type": "MediaOutlet", "degree": 1, "summary": ""},
]


def account(name, anchor="Acme Corp", **over):
    return {"name": name, "anchor": anchor, "relation": "works for", "type": "employee", "stance": "Opposing",
            "bio": "Bio.", "persona": "You are on the factory floor.", "profession": "Fitter", "age": 41,
            "why": "Their job is on the line.", **over}


def test_settings_layer_defaults_then_run_config_then_environment():
    assert growth.settings({}, env={})["join_max"] == growth.DEFAULTS["join_max"]
    opts = growth.settings({"growth_config": {"join_max": 4, "circle": False}}, env={"HIVEMIND_JOIN_MAX": "2"})
    assert (opts["join_max"], opts["circle"]) == (2, False)
    assert growth.settings({}, env={"HIVEMIND_JOIN": "off", "HIVEMIND_JOIN_EVERY": "0"})["join"] is False
    assert growth.settings({}, env={"HIVEMIND_JOIN_EVERY": "0"})["join_every"] == 1


def test_model_reply_is_read_through_a_code_fence():
    assert growth.parse_json('Here you go:\n```json\n{"accounts": []}\n```') == {"accounts": []}
    with pytest.raises(ValueError):
        growth.parse_json("nobody")


def test_anchors_are_the_most_connected_actors():
    assert [a["name"] for a in growth.pick_anchors(CAST, 2)] == ["Acme Corp", "Jo Lee"]


def test_only_usable_accounts_survive():
    rows = growth.parse_accounts({"accounts": [
        account("Acme line worker"),
        account("acme  corp"),                                   # already in the cast
        account("Acme line worker"),                             # said twice
        account("Acme supplier", type="Wizard", age=None),       # unknown type, an organisation
        account("Acme third hire"),                              # over the per-anchor limit
        account("Ledger reader", anchor="Nobody"),               # anchor is not in the cast
        account("No persona", anchor="Jo Lee", persona=""),
        "not an object",
    ]}, CAST, limit=10, per_anchor=2, require_anchor=True)
    assert [r["name"] for r in rows] == ["Acme line worker", "Acme supplier"]
    assert rows[0]["entity_type"] == "Employee" and rows[0]["stance"] == "opposing"
    assert rows[0]["anchor_agent_id"] == 0 and rows[0]["anchor_name"] == "Acme Corp"
    assert rows[1]["entity_type"] == growth.DEFAULT_ROLE_TYPE and rows[1]["age"] is None


def test_a_joiner_may_arrive_for_a_topic_with_no_anchor_and_the_limit_holds():
    rows = growth.parse_accounts({"accounts": [account("Port worker", anchor=None), account("Second"),
                                               account("Third")]}, CAST, limit=2)
    assert [r["name"] for r in rows] == ["Port worker", "Second"]
    assert rows[0]["anchor_agent_id"] is None


def test_hot_threads_rank_posts_by_the_reactions_they_drew():
    actions = [
        {"agent_name": "Jo Lee", "action_type": "CREATE_POST", "action_args": {"content": "We are closing the plant."}},
        {"agent_name": "The Ledger", "action_type": "CREATE_POST", "action_args": {"content": "Quiet day."}},
        {"agent_name": "The Ledger", "action_type": "CREATE_COMMENT", "action_args": {
            "content": "What about the staff?", "post_content": "We are closing the plant.", "post_author_name": "Jo Lee"}},
        {"agent_name": "Acme Corp", "action_type": "LIKE_POST", "action_args": {
            "post_content": "We are closing the plant.", "post_author_name": "Jo Lee"}},
        {"agent_name": "Acme Corp", "action_type": "DO_NOTHING", "action_args": {}},
    ]
    hot = growth.hot_threads(actions)
    assert hot[0]["author"] == "Jo Lee" and hot[0]["reactions"] == 2
    assert hot[0]["replies"] == [{"by": "The Ledger", "text": "What about the staff?"}]
    assert hot[1]["reactions"] == 0


def test_waves_fall_on_a_fixed_rhythm():
    assert [r for r in range(1, 9) if growth.wave_due(r, first=2, every=3)] == [2, 5, 8]


def test_rows_for_the_run_files_carry_origin_and_anchor():
    row = growth.parse_accounts({"accounts": [account("Acme line worker")]}, CAST, limit=1)[0]
    cfg = growth.agent_config_row(row, 7, growth.ORIGIN_JOINED, joined_round=4)
    assert (cfg["agent_id"], cfg["origin"], cfg["joined_round"], cfg["anchor_agent_id"]) == (7, "joined", 4, 0)
    assert cfg["active_hours"] == list(range(24)) and cfg["sentiment_bias"] < 0
    profile = growth.profile_row(row, 7)
    assert profile["user_id"] == 7 and profile["username"] == "acme_line_worker_7" and profile["age"] == 41
    assert {"mbti", "gender", "country", "persona", "bio"} <= set(profile)       # what OASIS reads


def test_a_rerun_starts_from_the_cast_that_was_set_up():
    config = {"agent_configs": [{"agent_id": 0}, {"agent_id": 1, "origin": "circle"}, {"agent_id": 2, "origin": "joined"}]}
    _, removed = growth.split_original(config)
    assert removed == [2] and [c["agent_id"] for c in config["agent_configs"]] == [0, 1]


def test_tree_nests_the_circle_and_joiners_under_their_actor():
    configs = [
        {"entity_name": "Acme Corp", "entity_type": "PublicCompany"},
        {"entity_name": "Acme line worker", "entity_type": "Employee", "origin": "circle",
         "anchor_name": "Acme Corp", "relation": "works for"},
        {"entity_name": "Worker's union rep", "entity_type": "UnionRep", "origin": "joined",
         "anchor_name": "Acme line worker", "joined_round": 4, "why": "The closure post."},
        {"entity_name": "Port worker", "entity_type": "Worker", "origin": "joined", "joined_round": 2},
    ]
    tree = build_cast_tree([{"name": "Acme Corp", "entity_type": "PublicCompany", "ready": True}], [], configs)
    assert tree["total"] == 4 and tree["complete"]
    assert tree["origins"] == {"evidence": 1, "circle": 1, "joined": 2}
    companies = next(g for g in tree["groups"] if g["key"] == "companies")
    acme = companies["types"][0]["agents"][0]
    assert companies["count"] == 3                                   # the actor and the two around it
    assert [(a["name"], a["origin"], a["joined_round"]) for a in acme["circle"]] == [
        ("Acme line worker", "circle", 0), ("Worker's union rep", "joined", 4)]
    public = next(g for g in tree["groups"] if g["key"] == "public")
    assert public["types"][0]["agents"][0]["name"] == "Port worker"  # no anchor: sits in its own group


def test_added_accounts_are_capped_at_a_quarter_of_the_evidence_cast():
    assert growth.cap_for(28, 12) == 7
    assert growth.cap_for(200, 12) == 12        # never above the configured ceiling
    assert growth.cap_for(3, 12) == 2           # a tiny cast still gets a couple
    assert growth.cap_for(28, 0) == 0           # switched off stays off


def test_briefing_says_how_many_voices_were_added_and_how_loud_they_were():
    from app.services.run_briefing import build_briefing_facts

    roster = [
        {"entity_name": "Acme Corp", "entity_type": "PublicCompany"},
        {"entity_name": "Acme line worker", "entity_type": "Employee", "origin": "circle"},
        {"entity_name": "Port worker", "entity_type": "Worker", "origin": "joined"},
    ]
    actions = [
        {"agent_name": "Acme Corp", "action_type": "CREATE_POST", "round_num": 1, "action_args": {"content": "We are closing."}},
        {"agent_name": "Acme Corp", "action_type": "CREATE_POST", "round_num": 2, "action_args": {"content": "More soon."}},
        {"agent_name": "Acme Corp", "action_type": "CREATE_POST", "round_num": 3, "action_args": {"content": "Details."}},
        {"agent_name": "Port worker", "action_type": "CREATE_POST", "round_num": 3, "action_args": {"content": "What about us?"}},
    ]
    cast = build_briefing_facts(actions, roster)["run"]["cast"]
    assert (cast["evidence"], cast["circle"], cast["joined"]) == (1, 1, 1)
    assert cast["added_share_of_posts"] == 0.25 and cast["added_names"] == ["Acme line worker", "Port worker"]
    assert "1 of these voices are named in the evidence" in cast["note"] and "25%" in cast["note"]
    assert build_briefing_facts(actions[:3], roster[:1])["run"]["cast"]["note"] == ""


def test_a_run_starts_when_half_the_cast_is_awake():
    agents = [{"active_hours": [9, 10]}, {"active_hours": [7, 8, 9]}, {"active_hours": [9]}, {"active_hours": [8, 9]}]
    assert growth.first_busy_hour({"agent_configs": agents}) == 8
    assert growth.first_busy_hour({"agent_configs": agents, "time_config": {"start_hour": 19}}) == 19
    assert growth.first_busy_hour({}) == 0


# ------------------------------------------------------------------ the director

def monkey_cap(n):
    """The cast in these tests has three actors; lift the quarter rule so the cap under test is join_max."""
    import agent_spawner
    agent_spawner.growth.ADDED_SHARE = 1 if n else 4       # the runner loads its own copy of the module


@pytest.fixture(autouse=True)
def restore_cap():
    yield
    if "agent_spawner" in sys.modules:
        sys.modules["agent_spawner"].growth.ADDED_SHARE = 4


def director_for(tmp_path, replies, **growth_config):
    import agent_spawner

    config = {
        "simulation_requirement": "Will the plant close?",
        "growth_config": {"join_first_round": 2, "join_every": 2, "join_per_wave": 2, "join_max": 3, **growth_config},
        "agent_configs": [{"agent_id": c["agent_id"], "entity_name": c["name"], "entity_type": c["entity_type"]}
                          for c in CAST],
    }
    monkey_cap(3)
    (tmp_path / "simulation_config.json").write_text(json.dumps(config))
    (tmp_path / "reddit_profiles.json").write_text(json.dumps([{"user_id": c["agent_id"], "name": c["name"]} for c in CAST]))
    calls = []

    async def ask(system, user):
        calls.append(user)
        return json.dumps({"accounts": replies.pop(0)})

    return agent_spawner.SpawnDirector(config, str(tmp_path), log=lambda m: None, ask=ask), config, calls


POST = [{"agent_name": "Jo Lee", "action_type": "CREATE_POST", "action_args": {"content": "We are closing the plant."}}]


def test_director_decides_a_round_once_for_every_platform_and_saves_the_newcomers(tmp_path):
    director, config, calls = director_for(tmp_path, [[account("Acme line worker"), account("Port worker", anchor=None)]])

    async def go():
        assert await director.wave_for(1) == []          # before the first look
        director.observe(POST)
        return await asyncio.gather(director.wave_for(2), director.wave_for(2))

    first, second = asyncio.run(go())
    assert first is second and len(calls) == 1
    assert [w["agent_id"] for w in first] == [3, 4]
    assert [c["entity_name"] for c in config["agent_configs"][3:]] == ["Acme line worker", "Port worker"]
    on_disk = json.loads((tmp_path / "simulation_config.json").read_text())
    assert [c["origin"] for c in on_disk["agent_configs"][3:]] == ["joined", "joined"]
    assert [p["user_id"] for p in json.loads((tmp_path / "reddit_profiles.json").read_text())] == [0, 1, 2, 3, 4]
    report = json.loads((tmp_path / growth.GROWTH_FILE).read_text())
    assert [j["joined_round"] for j in report["joined"]] == [2, 2]


def test_director_stops_at_the_cap_and_stays_quiet_when_nothing_happened(tmp_path):
    director, config, calls = director_for(
        tmp_path, [[account("One"), account("Two")], [account("Three"), account("Four")]])

    async def go():
        director.observe(POST)
        a = await director.wave_for(2)
        b = await director.wave_for(4)                   # nothing was posted since: no model call
        director.observe(POST)
        c = await director.wave_for(6)                   # one place left under the cap of 3
        director.observe(POST)
        d = await director.wave_for(8)
        return a, b, c, d

    a, b, c, d = asyncio.run(go())
    assert (len(a), len(b), len(c), len(d)) == (2, 0, 1, 0)
    assert len(calls) == 2 and len(config["agent_configs"]) == 6


def test_director_survives_a_bad_model_reply_and_resets_on_a_rerun(tmp_path):
    director, config, _ = director_for(tmp_path, [[account("One")]])

    async def broken(system, user):
        return "sorry, no JSON"

    director._ask = broken
    director.observe(POST)
    assert asyncio.run(director.wave_for(2)) == []

    # A second run of the same simulation: last run's joiners are in the files and must go.
    config["agent_configs"].append({"agent_id": 3, "entity_name": "Old joiner", "origin": "joined"})
    (tmp_path / "simulation_config.json").write_text(json.dumps(config))
    (tmp_path / "reddit_profiles.json").write_text(json.dumps([{"user_id": i} for i in range(4)]))
    import agent_spawner
    agent_spawner.SpawnDirector(config, str(tmp_path), log=lambda m: None)
    assert [c["agent_id"] for c in config["agent_configs"]] == [0, 1, 2]
    assert [p["user_id"] for p in json.loads((tmp_path / "reddit_profiles.json").read_text())] == [0, 1, 2]
    assert len(json.loads((tmp_path / "simulation_config.json").read_text())["agent_configs"]) == 3


def test_a_newcomer_is_registered_on_a_live_platform_and_follows_its_anchor(tmp_path, monkeypatch):
    """Against the real OASIS platform: sign-up and the follow edge after the run has started."""
    oasis = pytest.importorskip("oasis")
    import sqlite3
    from camel.models import ModelFactory
    from camel.types import ModelPlatformType

    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-used")
    model = ModelFactory.create(model_platform=ModelPlatformType.OPENAI, model_type="gpt-4o-mini")
    profiles = [{"user_id": i, "username": f"u{i}", "name": c["name"], "bio": "b", "persona": "p",
                 "age": 30, "gender": "other", "mbti": "ISTJ", "country": ""} for i, c in enumerate(CAST)]
    (tmp_path / "start.json").write_text(json.dumps(profiles))
    director, config, _ = director_for(tmp_path, [[account("Acme line worker")]])
    config["agent_configs"].append({"agent_id": 3, "entity_name": "Setup circle", "origin": "circle", "anchor_agent_id": 1})
    profiles.append({**profiles[0], "user_id": 3, "username": "u3", "name": "Setup circle"})
    (tmp_path / "start.json").write_text(json.dumps(profiles))
    db = str(tmp_path / "reddit.db")

    async def go():
        graph = await oasis.generate_reddit_agent_graph(
            profile_path=str(tmp_path / "start.json"), model=model, available_actions=[oasis.ActionType.DO_NOTHING])
        env = oasis.make(agent_graph=graph, platform=oasis.DefaultPlatformType.REDDIT, database_path=db)
        await env.reset()
        assert await director.apply_circle_follows(env, "reddit") == 1
        director.observe(POST)
        wave = await director.wave_for(2)
        names = {}
        joined = await director.join(env, "reddit", wave, model, [oasis.ActionType.DO_NOTHING], names)
        await env.close()
        return joined, names

    joined, names = asyncio.run(go())
    assert [agent_id for agent_id, _ in joined] == [4] and names == {4: "Acme line worker"}
    con = sqlite3.connect(db)
    assert con.execute("SELECT COUNT(*) FROM user").fetchone()[0] == 5
    assert con.execute("SELECT name FROM user WHERE user_id = 4").fetchone()[0] == "acme_line_worker_4"
    assert set(con.execute("SELECT follower_id, followee_id FROM follow").fetchall()) == {(3, 1), (4, 0)}
