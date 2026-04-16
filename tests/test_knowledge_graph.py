from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from app.models.note import GraphResponse, Note, NoteChunk
from app.services.knowledge_service import KnowledgeService
from app.storage.note_store import NoteStore


@pytest.fixture
def note_store(tmp_path):
    return NoteStore(db_path=tmp_path / "notes.db")


@pytest.fixture
def knowledge_service(note_store):
    return KnowledgeService(note_store)


def test_build_graph_uses_top_k_and_deduplicates_links(
    knowledge_service: KnowledgeService,
    note_store: NoteStore,
):
    note_store.add_note(
        Note(
            id="n1",
            student_id="stu1",
            course_id="c1",
            filename="oop.pdf",
            file_type="pdf",
            title="OOP 笔记",
            created_at="2026-04-16T10:00:00",
            updated_at="2026-04-16T10:00:00",
        )
    )
    note_store.add_chunks(
        [
            NoteChunk(chunk_id="c1", note_id="n1", heading="多态", content="多态", chunk_index=0),
            NoteChunk(chunk_id="c2", note_id="n1", heading="继承", content="继承", chunk_index=1),
            NoteChunk(chunk_id="c3", note_id="n1", heading="封装", content="封装", chunk_index=2),
        ]
    )

    mock_memory = MagicMock()
    mock_memory.search.side_effect = [
        [
            {"memory": "多态", "score": 1.0, "metadata": {"chunk_id": "c1", "note_id": "n1", "heading": "多态"}},
            {"memory": "继承", "score": 0.91, "metadata": {"chunk_id": "c2", "note_id": "n1", "heading": "继承"}},
            {"memory": "封装", "score": 0.88, "metadata": {"chunk_id": "c3", "note_id": "n1", "heading": "封装"}},
        ],
        [
            {"memory": "继承", "score": 1.0, "metadata": {"chunk_id": "c2", "note_id": "n1", "heading": "继承"}},
            {"memory": "多态", "score": 0.89, "metadata": {"chunk_id": "c1", "note_id": "n1", "heading": "多态"}},
            {"memory": "封装", "score": 0.80, "metadata": {"chunk_id": "c3", "note_id": "n1", "heading": "封装"}},
        ],
        [
            {"memory": "封装", "score": 1.0, "metadata": {"chunk_id": "c3", "note_id": "n1", "heading": "封装"}},
            {"memory": "多态", "score": 0.87, "metadata": {"chunk_id": "c1", "note_id": "n1", "heading": "多态"}},
            {"memory": "继承", "score": 0.79, "metadata": {"chunk_id": "c2", "note_id": "n1", "heading": "继承"}},
        ],
    ]
    knowledge_service._memory = mock_memory

    graph = knowledge_service.build_graph(
        student_id="stu1",
        course_id="c1",
        top_k=1,
        min_score=0.85,
        max_nodes=10,
    )

    assert isinstance(graph, GraphResponse)
    assert graph.total_nodes == 3
    assert graph.total_links == 2
    assert {node.id for node in graph.nodes} == {"c1", "c2", "c3"}
    assert {(link.source, link.target) for link in graph.links} == {
        ("c1", "c2"),
        ("c1", "c3"),
    }
    assert all(link.value >= 0.85 for link in graph.links)


def test_build_graph_respects_max_nodes(
    knowledge_service: KnowledgeService,
    note_store: NoteStore,
):
    note_store.add_note(
        Note(
            id="n1",
            student_id="stu1",
            course_id="c1",
            filename="oop.pdf",
            file_type="pdf",
            title="OOP 笔记",
            created_at="2026-04-16T10:00:00",
            updated_at="2026-04-16T10:00:00",
        )
    )
    note_store.add_chunks(
        [
            NoteChunk(chunk_id="c1", note_id="n1", heading="多态", content="多态", chunk_index=0),
            NoteChunk(chunk_id="c2", note_id="n1", heading="继承", content="继承", chunk_index=1),
            NoteChunk(chunk_id="c3", note_id="n1", heading="封装", content="封装", chunk_index=2),
        ]
    )

    mock_memory = MagicMock()
    mock_memory.search.side_effect = [
        [
            {"memory": "多态", "score": 1.0, "metadata": {"chunk_id": "c1", "note_id": "n1", "heading": "多态"}},
            {"memory": "继承", "score": 0.90, "metadata": {"chunk_id": "c2", "note_id": "n1", "heading": "继承"}},
        ],
        [
            {"memory": "继承", "score": 1.0, "metadata": {"chunk_id": "c2", "note_id": "n1", "heading": "继承"}},
            {"memory": "多态", "score": 0.90, "metadata": {"chunk_id": "c1", "note_id": "n1", "heading": "多态"}},
        ],
    ]
    knowledge_service._memory = mock_memory

    graph = knowledge_service.build_graph(
        student_id="stu1",
        top_k=1,
        min_score=0.5,
        max_nodes=2,
    )

    assert graph.truncated is True
    assert graph.total_nodes == 2
    assert {node.id for node in graph.nodes} == {"c1", "c2"}
    assert graph.total_links == 1


def test_graph_endpoint_returns_graph(monkeypatch: pytest.MonkeyPatch, tmp_path):
    pytest.importorskip("fastapi.testclient")
    from fastapi.testclient import TestClient
    import app.main as main_module
    import app.routers.knowledge as knowledge_router

    data_dir = tmp_path / "data"
    logs_dir = data_dir / "logs"
    schedules_dir = data_dir / "schedules"
    note_files_dir = data_dir / "note_files"
    users_file = data_dir / "users.json"

    monkeypatch.setattr(main_module, "DATA_DIR", data_dir)
    monkeypatch.setattr(main_module, "LOGS_DIR", logs_dir)
    monkeypatch.setattr(main_module, "APP_LOG_FILE", logs_dir / "app.log")
    monkeypatch.setattr(main_module, "SCHEDULES_DIR", schedules_dir)
    monkeypatch.setattr(main_module, "NOTE_FILES_DIR", note_files_dir)
    monkeypatch.setattr(main_module, "USERS_FILE", users_file)

    class AuthStub:
        def get_student_id(self, session_token):
            if session_token == "ok-token":
                return "stu1"
            raise PermissionError("未登录")

    class KnowledgeStub:
        def __init__(self):
            self.calls = []

        def build_graph(self, **kwargs):
            self.calls.append(kwargs)
            return GraphResponse(
                nodes=[
                    {
                        "id": "c1",
                        "label": "多态",
                        "group": "n1",
                        "note_id": "n1",
                        "note_title": "OOP 笔记",
                        "chunk_index": 0,
                        "content_preview": "多态",
                    }
                ],
                links=[],
                top_k=kwargs["top_k"],
                min_score=kwargs["min_score"],
                course_id=kwargs["course_id"],
                total_nodes=1,
                total_links=0,
                truncated=False,
            )

    auth_stub = AuthStub()
    knowledge_stub = KnowledgeStub()
    monkeypatch.setattr(knowledge_router, "auth_service", auth_stub)
    monkeypatch.setattr(knowledge_router, "knowledge_service", knowledge_stub)

    with TestClient(main_module.app) as client:
        client.cookies.set("session_token", "ok-token")
        response = client.get(
            "/knowledge/graph",
            params={
                "course_id": "c1",
                "top_k": 2,
                "min_score": 0.65,
                "max_nodes": 50,
            },
        )

    assert response.status_code == 200
    assert response.json()["total_nodes"] == 1
    assert knowledge_stub.calls == [
        {
            "student_id": "stu1",
            "course_id": "c1",
            "top_k": 2,
            "min_score": 0.65,
            "max_nodes": 50,
            "query": "",
            "topic_id": None,
            "topic_limit": 3,
        }
    ]
