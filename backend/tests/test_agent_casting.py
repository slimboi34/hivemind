"""How agents are cast: person vs organisation personas, and who posts the opening posts."""

from app.services.oasis_profile_generator import OasisProfileGenerator
from app.services.simulation_config_generator import (
    AgentActivityConfig,
    EventConfig,
    SimulationConfigGenerator,
)


def test_person_types_are_recognised_by_their_head_noun():
    gen = OasisProfileGenerator.__new__(OasisProfileGenerator)
    for person in ("Person", "GovernmentOfficial", "GovernmentPolitician", "ExecutiveFigure",
                   "NvidiaExecutive", "SocialMediaInfluencer", "SellSideAnalyst", "student", "publicfigure"):
        assert gen._is_individual_entity(person), person
    for org in ("PublicCompany", "TechCompany", "MediaOutlet", "FinancialMediaOutlet", "RegulatoryAgency",
                "GovernmentAgency", "LegislativeCommittee", "InvestmentAnalystFirm", "LegalFirm",
                "LegalRegulatoryBody", "Organization", "", None):
        assert not gen._is_individual_entity(org), org


def test_person_prompt_lets_the_model_fall_back_to_an_organisation_account():
    gen = OasisProfileGenerator.__new__(OasisProfileGenerator)
    prompt = gen._build_individual_persona_prompt("Wedbush", "SellSideAnalyst", "A brokerage.", {}, "")
    assert '"other"' in prompt
    for build in (gen._build_individual_persona_prompt, gen._build_group_persona_prompt):
        assert "Chinese" not in build("X", "Person", "", {}, "")    # country follows the run's language


def agent(agent_id, name, entity_type, influence=1.0):
    return AgentActivityConfig(agent_id=agent_id, entity_uuid=f"u{agent_id}", entity_name=name,
                               entity_type=entity_type, influence_weight=influence)


CAST = [
    agent(0, "Ron Wyden", "GovernmentOfficial"),
    agent(1, "Chuck Schumer", "GovernmentOfficial"),
    agent(2, "Donald Trump", "GovernmentOfficial", influence=3.0),
    agent(3, "Axios", "MediaOutlet"),
]


def assign(posts):
    gen = SimulationConfigGenerator.__new__(SimulationConfigGenerator)
    event = gen._assign_initial_post_agents(EventConfig(initial_posts=posts), CAST)
    return [(p["poster_agent_id"], p["matched_by"]) for p in event.initial_posts]


def test_opening_posts_go_to_the_named_account():
    assert assign([
        {"content": "I had no idea.", "poster_name": "Donald Trump", "poster_type": "GovernmentOfficial"},
        {"content": "We are opening a probe.", "poster_name": "  ron  wyden ", "poster_type": "GovernmentOfficial"},
        {"content": "Reporting says...", "poster_name": "Axios", "poster_type": "MediaOutlet"},
    ]) == [(2, "name"), (0, "name"), (3, "name")]


def test_unknown_or_missing_name_falls_back_to_type_then_influence():
    assert assign([
        {"content": "a", "poster_name": "Nobody Here", "poster_type": "GovernmentOfficial"},
        {"content": "b", "poster_type": "GovernmentOfficial"},        # older configs have no name
        {"content": "c", "poster_name": None, "poster_type": "Martian"},
    ]) == [(0, "type"), (1, "type"), (2, "fallback")]


class _Resp:
    def __init__(self, text):
        msg = type("M", (), {"content": text})()
        self.choices = [type("C", (), {"message": msg, "finish_reason": "stop"})()]


def test_fenced_json_keeps_every_persona_field(monkeypatch):
    """A ```json fence used to send the reply down the salvage path, which kept
    only bio and persona and dropped age, gender, country and the rest."""
    from app.services import oasis_profile_generator as mod

    fenced = '```json\n{"bio": "Senator.", "persona": "A senator.", "age": 76, "gender": "male", "country": "United States", "profession": "Senator"}\n```'
    monkeypatch.setattr(mod, "create_chat_completion", lambda *a, **k: _Resp(fenced))
    gen = OasisProfileGenerator.__new__(OasisProfileGenerator)
    gen.client, gen.model_name = None, "m"
    out = gen._generate_profile_with_llm("Ron Wyden", "GovernmentOfficial", "US Senator.", {}, "")
    assert (out["age"], out["gender"], out["country"], out["profession"]) == (76, "male", "United States", "Senator")


def test_fenced_json_config_is_parsed(monkeypatch):
    from app.services import simulation_config_generator as mod

    monkeypatch.setattr(mod, "create_chat_completion", lambda *a, **k: _Resp('```json\n{"hot_topics": ["x"]}\n```'))
    gen = SimulationConfigGenerator.__new__(SimulationConfigGenerator)
    gen.client, gen.model_name = None, "m"
    assert gen._call_llm_with_retry("p", "s") == {"hot_topics": ["x"]}
