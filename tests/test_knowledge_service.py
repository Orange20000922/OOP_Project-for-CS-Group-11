from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.models.note import Note, NoteChunk
from app.services.knowledge_service import KnowledgeService
from app.storage.note_store import NoteStore


@pytest.fixture
def note_store(tmp_path):
    return NoteStore(db_path=tmp_path / "test.db")


@pytest.fixture
def knowledge_service(note_store):
    return KnowledgeService(note_store)


@pytest.fixture
def sample_chunks():
    return [
        NoteChunk(chunk_id="c1", note_id="n1", heading="多态", content="多态是面向对象的核心概念", chunk_index=0),
        NoteChunk(chunk_id="c2", note_id="n1", heading="继承", content="继承允许子类复用父类方法", chunk_index=1),
        NoteChunk(chunk_id="c3", note_id="n1", heading="", content="", chunk_index=2),  # empty, should be skipped
    ]


class TestIndexChunks:
    def test_index_calls_memory_add(self, knowledge_service: KnowledgeService, sample_chunks):
        mock_memory = MagicMock()
        knowledge_service._memory = mock_memory

        count = knowledge_service.index_chunks("stu1", sample_chunks)
        assert count == 2  # empty chunk skipped
        assert mock_memory.add.call_count == 2

        first_call = mock_memory.add.call_args_list[0]
        assert first_call.kwargs["user_id"] == "stu1"
        assert first_call.kwargs["metadata"]["chunk_id"] == "c1"

    def test_index_fails_without_memory(self, knowledge_service: KnowledgeService, sample_chunks):
        knowledge_service._memory_failed = True
        with pytest.raises(RuntimeError, match="不可用"):
            knowledge_service.index_chunks("stu1", sample_chunks)


class TestSearch:
    def test_search_returns_results(self, knowledge_service: KnowledgeService, note_store: NoteStore):
        # Add a note for title lookup
        note_store.add_note(Note(
            id="n1", student_id="stu1", filename="a.pdf", file_type="pdf",
            title="OOP笔记", created_at="2026-01-01", updated_at="2026-01-01",
        ))

        mock_memory = MagicMock()
        mock_memory.search.return_value = [
            {
                "memory": "多态是面向对象的核心概念",
                "score": 0.92,
                "metadata": {"chunk_id": "c1", "note_id": "n1", "heading": "多态"},
            }
        ]
        knowledge_service._memory = mock_memory

        results = knowledge_service.search("stu1", "什么是多态")
        assert len(results) == 1
        assert results[0].score == 0.92
        assert results[0].note_title == "OOP笔记"
        assert results[0].chunk.heading == "多态"

    def test_search_fails_without_memory(self, knowledge_service: KnowledgeService):
        knowledge_service._memory_failed = True
        with pytest.raises(RuntimeError, match="不可用"):
            knowledge_service.search("stu1", "query")


class TestAsk:
    def test_ask_with_llm(self, knowledge_service: KnowledgeService):
        # Mock memory for search
        mock_memory = MagicMock()
        mock_memory.search.return_value = [
            {
                "memory": "多态是OOP核心",
                "score": 0.9,
                "metadata": {"chunk_id": "c1", "note_id": "n1", "heading": "多态"},
            }
        ]
        knowledge_service._memory = mock_memory

        # Mock LLM
        mock_llm = MagicMock()
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "多态允许不同类型通过统一接口调用。"
        mock_llm.chat.completions.create.return_value = mock_resp
        knowledge_service._llm_client = mock_llm

        answer, sources = knowledge_service.ask("stu1", "什么是多态")
        assert "多态" in answer
        assert len(sources) == 1

        # Verify prompt contains context
        call_args = mock_llm.chat.completions.create.call_args
        prompt_content = call_args.kwargs["messages"][0]["content"]
        assert "多态是OOP核心" in prompt_content
        assert "什么是多态" in prompt_content

    def test_ask_without_llm_returns_raw_results(self, knowledge_service: KnowledgeService):
        mock_memory = MagicMock()
        mock_memory.search.return_value = [
            {"memory": "内容A", "score": 0.8, "metadata": {"chunk_id": "c1", "note_id": "n1", "heading": "标题"}},
        ]
        knowledge_service._memory = mock_memory
        knowledge_service._llm_failed = True

        answer, sources = knowledge_service.ask("stu1", "问题")
        assert "LLM 不可用" in answer
        assert "内容A" in answer


class TestGenerateSummary:
    def test_with_llm(self, knowledge_service: KnowledgeService, sample_chunks):
        mock_llm = MagicMock()
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = '{"title": "OOP笔记", "summary": "关于多态和继承的笔记"}'
        mock_llm.chat.completions.create.return_value = mock_resp
        knowledge_service._llm_client = mock_llm

        result = knowledge_service.generate_summary(sample_chunks)
        assert result["title"] == "OOP笔记"
        assert "多态" in result["summary"]

    def test_without_llm_fallback(self, knowledge_service: KnowledgeService, sample_chunks):
        knowledge_service._llm_failed = True

        result = knowledge_service.generate_summary(sample_chunks)
        assert result["title"] == "多态"  # first heading
        assert "面向对象" in result["summary"]

    def test_invalid_json_from_llm(self, knowledge_service: KnowledgeService, sample_chunks):
        mock_llm = MagicMock()
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "这不是JSON"
        mock_llm.chat.completions.create.return_value = mock_resp
        knowledge_service._llm_client = mock_llm

        result = knowledge_service.generate_summary(sample_chunks)
        assert result["title"] == ""
        assert "这不是JSON" in result["summary"]
