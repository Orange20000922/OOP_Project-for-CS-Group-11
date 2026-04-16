from __future__ import annotations

from pydantic import BaseModel, Field


class KnowledgeTopic(BaseModel):
    id: str
    name: str = Field(..., min_length=1, max_length=128)
    parent_id: str | None = None
    child_ids: list[str] = Field(default_factory=list)
    note_ids: list[str] = Field(default_factory=list)
    summary: str = ""
    keywords: list[str] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


class KnowledgeTree(BaseModel):
    version: int = 1
    student_id: str
    course_id: str | None = None
    root_ids: list[str] = Field(default_factory=list)
    topics: dict[str, KnowledgeTopic] = Field(default_factory=dict)


class KnowledgeTopicCreate(BaseModel):
    course_id: str | None = Field(default=None, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    parent_id: str | None = Field(default=None, max_length=64)
    summary: str = Field(default="", max_length=1024)
    keywords: list[str] = Field(default_factory=list, max_length=32)


class KnowledgeTopicUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    parent_id: str | None = Field(default=None, max_length=64)
    summary: str | None = Field(default=None, max_length=1024)
    keywords: list[str] | None = Field(default=None, max_length=32)


class KnowledgeTopicAssign(BaseModel):
    course_id: str | None = Field(default=None, max_length=64)
    note_id: str = Field(..., min_length=1, max_length=64)

