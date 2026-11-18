"""The cast tree: grouping, progress while agents are spun up, and the sidecar file."""

import json

from app.services.oasis_profile_generator import CAST_PROGRESS_FILE, OasisAgentProfile, OasisProfileGenerator
from app.services.run_cast import build_cast_tree
from app.services.zep_entity_reader import EntityNode


def test_tree_groups_by_reader_group_then_type_and_counts_progress():
    tree = build_cast_tree(
        [
            {"name": "Acme", "entity_type": "PublicCompany", "ready": True},
            {"name": "Jo Lee", "entity_type": "CompanyExecutive", "ready": False},
            {"name": "The Ledger", "entity_type": "MediaOutlet", "ready": True},
            {"name": "", "entity_type": "MediaOutlet", "ready": True},
        ],
        [{"name": "Acme", "gender": "other", "profession": "Retailer", "bio": "x" * 400}],
        [{"entity_name": "Acme", "stance": "supportive", "activity_level": 0.4}],
    )
    assert (tree["total"], tree["ready"], tree["complete"]) == (3, 2, False)
    assert [g["key"] for g in tree["groups"]] == ["media", "companies"]
    companies = tree["groups"][1]
    assert (companies["count"], companies["ready"]) == (2, 1)
    assert [t["label"] for t in companies["types"]] == ["Company executive", "Public company"]
    acme = companies["types"][1]["agents"][0]
    assert acme["kind"] == "organisation" and acme["stance"] == "supportive"
    assert len(acme["bio"]) == 181
    assert companies["types"][0]["agents"][0]["kind"] is None      # persona not written yet


def test_profile_generation_writes_the_planned_cast_and_progress(tmp_path):
    gen = OasisProfileGenerator.__new__(OasisProfileGenerator)
    gen.graph_id = None
    gen.generate_profile_from_entity = lambda entity, user_id, use_llm: OasisAgentProfile(
        user_id=user_id, user_name=f"u{user_id}", name=entity.name, bio="b", persona="p")
    gen._print_generated_profile = lambda *a, **k: None
    entities = [
        EntityNode(uuid="1", name="Acme", labels=["Entity", "PublicCompany"], summary="", attributes={}),
        EntityNode(uuid="2", name="Jo Lee", labels=["Entity", "Person"], summary="", attributes={}),
    ]
    gen.generate_profiles_from_entities(
        entities, use_llm=False, parallel_count=1,
        realtime_output_path=str(tmp_path / "reddit_profiles.json"),
    )
    rows = json.loads((tmp_path / CAST_PROGRESS_FILE).read_text())
    assert [(r["name"], r["entity_type"], r["ready"]) for r in rows] == [
        ("Acme", "PublicCompany", True), ("Jo Lee", "Person", True)]
