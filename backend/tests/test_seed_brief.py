"""Starting a run from a question alone, or from pasted text."""

import io

import pytest

from app import create_app
from app.api import graph as graph_api
from app.models.project import ProjectManager
from app.services import seed_brief


class FakeGenerator:
    seen = None

    def generate(self, **kwargs):
        FakeGenerator.seen = kwargs
        return {"entity_types": [], "edge_types": [], "analysis_summary": "ok"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(ProjectManager, "PROJECTS_DIR", str(tmp_path))
    monkeypatch.setattr(graph_api, "OntologyGenerator", FakeGenerator)
    FakeGenerator.seen = None
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def post(client, **data):
    return client.post("/api/graph/ontology/generate", data=data, content_type="multipart/form-data")


def test_question_alone_gets_a_generated_brief(client, monkeypatch):
    monkeypatch.setattr(graph_api, "write_seed_brief", lambda q: f"# Background brief\n\nAbout: {q}\n" + "Actors. " * 40)
    res = post(client, simulation_requirement="How will banks react to a rate cut?")
    assert res.status_code == 200
    data = res.json["data"]
    assert data["seed_source"] == "brief"
    assert [f["filename"] for f in data["files"]] == [seed_brief.BRIEF_FILENAME]
    assert "rate cut" in FakeGenerator.seen["document_texts"][0]


def test_pasted_text_is_used_as_the_seed(client, monkeypatch):
    monkeypatch.setattr(graph_api, "write_seed_brief", lambda q: pytest.fail("no brief needed"))
    res = post(client, simulation_requirement="How will staff react?", seed_text="Memo: the office closes in March.")
    assert res.status_code == 200
    assert res.json["data"]["seed_source"] == "pasted"
    assert FakeGenerator.seen["document_texts"] == ["Memo: the office closes in March."]


def test_files_and_pasted_text_combine(client, monkeypatch):
    monkeypatch.setattr(graph_api, "write_seed_brief", lambda q: pytest.fail("no brief needed"))
    res = post(client, simulation_requirement="Q?", seed_text="Extra notes.",
               files=(io.BytesIO(b"A short source document."), "source.md"))
    assert res.status_code == 200
    assert res.json["data"]["seed_source"] == "documents"
    assert len(FakeGenerator.seen["document_texts"]) == 2


def test_unreadable_upload_is_an_error_not_a_silent_brief(client, monkeypatch):
    monkeypatch.setattr(graph_api, "write_seed_brief", lambda q: pytest.fail("must not replace the user's file"))
    res = post(client, simulation_requirement="Q?", files=(io.BytesIO(b"x"), "photo.png"))
    assert res.status_code == 400


def test_question_is_still_required(client):
    assert post(client, seed_text="Some notes.").status_code == 400


def test_brief_carries_the_question_and_a_provenance_note():
    class LLM:
        def chat(self, messages, **kwargs):
            assert "QUESTION:" in messages[1]["content"]
            return "## Situation\n" + "Something is happening. " * 20

    brief = seed_brief.write_seed_brief("  What happens next?  ", llm_client=LLM())
    assert "Question: What happens next?" in brief
    assert "may be out of date" in brief
    assert "## Situation" in brief

    class Empty:
        def chat(self, messages, **kwargs):
            return "Sorry."

    with pytest.raises(ValueError):
        seed_brief.write_seed_brief("Q?", llm_client=Empty())
