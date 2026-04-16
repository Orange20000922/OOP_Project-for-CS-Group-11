from __future__ import annotations

import pytest

from app.models.note import Note, NoteChunk
from app.storage.note_store import NoteStore


@pytest.fixture
def note_store(tmp_path):
    return NoteStore(db_path=tmp_path / "test_notes.db")


@pytest.fixture
def sample_note() -> Note:
    return Note(
        id="note-001",
        student_id="20250001",
        course_id="course-1",
        filename="test.pdf",
        file_type="pdf",
        title="测试笔记",
        summary="这是一份测试笔记",
        chunk_count=2,
        created_at="2026-04-16T10:00:00",
        updated_at="2026-04-16T10:00:00",
    )


@pytest.fixture
def sample_chunks() -> list[NoteChunk]:
    return [
        NoteChunk(chunk_id="chunk-001", note_id="note-001", heading="第一章", content="内容一", chunk_index=0),
        NoteChunk(chunk_id="chunk-002", note_id="note-001", heading="第二章", content="内容二", chunk_index=1),
    ]


class TestNoteStoreCRUD:
    def test_add_and_get(self, note_store: NoteStore, sample_note: Note):
        note_store.add_note(sample_note)
        got = note_store.get_note("note-001")
        assert got is not None
        assert got.id == "note-001"
        assert got.title == "测试笔记"
        assert got.student_id == "20250001"

    def test_get_nonexistent(self, note_store: NoteStore):
        assert note_store.get_note("no-such-id") is None

    def test_list_by_student(self, note_store: NoteStore, sample_note: Note):
        note_store.add_note(sample_note)
        note2 = sample_note.model_copy(update={"id": "note-002", "course_id": "course-2", "filename": "b.pdf"})
        note_store.add_note(note2)

        all_notes = note_store.list_by_student("20250001")
        assert len(all_notes) == 2

        filtered = note_store.list_by_student("20250001", course_id="course-1")
        assert len(filtered) == 1
        assert filtered[0].id == "note-001"

    def test_list_empty(self, note_store: NoteStore):
        assert note_store.list_by_student("nobody") == []

    def test_update_note(self, note_store: NoteStore, sample_note: Note):
        note_store.add_note(sample_note)
        updated = sample_note.model_copy(update={"title": "新标题", "summary": "新摘要", "updated_at": "2026-04-16T12:00:00"})
        note_store.update_note(updated)

        got = note_store.get_note("note-001")
        assert got is not None
        assert got.title == "新标题"
        assert got.summary == "新摘要"

    def test_delete_note(self, note_store: NoteStore, sample_note: Note):
        note_store.add_note(sample_note)
        note_store.delete_note("note-001")
        assert note_store.get_note("note-001") is None


class TestNoteStoreChunks:
    def test_add_and_get_chunks(self, note_store: NoteStore, sample_note: Note, sample_chunks: list[NoteChunk]):
        note_store.add_note(sample_note)
        note_store.add_chunks(sample_chunks)

        chunks = note_store.get_chunks_by_note("note-001")
        assert len(chunks) == 2
        assert chunks[0].heading == "第一章"
        assert chunks[1].chunk_index == 1

    def test_delete_chunks(self, note_store: NoteStore, sample_note: Note, sample_chunks: list[NoteChunk]):
        note_store.add_note(sample_note)
        note_store.add_chunks(sample_chunks)
        note_store.delete_chunks_by_note("note-001")
        assert note_store.get_chunks_by_note("note-001") == []

    def test_cascade_delete(self, note_store: NoteStore, sample_note: Note, sample_chunks: list[NoteChunk]):
        note_store.add_note(sample_note)
        note_store.add_chunks(sample_chunks)
        note_store.delete_note("note-001")
        assert note_store.get_chunks_by_note("note-001") == []

    def test_add_empty_chunks(self, note_store: NoteStore):
        note_store.add_chunks([])  # should not raise
