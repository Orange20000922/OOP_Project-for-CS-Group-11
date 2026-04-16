from __future__ import annotations

import sys

import pytest

from app.models.note import NoteChunk
from app.services.note_service import (
    NoteService,
    _is_heading,
    chunk_text,
)
from app.storage.note_store import NoteStore

_note_svc_mod = sys.modules["app.services.note_service"]


@pytest.fixture
def note_store(tmp_path):
    return NoteStore(db_path=tmp_path / "test.db")


@pytest.fixture
def note_service(tmp_path, note_store, monkeypatch):
    monkeypatch.setattr(_note_svc_mod, "NOTE_FILES_DIR", tmp_path / "note_files")
    return NoteService(note_store)


class TestHeadingDetection:
    def test_markdown_heading(self):
        assert _is_heading("# 第一章 概述")
        assert _is_heading("## 二、方法")

    def test_chinese_chapter(self):
        assert _is_heading("第一章")
        assert _is_heading("第3节")

    def test_numbered(self):
        assert _is_heading("1. 概述")
        assert _is_heading("2 方法论")

    def test_chinese_numbering(self):
        assert _is_heading("一、概述")
        assert _is_heading("三、总结")

    def test_not_heading(self):
        assert not _is_heading("")
        assert not _is_heading("这是一段普通文字")
        assert not _is_heading("  ")


class TestChunkText:
    def test_empty_text(self):
        assert chunk_text("") == []
        assert chunk_text("   ") == []

    def test_with_headings(self):
        text = "# 第一章\n内容A\n# 第二章\n内容B"
        chunks = chunk_text(text)
        assert len(chunks) == 2
        assert chunks[0]["heading"] == "# 第一章"
        assert "内容A" in chunks[0]["content"]
        assert chunks[1]["heading"] == "# 第二章"

    def test_no_heading_fixed_window(self):
        text = "这是一段没有标题的纯文本内容。" * 100  # ~1200 chars
        chunks = chunk_text(text, max_length=500, overlap=50)
        assert len(chunks) >= 2
        assert all(c["heading"] == "" for c in chunks)
        assert all(len(c["content"]) <= 500 for c in chunks)

    def test_long_section_split(self):
        text = "# 长章节\n" + "段落内容。\n\n" * 200
        chunks = chunk_text(text, max_length=500, overlap=50)
        assert len(chunks) > 1
        assert chunks[0]["heading"] == "# 长章节"

    def test_short_text_single_chunk(self):
        text = "# 标题\n短内容"
        chunks = chunk_text(text)
        assert len(chunks) == 1
        assert chunks[0]["heading"] == "# 标题"


class TestNoteServiceUpload:
    def test_upload_unsupported_type(self, note_service: NoteService):
        with pytest.raises(ValueError, match="仅支持"):
            note_service.upload("stu1", "test.txt", b"hello")

    def test_upload_pdf(self, note_service: NoteService, monkeypatch):
        monkeypatch.setattr(_note_svc_mod, "extract_text_from_pdf", lambda p: "# 第一章\n这是PDF内容\n# 第二章\n更多内容")

        detail = note_service.upload("stu1", "test.pdf", b"%PDF-fake")
        assert detail.note.student_id == "stu1"
        assert detail.note.file_type == "pdf"
        assert detail.note.chunk_count == 2
        assert len(detail.chunks) == 2

    def test_upload_docx(self, note_service: NoteService, monkeypatch):
        monkeypatch.setattr(_note_svc_mod, "extract_text_from_docx", lambda p: "# 概述\n文档内容")

        detail = note_service.upload("stu1", "note.docx", b"PK-fake")
        assert detail.note.file_type == "docx"
        assert detail.note.chunk_count == 1

    def test_delete_note(self, note_service: NoteService, monkeypatch):
        monkeypatch.setattr(_note_svc_mod, "extract_text_from_pdf", lambda p: "# 标题\n内容")

        detail = note_service.upload("stu1", "del.pdf", b"data")
        note_service.delete("stu1", detail.note.id)
        assert note_service.get_detail(detail.note.id) is None

    def test_delete_wrong_owner(self, note_service: NoteService, monkeypatch):
        monkeypatch.setattr(_note_svc_mod, "extract_text_from_pdf", lambda p: "内容")

        detail = note_service.upload("stu1", "x.pdf", b"data")
        with pytest.raises(PermissionError, match="无权"):
            note_service.delete("stu2", detail.note.id)

    def test_list_notes(self, note_service: NoteService, monkeypatch):
        monkeypatch.setattr(_note_svc_mod, "extract_text_from_pdf", lambda p: "内容")

        note_service.upload("stu1", "a.pdf", b"d", course_id="c1")
        note_service.upload("stu1", "b.pdf", b"d", course_id="c2")

        assert len(note_service.list_notes("stu1")) == 2
        assert len(note_service.list_notes("stu1", course_id="c1")) == 1
