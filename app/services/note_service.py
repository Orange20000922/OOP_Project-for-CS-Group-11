from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from app.config import CHUNK_MAX_LENGTH, CHUNK_OVERLAP, NOTE_FILES_DIR
from app.logging_config import logger
from app.models.note import Note, NoteChunk, NoteDetail, NoteUpdate
from app.storage.note_store import NoteStore

HEADING_PATTERNS = [
    re.compile(r"^#{1,3}\s+.+"),
    re.compile(r"^第[一二三四五六七八九十\d]+[章节部分]"),
    re.compile(r"^[一二三四五六七八九十]+[、.]\s*.+"),
    re.compile(r"^\d+[.\s].+"),
    re.compile(r"^[A-Z][A-Za-z\s]{2,50}$"),
]


def _is_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    return any(p.match(stripped) for p in HEADING_PATTERNS)


def extract_text_from_pdf(file_path: Path) -> str:
    import pdfplumber

    pages: list[str] = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
    return "\n\n".join(pages)


def extract_text_from_docx(file_path: Path) -> str:
    from docx import Document

    doc = Document(str(file_path))
    paragraphs: list[str] = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            paragraphs.append(text)
    return "\n\n".join(paragraphs)


def extract_text(file_path: Path, file_type: str) -> str:
    if file_type == "pdf":
        return extract_text_from_pdf(file_path)
    elif file_type == "docx":
        return extract_text_from_docx(file_path)
    else:
        raise ValueError(f"不支持的文件类型: {file_type}")


def chunk_text(
    text: str,
    max_length: int = CHUNK_MAX_LENGTH,
    overlap: int = CHUNK_OVERLAP,
) -> list[dict[str, str]]:
    """将文本切片为 [{heading, content}, ...]"""
    if not text.strip():
        return []

    lines = text.splitlines()
    sections: list[dict[str, str]] = []
    current_heading = ""
    current_lines: list[str] = []

    for line in lines:
        if _is_heading(line):
            if current_lines:
                sections.append({"heading": current_heading, "content": "\n".join(current_lines).strip()})
            current_heading = line.strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        sections.append({"heading": current_heading, "content": "\n".join(current_lines).strip()})

    # 如果没有任何标题匹配（纯文本），按固定窗口切
    if len(sections) == 1 and not sections[0]["heading"]:
        return _fixed_window_chunks(sections[0]["content"], max_length, overlap)

    # 对超长段落做二次切分
    result: list[dict[str, str]] = []
    for sec in sections:
        content = sec["content"]
        if not content:
            continue
        if len(content) <= max_length:
            result.append(sec)
        else:
            sub_chunks = _split_long_section(content, max_length, overlap)
            for i, sc in enumerate(sub_chunks):
                heading = sec["heading"]
                if i > 0 and heading:
                    heading = f"{heading} (续{i})"
                result.append({"heading": heading, "content": sc})

    return result


def _split_long_section(text: str, max_length: int, overlap: int) -> list[str]:
    """按空行拆分，仍超长则硬截断"""
    paragraphs = re.split(r"\n\s*\n", text)
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(current) + len(para) + 1 <= max_length:
            current = f"{current}\n{para}" if current else para
        else:
            if current:
                chunks.append(current)
            if len(para) > max_length:
                chunks.extend(_hard_split(para, max_length, overlap))
            else:
                current = para
                continue
            current = ""

    if current:
        chunks.append(current)

    return chunks if chunks else [text[:max_length]]


def _hard_split(text: str, max_length: int, overlap: int) -> list[str]:
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + max_length
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


def _fixed_window_chunks(text: str, max_length: int, overlap: int) -> list[dict[str, str]]:
    pieces = _hard_split(text, max_length, overlap)
    return [{"heading": "", "content": p} for p in pieces]


class NoteService:
    def __init__(self, note_store: NoteStore) -> None:
        self._store = note_store
        NOTE_FILES_DIR.mkdir(parents=True, exist_ok=True)

    def upload(
        self,
        student_id: str,
        filename: str,
        content: bytes,
        course_id: str | None = None,
    ) -> NoteDetail:
        suffix = Path(filename).suffix.lower().lstrip(".")
        if suffix not in ("pdf", "docx"):
            raise ValueError("仅支持 PDF 和 DOCX 文件")

        note_id = uuid4().hex
        now = datetime.now().isoformat()

        # 保存原始文件
        file_path = NOTE_FILES_DIR / f"{note_id}.{suffix}"
        file_path.write_bytes(content)
        logger.info("Saved uploaded file {} -> {}", filename, file_path)

        # 提取文本 + 切片
        text = extract_text(file_path, suffix)
        raw_chunks = chunk_text(text)

        chunks: list[NoteChunk] = []
        for i, rc in enumerate(raw_chunks):
            chunks.append(NoteChunk(
                chunk_id=uuid4().hex,
                note_id=note_id,
                heading=rc["heading"],
                content=rc["content"],
                chunk_index=i,
            ))

        note = Note(
            id=note_id,
            student_id=student_id,
            course_id=course_id,
            filename=filename,
            file_type=suffix,
            chunk_count=len(chunks),
            created_at=now,
            updated_at=now,
        )

        self._store.add_note(note)
        self._store.add_chunks(chunks)
        logger.info("Uploaded note {} with {} chunks", note_id, len(chunks))
        return NoteDetail(note=note, chunks=chunks)

    def get_detail(self, note_id: str) -> NoteDetail | None:
        note = self._store.get_note(note_id)
        if note is None:
            return None
        chunks = self._store.get_chunks_by_note(note_id)
        return NoteDetail(note=note, chunks=chunks)

    def list_notes(self, student_id: str, course_id: str | None = None) -> list[Note]:
        return self._store.list_by_student(student_id, course_id)

    def update_metadata(self, student_id: str, note_id: str, payload: NoteUpdate) -> Note:
        note = self._store.get_note(note_id)
        if note is None:
            raise ValueError("笔记不存在")
        if note.student_id != student_id:
            raise PermissionError("无权修改此笔记")

        updates = payload.model_dump(exclude_unset=True)
        if "title" in updates:
            note.title = (updates["title"] or "").strip()
        if "summary" in updates:
            note.summary = (updates["summary"] or "").strip()
        if "course_id" in updates:
            note.course_id = (updates["course_id"] or None)
        note.updated_at = datetime.now().isoformat()
        return self._store.update_note(note)

    def delete(self, student_id: str, note_id: str) -> None:
        note = self._store.get_note(note_id)
        if note is None:
            raise ValueError("笔记不存在")
        if note.student_id != student_id:
            raise PermissionError("无权删除此笔记")
        # 删除原始文件
        file_path = NOTE_FILES_DIR / f"{note_id}.{note.file_type}"
        if file_path.exists():
            file_path.unlink()
        self._store.delete_note(note_id)
        logger.info("Deleted note {} and its file", note_id)

    def get_file_path(self, note_id: str) -> Path | None:
        note = self._store.get_note(note_id)
        if note is None:
            return None
        path = NOTE_FILES_DIR / f"{note_id}.{note.file_type}"
        return path if path.exists() else None
