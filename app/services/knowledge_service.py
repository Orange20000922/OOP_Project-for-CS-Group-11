from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any
from uuid import uuid4

from app.config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    QDRANT_DB_DIR,
)
from app.logging_config import logger
from app.models.knowledge import KnowledgeTopic, KnowledgeTopicCreate, KnowledgeTopicUpdate, KnowledgeTree
from app.models.note import (
    GraphLink,
    GraphNode,
    GraphResponse,
    Note,
    NoteChunk,
    SearchResult,
)
from app.storage.knowledge_tree_store import KnowledgeTreeStore
from app.storage.note_store import NoteStore
from app.services.topic_vector_store import TopicVectorStore

# 这个模块负责处理与笔记聚类相关的功能，包括向量索引、语义搜索、RAG 和图谱构建等。

class KnowledgeService:
    """Vector index, topic tree, RAG and graph-building helpers."""

    def __init__(
        self,
        note_store: NoteStore,
        tree_store: KnowledgeTreeStore | None = None,
    ) -> None:
        self._note_store = note_store
        self._tree_store = tree_store or KnowledgeTreeStore()
        self._memory: Any | None = None
        self._memory_failed = False
        self._topic_store: Any | None = None
        self._topic_store_failed = False
        self._llm_client: Any | None = None
        self._llm_failed = False

    def _close_resource(self, resource: Any, label: str) -> None:
        if resource is None:
            return

        close_fn = getattr(resource, "close", None)
        if close_fn is None:
            return

        try:
            close_fn()
            logger.info("Closed {}", label)
        except Exception as exc:
            logger.warning("Failed to close {}: {}", label, exc)

    def close(self) -> None:
        self._close_resource(self._memory, "chunk memory")
        self._memory = None

        topic_store = self._topic_store
        self._topic_store = None
        if topic_store is not None:
            try:
                topic_store.close()
                logger.info("Closed topic vector store")
            except Exception as exc:
                logger.warning("Failed to close topic vector store: {}", exc)

        self._close_resource(self._llm_client, "LLM client")
        self._llm_client = None

    def _build_memory_config(self, collection_name: str) -> dict[str, Any]:
        store_dir = QDRANT_DB_DIR / collection_name
        store_dir.mkdir(parents=True, exist_ok=True)
        return {
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "collection_name": collection_name,
                    "path": str(store_dir),
                    "embedding_model_dims": 384,
                    "on_disk": True,
                },
            },
            "embedder": {
                "provider": "huggingface",
                "config": {
                    "model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                },
            },
            "llm": {
                "provider": "openai",
                "config": {
                    "model": DEEPSEEK_MODEL,
                    "api_key": DEEPSEEK_API_KEY or "placeholder",
                    "openai_base_url": DEEPSEEK_BASE_URL,
                },
            },
        }

    def _ensure_memory(self) -> None:
        if self._memory is not None or self._memory_failed:
            return
        try:
            from mem0 import Memory

            QDRANT_DB_DIR.mkdir(parents=True, exist_ok=True)
            self._memory = Memory.from_config(self._build_memory_config("course_notes"))
            logger.info("Chunk memory initialized at {}", QDRANT_DB_DIR)
        except Exception as exc:
            logger.error("Failed to initialize chunk memory: {}", exc)
            self._memory_failed = True

    def _ensure_topic_store(self) -> None:
        if self._topic_store is not None or self._topic_store_failed:
            return
        try:
            QDRANT_DB_DIR.mkdir(parents=True, exist_ok=True)
            self._topic_store = TopicVectorStore()
            logger.info("Topic vector store initialized at {}", QDRANT_DB_DIR)
        except Exception as exc:
            logger.warning("Failed to initialize topic vector store: {}", exc)
            self._topic_store_failed = True

    def _ensure_llm(self) -> None:
        if self._llm_client is not None or self._llm_failed:
            return
        if not DEEPSEEK_API_KEY:
            logger.warning("DEEPSEEK_API_KEY not set; LLM features disabled")
            self._llm_failed = True
            return
        try:
            from openai import OpenAI

            self._llm_client = OpenAI(
                api_key=DEEPSEEK_API_KEY,
                base_url=DEEPSEEK_BASE_URL,
            )
            logger.info("OpenAI client initialized for DeepSeek")
        except Exception as exc:
            logger.error("Failed to initialize OpenAI client: {}", exc)
            self._llm_failed = True

    def _require_memory(self) -> Any:
        self._ensure_memory()
        if self._memory is None:
            raise RuntimeError("向量索引服务不可用")
        return self._memory

    def _clean_keywords(self, keywords: list[str] | None) -> list[str]:
        if not keywords:
            return []
        seen: set[str] = set()
        result: list[str] = []
        for item in keywords:
            value = item.strip()
            if not value:
                continue
            key = value.casefold()
            if key in seen:
                continue
            seen.add(key)
            result.append(value)
        return result

    def _get_tree(self, student_id: str, course_id: str | None = None) -> KnowledgeTree:
        return self._tree_store.load(student_id, course_id)

    def get_tree(self, student_id: str, course_id: str | None = None) -> KnowledgeTree:
        return self._get_tree(student_id, course_id)

    def _save_tree(self, tree: KnowledgeTree) -> KnowledgeTree:
        return self._tree_store.save(tree)

    def _get_topic_or_raise(self, tree: KnowledgeTree, topic_id: str) -> KnowledgeTopic:
        topic = tree.topics.get(topic_id)
        if topic is None:
            raise ValueError(f"知识主题不存在: {topic_id}")
        return topic

    def _append_unique(self, items: list[str], value: str) -> None:
        if value not in items:
            items.append(value)

    def _remove_value(self, items: list[str], value: str) -> None:
        while value in items:
            items.remove(value)

    def _detach_topic(self, tree: KnowledgeTree, topic: KnowledgeTopic) -> None:
        if topic.parent_id:
            parent = tree.topics.get(topic.parent_id)
            if parent is not None:
                self._remove_value(parent.child_ids, topic.id)
        else:
            self._remove_value(tree.root_ids, topic.id)

    def _attach_topic(self, tree: KnowledgeTree, topic: KnowledgeTopic, parent_id: str | None) -> None:
        topic.parent_id = parent_id
        if parent_id:
            parent = self._get_topic_or_raise(tree, parent_id)
            self._append_unique(parent.child_ids, topic.id)
        else:
            self._append_unique(tree.root_ids, topic.id)

    def _collect_descendant_topic_ids(self, tree: KnowledgeTree, topic_id: str) -> list[str]:
        ordered: list[str] = []
        stack = [topic_id]
        seen: set[str] = set()
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            topic = tree.topics.get(current)
            if topic is None:
                continue
            ordered.append(current)
            stack.extend(reversed(topic.child_ids))
        return ordered

    def _topic_has_descendant(
        self,
        tree: KnowledgeTree,
        topic_id: str,
        candidate_parent_id: str | None,
    ) -> bool:
        if not candidate_parent_id:
            return False
        return candidate_parent_id in self._collect_descendant_topic_ids(tree, topic_id)

    def _notes_by_id(self, student_id: str, course_id: str | None = None) -> dict[str, Note]:
        return {
            note.id: note
            for note in self._note_store.list_by_student(student_id, course_id)
        }

    def _topic_text(self, topic: KnowledgeTopic, notes_by_id: dict[str, Note]) -> str:
        parts: list[str] = []
        if topic.name.strip():
            parts.append(topic.name.strip())
        if topic.summary.strip():
            parts.append(topic.summary.strip())
        if topic.keywords:
            parts.append(" ".join(topic.keywords))

        note_summaries: list[str] = []
        for note_id in topic.note_ids[:8]:
            note = notes_by_id.get(note_id)
            if note is None:
                continue
            title = note.title.strip() or note.filename.strip()
            if note.summary.strip():
                note_summaries.append(f"{title} {note.summary.strip()}")
            else:
                note_summaries.append(title)
        if note_summaries:
            parts.append("\n".join(note_summaries))

        return "\n".join(part for part in parts if part)

    def _reindex_topic(self, student_id: str, course_id: str | None, tree: KnowledgeTree, topic_id: str) -> None:
        topic = tree.topics.get(topic_id)
        if topic is None:
            return
        self._ensure_topic_store()
        if self._topic_store is None:
            return

        notes_by_id = self._notes_by_id(student_id, course_id)
        payload = self._topic_text(topic, notes_by_id).strip()
        try:
            self._topic_store.delete_topic(student_id, course_id, topic_id)
        except Exception as exc:
            logger.warning("Failed to delete stale topic vector for {}: {}", topic_id, exc)
        if not payload:
            return

        self._topic_store.upsert_topic(
            student_id=student_id,
            course_id=course_id,
            topic_id=topic.id,
            topic_name=topic.name,
            text=payload,
        )

    def _delete_topic_vector(self, student_id: str, course_id: str | None, topic_id: str) -> None:
        self._ensure_topic_store()
        if self._topic_store is None:
            return
        try:
            self._topic_store.delete_topic(student_id, course_id, topic_id)
        except Exception as exc:
            logger.warning("Failed to delete topic vector for {}: {}", topic_id, exc)

    def _tokenize(self, text: str) -> list[str]:
        return re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]", text.casefold())

    def _lexical_similarity(self, query: str, text: str) -> float:
        query_text = query.strip().casefold()
        candidate_text = text.strip().casefold()
        if not query_text or not candidate_text:
            return 0.0

        query_tokens = set(self._tokenize(query_text))
        candidate_tokens = set(self._tokenize(candidate_text))
        if not query_tokens or not candidate_tokens:
            return 0.0

        overlap = len(query_tokens & candidate_tokens)
        score = overlap / max(1, len(query_tokens))
        if query_text in candidate_text or candidate_text in query_text:
            score += 0.35
        return min(score, 1.0)

    def create_topic(self, student_id: str, payload: KnowledgeTopicCreate) -> KnowledgeTree:
        tree = self._get_tree(student_id, payload.course_id)
        parent_id = payload.parent_id or None
        if parent_id is not None:
            self._get_topic_or_raise(tree, parent_id)

        now = datetime.now().isoformat()
        topic = KnowledgeTopic(
            id=uuid4().hex,
            name=payload.name.strip(),
            parent_id=parent_id,
            summary=payload.summary.strip(),
            keywords=self._clean_keywords(payload.keywords),
            created_at=now,
            updated_at=now,
        )
        tree.topics[topic.id] = topic
        self._attach_topic(tree, topic, parent_id)
        self._save_tree(tree)
        self._reindex_topic(student_id, tree.course_id, tree, topic.id)
        return tree

    def update_topic(
        self,
        student_id: str,
        course_id: str | None,
        topic_id: str,
        payload: KnowledgeTopicUpdate,
    ) -> KnowledgeTree:
        tree = self._get_tree(student_id, course_id)
        topic = self._get_topic_or_raise(tree, topic_id)
        updates = payload.model_dump(exclude_unset=True)

        if "parent_id" in updates:
            new_parent_id = updates["parent_id"] or None
            if new_parent_id == topic.id:
                raise ValueError("主题不能把自己作为父节点")
            if self._topic_has_descendant(tree, topic.id, new_parent_id):
                raise ValueError("主题不能移动到自己的子节点下")
            if new_parent_id is not None:
                self._get_topic_or_raise(tree, new_parent_id)
            self._detach_topic(tree, topic)
            self._attach_topic(tree, topic, new_parent_id)

        if "name" in updates:
            topic.name = (updates["name"] or "").strip()
        if "summary" in updates:
            topic.summary = (updates["summary"] or "").strip()
        if "keywords" in updates:
            topic.keywords = self._clean_keywords(updates["keywords"])
        topic.updated_at = datetime.now().isoformat()

        self._save_tree(tree)
        self._reindex_topic(student_id, tree.course_id, tree, topic.id)
        return tree

    def delete_topic(self, student_id: str, course_id: str | None, topic_id: str) -> KnowledgeTree:
        tree = self._get_tree(student_id, course_id)
        topic = self._get_topic_or_raise(tree, topic_id)
        parent_id = topic.parent_id
        touched_topic_ids: set[str] = set()

        if parent_id:
            parent = self._get_topic_or_raise(tree, parent_id)
            for note_id in topic.note_ids:
                self._append_unique(parent.note_ids, note_id)
            parent.updated_at = datetime.now().isoformat()
            touched_topic_ids.add(parent.id)

        self._detach_topic(tree, topic)
        for child_id in list(topic.child_ids):
            child = self._get_topic_or_raise(tree, child_id)
            child.parent_id = parent_id
            if parent_id:
                parent = self._get_topic_or_raise(tree, parent_id)
                self._append_unique(parent.child_ids, child_id)
            else:
                self._append_unique(tree.root_ids, child_id)

        del tree.topics[topic_id]
        self._save_tree(tree)
        self._delete_topic_vector(student_id, tree.course_id, topic_id)
        for touched_topic_id in touched_topic_ids:
            self._reindex_topic(student_id, tree.course_id, tree, touched_topic_id)
        return tree

    def remove_note_from_topics(
        self,
        student_id: str,
        note_id: str,
        course_id: str | None,
    ) -> KnowledgeTree:
        tree = self._get_tree(student_id, course_id)
        changed_topic_ids: list[str] = []
        for topic in tree.topics.values():
            if note_id in topic.note_ids:
                self._remove_value(topic.note_ids, note_id)
                topic.updated_at = datetime.now().isoformat()
                changed_topic_ids.append(topic.id)
        if not changed_topic_ids:
            return tree
        self._save_tree(tree)
        for topic_id in changed_topic_ids:
            self._reindex_topic(student_id, tree.course_id, tree, topic_id)
        return tree

    def assign_note_to_topic(
        self,
        student_id: str,
        course_id: str | None,
        topic_id: str,
        note_id: str,
    ) -> KnowledgeTree:
        note = self._note_store.get_note(note_id)
        if note is None:
            raise ValueError(f"笔记不存在: {note_id}")
        if note.student_id != student_id:
            raise PermissionError("不能关联其他用户的笔记")
        if note.course_id != course_id:
            raise ValueError("笔记课程和知识树课程不一致")

        tree = self.remove_note_from_topics(student_id, note_id, course_id)
        topic = self._get_topic_or_raise(tree, topic_id)
        self._append_unique(topic.note_ids, note_id)
        topic.updated_at = datetime.now().isoformat()
        self._save_tree(tree)
        self._reindex_topic(student_id, tree.course_id, tree, topic.id)
        return tree

    def unassign_note_from_topic(
        self,
        student_id: str,
        course_id: str | None,
        topic_id: str,
        note_id: str,
    ) -> KnowledgeTree:
        tree = self._get_tree(student_id, course_id)
        topic = self._get_topic_or_raise(tree, topic_id)
        if note_id not in topic.note_ids:
            return tree
        self._remove_value(topic.note_ids, note_id)
        topic.updated_at = datetime.now().isoformat()
        self._save_tree(tree)
        self._reindex_topic(student_id, tree.course_id, tree, topic.id)
        return tree

    def refresh_topics_for_note(self, student_id: str, note: Note) -> None:
        if note.course_id is None:
            return
        tree = self._get_tree(student_id, note.course_id)
        for topic in tree.topics.values():
            if note.id in topic.note_ids:
                self._reindex_topic(student_id, tree.course_id, tree, topic.id)

    def _rank_topics_with_vectors(
        self,
        student_id: str,
        tree: KnowledgeTree,
        query: str,
        limit: int,
    ) -> list[tuple[str, float]]:
        self._ensure_topic_store()
        if self._topic_store is None:
            return []

        ranked = self._topic_store.search_topics(
            student_id=student_id,
            course_id=tree.course_id,
            query=query,
            limit=limit,
        )
        return [
            (topic_id, score)
            for topic_id, score in ranked
            if topic_id in tree.topics
        ]

    def _rank_topics_lexically(
        self,
        student_id: str,
        tree: KnowledgeTree,
        query: str,
        limit: int,
    ) -> list[tuple[str, float]]:
        notes_by_id = self._notes_by_id(student_id, tree.course_id)
        scored: list[tuple[str, float]] = []
        for topic in tree.topics.values():
            score = self._lexical_similarity(query, self._topic_text(topic, notes_by_id))
            if score > 0:
                scored.append((topic.id, score))
        scored.sort(key=lambda item: (-item[1], item[0]))
        return scored[:limit]

    def _rank_topics(
        self,
        student_id: str,
        tree: KnowledgeTree,
        query: str,
        limit: int = 3,
    ) -> list[tuple[str, float]]:
        ranked = self._rank_topics_with_vectors(student_id, tree, query, limit)
        if ranked:
            return ranked
        return self._rank_topics_lexically(student_id, tree, query, limit)

    def auto_assign_note(
        self,
        student_id: str,
        note: Note,
        chunks: list[NoteChunk],
        min_score: float = 0.15,
    ) -> str | None:
        if note.course_id is None:
            return None

        tree = self._get_tree(student_id, note.course_id)
        if not tree.topics:
            return None

        parts = [note.title.strip(), note.summary.strip(), note.filename.strip()]
        headings = [chunk.heading.strip() for chunk in chunks if chunk.heading.strip()]
        parts.extend(headings[:3])
        query = " ".join(part for part in parts if part).strip()
        if not query:
            return None

        ranked = self._rank_topics(student_id, tree, query, limit=1)
        if not ranked:
            return None
        topic_id, score = ranked[0]
        if score < min_score:
            return None
        self.assign_note_to_topic(student_id, note.course_id, topic_id, note.id)
        return topic_id

    def _resolve_selected_topic_ids(
        self,
        student_id: str,
        tree: KnowledgeTree,
        query: str,
        topic_id: str | None,
        topic_limit: int,
    ) -> list[str]:
        if topic_id:
            self._get_topic_or_raise(tree, topic_id)
            return self._collect_descendant_topic_ids(tree, topic_id)
        if not query.strip():
            return []

        ranked = self._rank_topics(student_id, tree, query, limit=topic_limit)
        selected: list[str] = []
        for ranked_topic_id, score in ranked:
            if score <= 0:
                continue
            for expanded_topic_id in self._collect_descendant_topic_ids(tree, ranked_topic_id):
                if expanded_topic_id not in selected:
                    selected.append(expanded_topic_id)
        return selected

    def _candidate_note_ids_from_topics(self, tree: KnowledgeTree, topic_ids: list[str]) -> set[str]:
        note_ids: set[str] = set()
        for topic_id in topic_ids:
            topic = tree.topics.get(topic_id)
            if topic is None:
                continue
            note_ids.update(topic.note_ids)
        return note_ids

    def _note_topic_map(self, tree: KnowledgeTree) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for topic in tree.topics.values():
            for note_id in topic.note_ids:
                mapping[note_id] = topic.id
        return mapping

    def _iter_memory_results(self, raw_results: Any) -> list[dict[str, Any]]:
        if isinstance(raw_results, dict):
            candidates = raw_results.get("results") or raw_results.get("memories") or []
        else:
            candidates = raw_results

        if not isinstance(candidates, list):
            return []

        normalized: list[dict[str, Any]] = []
        for item in candidates:
            if isinstance(item, dict):
                data = dict(item)
            else:
                dump = getattr(item, "model_dump", None)
                if callable(dump):
                    data = dump()
                else:
                    dump = getattr(item, "dict", None)
                    if callable(dump):
                        data = dump()
                    else:
                        continue

            metadata = data.get("metadata") or data.get("payload") or {}
            if not isinstance(metadata, dict):
                metadata = {}
            data["metadata"] = metadata

            if data.get("memory") is None:
                data["memory"] = data.get("text") or data.get("content") or ""
            if data.get("score") is None:
                data["score"] = data.get("similarity") or 0.0
            normalized.append(data)

        return normalized

    def _build_search_result(self, item: dict[str, Any]) -> SearchResult:
        metadata = item.get("metadata") or {}
        chunk_id = str(metadata.get("chunk_id", ""))
        note_id = str(metadata.get("note_id", ""))
        heading = str(metadata.get("heading", ""))
        note = self._note_store.get_note(note_id) if note_id else None

        return SearchResult(
            chunk=NoteChunk(
                chunk_id=chunk_id,
                note_id=note_id,
                heading=heading,
                content=str(item.get("memory", "")),
                chunk_index=0,
            ),
            score=float(item.get("score", 0.0) or 0.0),
            note_title=note.title if note else "",
        )

    def _build_graph_node(
        self,
        chunk: NoteChunk,
        note_title: str,
        topic_id: str | None,
    ) -> GraphNode:
        label = chunk.heading.strip() or note_title.strip() or f"Chunk {chunk.chunk_index + 1}"
        preview = chunk.content.strip().replace("\n", " ")
        if len(preview) > 120:
            preview = f"{preview[:117]}..."
        return GraphNode(
            id=chunk.chunk_id,
            label=label,
            group=topic_id or chunk.note_id,
            note_id=chunk.note_id,
            note_title=note_title,
            topic_id=topic_id,
            chunk_index=chunk.chunk_index,
            content_preview=preview,
        )

    def _chunk_search_text(self, chunk: NoteChunk, note_title: str = "") -> str:
        parts = [chunk.heading.strip(), note_title.strip(), chunk.content.strip()]
        return "\n".join(part for part in parts if part)

    def _search_lexically(
        self,
        student_id: str,
        query: str,
        limit: int,
        course_id: str | None = None,
    ) -> list[SearchResult]:
        notes = self._note_store.list_by_student(student_id, course_id)
        if not notes:
            return []

        note_titles = {
            note.id: (note.title.strip() or note.filename)
            for note in notes
        }
        scored_chunks: list[tuple[float, NoteChunk]] = []
        for chunk in self._note_store.list_chunks_by_student(student_id, course_id):
            if not chunk.content.strip():
                continue
            score = self._lexical_similarity(
                query,
                self._chunk_search_text(chunk, note_titles.get(chunk.note_id, "")),
            )
            if score <= 0:
                continue
            scored_chunks.append((score, chunk))

        scored_chunks.sort(
            key=lambda item: (-item[0], item[1].note_id, item[1].chunk_index, item[1].chunk_id)
        )
        return [
            SearchResult(
                chunk=chunk,
                score=score,
                note_title=note_titles.get(chunk.note_id, ""),
            )
            for score, chunk in scored_chunks[:limit]
        ]

    def _build_graph_links_lexically(
        self,
        candidate_chunks: list[NoteChunk],
        top_k: int,
        min_score: float,
    ) -> list[GraphLink]:
        chunk_texts = {
            chunk.chunk_id: self._chunk_search_text(chunk)
            for chunk in candidate_chunks
        }
        edge_map: dict[tuple[str, str], GraphLink] = {}

        for chunk in candidate_chunks:
            scored_neighbors: list[tuple[float, str]] = []
            query_text = chunk_texts.get(chunk.chunk_id, "")
            for neighbor in candidate_chunks:
                if neighbor.chunk_id == chunk.chunk_id:
                    continue
                score = self._lexical_similarity(
                    query_text,
                    chunk_texts.get(neighbor.chunk_id, ""),
                )
                if score < min_score:
                    continue
                scored_neighbors.append((score, neighbor.chunk_id))

            scored_neighbors.sort(key=lambda item: (-item[0], item[1]))
            for score, neighbor_id in scored_neighbors[:top_k]:
                source, target = sorted((chunk.chunk_id, neighbor_id))
                key = (source, target)
                current = edge_map.get(key)
                if current is None or score > current.value:
                    edge_map[key] = GraphLink(source=source, target=target, value=score)

        return sorted(
            edge_map.values(),
            key=lambda link: (-link.value, link.source, link.target),
        )

    def index_chunks(self, student_id: str, chunks: list[NoteChunk]) -> int:
        memory = self._require_memory()

        count = 0
        for chunk in chunks:
            if not chunk.content.strip():
                continue
            memory.add(
                messages=[{"role": "user", "content": chunk.content}],
                user_id=student_id,
                metadata={
                    "note_id": chunk.note_id,
                    "chunk_id": chunk.chunk_id,
                    "heading": chunk.heading,
                },
            )
            count += 1

        logger.info("Indexed {} chunks for {}", count, student_id)
        return count

    def delete_note_vectors(self, student_id: str, note_id: str) -> None:
        self._ensure_memory()
        if self._memory is None:
            return
        try:
            self._memory.delete_all(user_id=student_id, metadata={"note_id": note_id})
        except Exception as exc:
            logger.warning(
                "Metadata-filtered vector delete failed for note {}: {}",
                note_id,
                exc,
            )

    def search(
        self,
        student_id: str,
        query: str,
        limit: int = 10,
        course_id: str | None = None,
    ) -> list[SearchResult]:
        self._ensure_memory()
        if self._memory is None:
            logger.warning(
                "Chunk memory unavailable; falling back to lexical search for {} (course_id={})",
                student_id,
                course_id,
            )
            return self._search_lexically(student_id, query, limit, course_id)

        memory = self._memory

        allowed_note_ids: set[str] | None = None
        fetch_limit = max(limit, 1)
        if course_id is not None:
            allowed_note_ids = {
                note.id for note in self._note_store.list_by_student(student_id, course_id)
            }
            if not allowed_note_ids:
                return []
            fetch_limit = max(limit * 4, 20)

        raw_results = memory.search(query=query, filters={"user_id": student_id}, limit=fetch_limit)

        results: list[SearchResult] = []
        for item in self._iter_memory_results(raw_results):
            metadata = item.get("metadata") or {}
            note_id = str(metadata.get("note_id", ""))
            if allowed_note_ids is not None and note_id not in allowed_note_ids:
                continue
            results.append(self._build_search_result(item))
            if len(results) >= limit:
                break

        return results

    def ask(
        self,
        student_id: str,
        question: str,
        course_id: str | None = None,
    ) -> tuple[str, list[SearchResult]]:
        sources = self.search(student_id, question, limit=5, course_id=course_id)

        self._ensure_llm()
        if self._llm_client is None:
            context_text = "\n---\n".join(
                f"[{source.chunk.heading}] {source.chunk.content}" for source in sources
            )
            return f"(LLM 不可用，以下为检索结果)\n\n{context_text}", sources

        context = "\n---\n".join(
            f"[{source.chunk.heading}] {source.chunk.content}" for source in sources
        )
        prompt = (
            "你是一个课程笔记助手。根据以下笔记内容回答问题。"
            "如果笔记中没有相关内容，请如实说明。\n\n"
            f"笔记内容：\n{context}\n\n"
            f"问题：{question}"
        )

        resp = self._llm_client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
        )
        answer = resp.choices[0].message.content or ""
        return answer, sources

    def build_graph(
        self,
        student_id: str,
        course_id: str | None = None,
        top_k: int = 3,
        min_score: float = 0.5,
        max_nodes: int = 120,
        query: str = "",
        topic_id: str | None = None,
        topic_limit: int = 3,
    ) -> GraphResponse:
        notes = self._note_store.list_by_student(student_id, course_id)
        if not notes:
            return GraphResponse(
                top_k=top_k,
                min_score=min_score,
                course_id=course_id,
                query=query,
            )

        note_titles = {
            note.id: (note.title.strip() or note.filename)
            for note in notes
        }
        all_course_chunks = [
            chunk
            for chunk in self._note_store.list_chunks_by_student(student_id, course_id)
            if chunk.content.strip()
        ]
        if not all_course_chunks:
            return GraphResponse(
                top_k=top_k,
                min_score=min_score,
                course_id=course_id,
                query=query,
            )

        tree = self._get_tree(student_id, course_id)
        selected_topic_ids: list[str] = []
        routing_applied = False
        allowed_note_ids = set(note_titles)
        if tree.topics and (query.strip() or topic_id):
            selected_topic_ids = self._resolve_selected_topic_ids(
                student_id=student_id,
                tree=tree,
                query=query,
                topic_id=topic_id,
                topic_limit=topic_limit,
            )
            routing_applied = True
            allowed_note_ids = self._candidate_note_ids_from_topics(tree, selected_topic_ids)

        candidate_chunks = [
            chunk for chunk in all_course_chunks if chunk.note_id in allowed_note_ids
        ]
        truncated = len(candidate_chunks) > max_nodes
        candidate_chunks = candidate_chunks[:max_nodes]
        allowed_chunk_ids = {chunk.chunk_id for chunk in candidate_chunks}
        note_topic_map = self._note_topic_map(tree)

        nodes = [
            self._build_graph_node(
                chunk,
                note_titles.get(chunk.note_id, ""),
                note_topic_map.get(chunk.note_id),
            )
            for chunk in candidate_chunks
        ]
        if not nodes:
            return GraphResponse(
                top_k=top_k,
                min_score=min_score,
                course_id=course_id,
                query=query,
                selected_topic_ids=selected_topic_ids,
                routing_applied=routing_applied,
                truncated=truncated,
            )

        self._ensure_memory()
        if self._memory is None:
            logger.warning(
                "Chunk memory unavailable; falling back to lexical graph links for {} (course_id={})",
                student_id,
                course_id,
            )
            links = self._build_graph_links_lexically(candidate_chunks, top_k, min_score)
        else:
            search_limit = max(
                top_k + 1,
                min(len(all_course_chunks) + 1, max(len(candidate_chunks) * 4, 20)),
            )
            edge_map: dict[tuple[str, str], GraphLink] = {}

            for chunk in candidate_chunks:
                kept_neighbors = 0
                results = self._memory.search(
                    query=chunk.content,
                    filters={"user_id": student_id},
                    limit=search_limit,
                )

                for item in self._iter_memory_results(results):
                    metadata = item.get("metadata") or {}
                    neighbor_id = str(metadata.get("chunk_id", ""))
                    if (
                        not neighbor_id
                        or neighbor_id == chunk.chunk_id
                        or neighbor_id not in allowed_chunk_ids
                    ):
                        continue

                    score = float(item.get("score", 0.0) or 0.0)
                    if score < min_score:
                        continue

                    source, target = sorted((chunk.chunk_id, neighbor_id))
                    key = (source, target)
                    current = edge_map.get(key)
                    if current is None or score > current.value:
                        edge_map[key] = GraphLink(source=source, target=target, value=score)

                    kept_neighbors += 1
                    if kept_neighbors >= top_k:
                        break

            links = sorted(
                edge_map.values(),
                key=lambda link: (-link.value, link.source, link.target),
            )
        graph = GraphResponse(
            nodes=nodes,
            links=links,
            top_k=top_k,
            min_score=min_score,
            course_id=course_id,
            query=query,
            selected_topic_ids=selected_topic_ids,
            routing_applied=routing_applied,
            total_nodes=len(nodes),
            total_links=len(links),
            truncated=truncated,
        )
        logger.info(
            "Built knowledge graph for {} with {} nodes and {} links (course_id={}, top_k={}, min_score={}, selected_topics={})",
            student_id,
            graph.total_nodes,
            graph.total_links,
            course_id,
            top_k,
            min_score,
            selected_topic_ids,
        )
        return graph
     
    def generate_summary(self, chunks: list[NoteChunk]) -> dict[str, str]:
        self._ensure_llm()
        if self._llm_client is None:
            title = ""
            summary = ""
            for chunk in chunks[:3]:
                if chunk.heading and not title:
                    title = chunk.heading
                summary += chunk.content + " "
            return {"title": title, "summary": summary[:100].strip()}

        text = "\n".join(chunk.content for chunk in chunks[:3])[:2000]
        prompt = (
            "从以下笔记内容中提取标题和摘要。返回 JSON 格式：\n"
            '{"title": "标题", "summary": "50字以内的摘要"}\n'
            "只返回 JSON，不要其他文字。\n\n"
            f"{text}"
        )

        resp = self._llm_client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=256,
        )
        content = resp.choices[0].message.content or "{}"

        try:
            data = json.loads(content)
            return {
                "title": data.get("title", ""),
                "summary": data.get("summary", ""),
            }
        except json.JSONDecodeError:
            logger.warning("LLM summary response is not valid JSON: {}", content[:100])
            return {"title": "", "summary": content[:100]}
