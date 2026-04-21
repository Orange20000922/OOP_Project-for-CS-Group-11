from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from app.models.knowledge import KnowledgeTopicCreate
from app.models.note import Note, NoteChunk
from app.services.knowledge_service import KnowledgeService
from app.storage.knowledge_tree_store import KnowledgeTreeStore
from app.storage.note_store import NoteStore


def make_service(tmp_path):
    note_store = NoteStore(db_path=tmp_path / "notes.db")
    tree_store = KnowledgeTreeStore(root_dir=tmp_path / "knowledge_trees")
    service = KnowledgeService(note_store, tree_store=tree_store)
    service._topic_store = MagicMock()
    return service, note_store


def test_create_topic_and_assign_note(tmp_path):
    service, note_store = make_service(tmp_path)

    note_store.add_note(
        Note(
            id="n1",
            student_id="stu1",
            course_id="c1",
            filename="oop.pdf",
            file_type="pdf",
            title="Object Oriented Programming",
            summary="Classes and objects",
            created_at="2026-04-17T10:00:00",
            updated_at="2026-04-17T10:00:00",
        )
    )

    tree = service.create_topic(
        "stu1",
        KnowledgeTopicCreate(course_id="c1", name="OOP", keywords=["class", "object"]),
    )
    topic_id = tree.root_ids[0]

    tree = service.assign_note_to_topic("stu1", "c1", topic_id, "n1")

    assert tree.course_id == "c1"
    assert tree.topics[topic_id].note_ids == ["n1"]
    assert service.get_tree("stu1", "c1").topics[topic_id].note_ids == ["n1"]


def test_build_graph_routes_by_query_to_topic_candidates(tmp_path):
    service, note_store = make_service(tmp_path)

    note_store.add_note(
        Note(
            id="n1",
            student_id="stu1",
            course_id="c1",
            filename="oop.pdf",
            file_type="pdf",
            title="Polymorphism",
            summary="Dynamic dispatch and interface design",
            created_at="2026-04-17T10:00:00",
            updated_at="2026-04-17T10:00:00",
        )
    )
    note_store.add_note(
        Note(
            id="n2",
            student_id="stu1",
            course_id="c1",
            filename="inheritance.pdf",
            file_type="pdf",
            title="Inheritance",
            summary="Base class and derived class",
            created_at="2026-04-17T10:05:00",
            updated_at="2026-04-17T10:05:00",
        )
    )
    note_store.add_chunks(
        [
            NoteChunk(chunk_id="c1", note_id="n1", heading="Polymorphism", content="virtual call", chunk_index=0),
            NoteChunk(chunk_id="c2", note_id="n2", heading="Inheritance", content="derived class", chunk_index=0),
        ]
    )

    tree = service.create_topic(
        "stu1",
        KnowledgeTopicCreate(course_id="c1", name="Polymorphism", keywords=["virtual", "dispatch"]),
    )
    topic_a = tree.root_ids[0]
    tree = service.create_topic(
        "stu1",
        KnowledgeTopicCreate(course_id="c1", name="Inheritance", keywords=["derived", "base"]),
    )
    topic_b = [topic_id for topic_id in tree.root_ids if topic_id != topic_a][0]

    service.assign_note_to_topic("stu1", "c1", topic_a, "n1")
    service.assign_note_to_topic("stu1", "c1", topic_b, "n2")

    mock_topic_store = MagicMock()
    mock_topic_store.search_topics.return_value = [(topic_b, 0.92)]
    mock_memory = MagicMock()
    mock_memory.search.return_value = [
        {"memory": "derived class", "score": 1.0, "metadata": {"chunk_id": "c2", "note_id": "n2", "heading": "Inheritance"}},
    ]
    service._topic_store = mock_topic_store
    service._memory = mock_memory

    graph = service.build_graph(
        student_id="stu1",
        course_id="c1",
        query="how does inheritance work",
        top_k=1,
        min_score=0.5,
        max_nodes=10,
        topic_limit=1,
    )

    assert graph.routing_applied is True
    assert graph.selected_topic_ids == [topic_b]
    assert graph.total_nodes == 1
    assert {node.id for node in graph.nodes} == {"c2"}
    assert graph.nodes[0].topic_id == topic_b
    assert graph.total_links == 0
    assert mock_topic_store.search_topics.call_count == 1
    assert mock_memory.search.call_count == 1


def test_tree_endpoint_returns_tree(monkeypatch: pytest.MonkeyPatch):
    pytest.importorskip("fastapi.testclient")
    from fastapi.testclient import TestClient

    import app.main as main_module
    import app.routers.knowledge as knowledge_router
    from app.models.knowledge import KnowledgeTree

    class AuthStub:
        def get_student_id(self, session_token):
            if session_token == "ok-token":
                return "stu1"
            raise PermissionError("not logged in")

    class KnowledgeStub:
        def __init__(self):
            self.calls = []

        def get_tree(self, student_id, course_id):
            self.calls.append((student_id, course_id))
            return KnowledgeTree(student_id=student_id, course_id=course_id)

    auth_stub = AuthStub()
    knowledge_stub = KnowledgeStub()
    monkeypatch.setattr(knowledge_router, "auth_service", auth_stub)
    monkeypatch.setattr(knowledge_router, "knowledge_service", knowledge_stub)

    with TestClient(main_module.app) as client:
        client.cookies.set("session_token", "ok-token")
        response = client.get("/knowledge/tree", params={"course_id": "c1"})

    assert response.status_code == 200
    assert response.json()["student_id"] == "stu1"
    assert response.json()["course_id"] == "c1"
    assert knowledge_stub.calls == [("stu1", "c1")]
