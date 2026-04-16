from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import Lock

from app.config import NOTES_DB_PATH
from app.logging_config import logger
from app.models.note import Note, NoteChunk


class NoteStore:
    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = str(db_path or NOTES_DB_PATH)
        self._lock = Lock()
        self._init_db()
        logger.debug("NoteStore initialized with {}", self._db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS notes (
                    id          TEXT PRIMARY KEY,
                    student_id  TEXT NOT NULL,
                    course_id   TEXT,
                    filename    TEXT NOT NULL,
                    file_type   TEXT NOT NULL,
                    title       TEXT NOT NULL DEFAULT '',
                    summary     TEXT NOT NULL DEFAULT '',
                    chunk_count INTEGER NOT NULL DEFAULT 0,
                    created_at  TEXT NOT NULL,
                    updated_at  TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS note_chunks (
                    chunk_id    TEXT PRIMARY KEY,
                    note_id     TEXT NOT NULL,
                    heading     TEXT NOT NULL DEFAULT '',
                    content     TEXT NOT NULL DEFAULT '',
                    chunk_index INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_notes_student
                ON notes(student_id)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chunks_note
                ON note_chunks(note_id)
                """
            )

    def add_note(self, note: Note) -> Note:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO notes
                   (id, student_id, course_id, filename, file_type,
                    title, summary, chunk_count, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    note.id,
                    note.student_id,
                    note.course_id,
                    note.filename,
                    note.file_type,
                    note.title,
                    note.summary,
                    note.chunk_count,
                    note.created_at,
                    note.updated_at,
                ),
            )
        logger.info("Added note {} for {}", note.id, note.student_id)
        return note

    def get_note(self, note_id: str) -> Note | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
        if row is None:
            return None
        return Note(**dict(row))

    def list_by_student(self, student_id: str, course_id: str | None = None) -> list[Note]:
        sql = "SELECT * FROM notes WHERE student_id = ?"
        params: list[str] = [student_id]
        if course_id is not None:
            sql += " AND course_id = ?"
            params.append(course_id)
        sql += " ORDER BY created_at DESC"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [Note(**dict(row)) for row in rows]

    def list_chunks_by_student(self, student_id: str, course_id: str | None = None) -> list[NoteChunk]:
        sql = """
            SELECT c.*
            FROM note_chunks AS c
            INNER JOIN notes AS n ON n.id = c.note_id
            WHERE n.student_id = ?
        """
        params: list[str] = [student_id]
        if course_id is not None:
            sql += " AND n.course_id = ?"
            params.append(course_id)
        sql += " ORDER BY n.created_at DESC, n.id ASC, c.chunk_index ASC"

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [NoteChunk(**dict(row)) for row in rows]

    def update_note(self, note: Note) -> Note:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE notes
                SET title = ?, summary = ?, chunk_count = ?, updated_at = ?
                WHERE id = ?
                """,
                (note.title, note.summary, note.chunk_count, note.updated_at, note.id),
            )
        logger.info("Updated note {}", note.id)
        return note

    def delete_note(self, note_id: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        logger.info("Deleted note {}", note_id)

    def add_chunks(self, chunks: list[NoteChunk]) -> None:
        if not chunks:
            return
        with self._lock, self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO note_chunks
                   (chunk_id, note_id, heading, content, chunk_index)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (chunk.chunk_id, chunk.note_id, chunk.heading, chunk.content, chunk.chunk_index)
                    for chunk in chunks
                ],
            )
        logger.debug("Added {} chunks for note {}", len(chunks), chunks[0].note_id)

    def get_chunks_by_note(self, note_id: str) -> list[NoteChunk]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM note_chunks WHERE note_id = ? ORDER BY chunk_index",
                (note_id,),
            ).fetchall()
        return [NoteChunk(**dict(row)) for row in rows]

    def delete_chunks_by_note(self, note_id: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM note_chunks WHERE note_id = ?", (note_id,))
