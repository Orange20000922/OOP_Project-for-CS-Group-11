from __future__ import annotations

from pydantic import BaseModel, Field


class Note(BaseModel):
    id: str
    student_id: str
    course_id: str | None = None
    filename: str
    file_type: str
    title: str = ""
    summary: str = ""
    chunk_count: int = 0
    created_at: str = ""
    updated_at: str = ""


class NoteCreate(BaseModel):
    course_id: str | None = Field(default=None, max_length=64)


class NoteChunk(BaseModel):
    chunk_id: str
    note_id: str
    heading: str = ""
    content: str = ""
    chunk_index: int = 0


class NoteDetail(BaseModel):
    note: Note
    chunks: list[NoteChunk] = Field(default_factory=list)


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1024)
    limit: int = Field(default=10, ge=1, le=50)


class SearchResult(BaseModel):
    chunk: NoteChunk
    score: float
    note_title: str = ""


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1024)


class AskResponse(BaseModel):
    answer: str
    sources: list[SearchResult] = Field(default_factory=list)


class GraphNode(BaseModel):
    id: str
    label: str
    group: str
    note_id: str
    note_title: str = ""
    chunk_index: int = 0
    content_preview: str = ""


class GraphLink(BaseModel):
    source: str
    target: str
    value: float


class GraphResponse(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    links: list[GraphLink] = Field(default_factory=list)
    top_k: int = 0
    min_score: float = 0.0
    course_id: str | None = None
    total_nodes: int = 0
    total_links: int = 0
    truncated: bool = False
