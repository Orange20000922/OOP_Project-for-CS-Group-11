from __future__ import annotations

from typing import Any

from app.config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    QDRANT_DB_DIR,
)
from app.core import Stack
from app.logging_config import logger
from app.models.knowledge import KnowledgeTopicCreate, KnowledgeTopicUpdate, KnowledgeTree
from app.models.note import GraphResponse, Note, NoteChunk, SearchResult
from app.services.knowledge_search_operations import KnowledgeSearchOperations
from app.services.knowledge_tree_operations import KnowledgeTreeOperations
from app.services.topic_vector_store import TopicVectorStore
from app.storage.knowledge_tree_store import KnowledgeTreeStore
from app.storage.note_store import NoteStore


class KnowledgeService:
    """知识管理主服务：组合知识树操作和检索操作"""

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

        self._tree_ops = KnowledgeTreeOperations(
            note_store=note_store,
            tree_store=self._tree_store,
            topic_vector_store=None,
        )
        self._search_ops: KnowledgeSearchOperations | None = None

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
            self._tree_ops._topic_store = self._topic_store
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

    def _ensure_search_ops(self) -> None:
        if self._search_ops is not None:
            return
        self._ensure_memory()
        self._ensure_llm()
        self._search_ops = KnowledgeSearchOperations(
            note_store=self._note_store,
            tree_store=self._tree_store,
            memory=self._memory,
            llm_client=self._llm_client,
            collect_topic_note_ids_fn=self._tree_ops.collect_topic_note_ids,
        )

    def get_tree(self, student_id: str, course_id: str | None = None) -> KnowledgeTree:
        return self._tree_ops.get_tree(student_id, course_id)

    def create_topic(self, student_id: str, payload: KnowledgeTopicCreate) -> KnowledgeTree:
        self._ensure_topic_store()
        return self._tree_ops.create_topic(student_id, payload)

    def update_topic(
        self,
        student_id: str,
        course_id: str | None,
        topic_id: str,
        payload: KnowledgeTopicUpdate,
    ) -> KnowledgeTree:
        self._ensure_topic_store()
        return self._tree_ops.update_topic(student_id, course_id, topic_id, payload)

    def delete_topic(self, student_id: str, course_id: str | None, topic_id: str) -> KnowledgeTree:
        return self._tree_ops.delete_topic(student_id, course_id, topic_id)

    def assign_note_to_topic(
        self,
        student_id: str,
        course_id: str | None,
        topic_id: str,
        note_id: str,
    ) -> KnowledgeTree:
        return self._tree_ops.assign_note_to_topic(student_id, course_id, topic_id, note_id)

    def unassign_note_from_topic(
        self,
        student_id: str,
        course_id: str | None,
        topic_id: str,
        note_id: str,
    ) -> KnowledgeTree:
        return self._tree_ops.unassign_note_from_topic(student_id, course_id, topic_id, note_id)

    def refresh_topics_for_note(self, student_id: str, note: Note) -> None:
        self._ensure_topic_store()
        self._tree_ops.refresh_topics_for_note(student_id, note)

    def auto_assign_note(
        self,
        student_id: str,
        note: Note,
        chunks: list[NoteChunk],
        min_score: float = 0.15,
    ) -> str | None:
        self._ensure_topic_store()
        self._ensure_search_ops()
        return self._tree_ops.auto_assign_note(
            student_id,
            note,
            chunks,
            min_score,
            lexical_similarity_fn=self._search_ops._lexical_similarity if self._search_ops else None,
        )

    def index_chunks(self, student_id: str, chunks: list[NoteChunk]) -> int:
        self._ensure_search_ops()
        if self._search_ops is None:
            raise RuntimeError("向量索引服务不可用")
        return self._search_ops.index_chunks(student_id, chunks)

    def delete_note_vectors(self, student_id: str, note_id: str) -> None:
        self._ensure_search_ops()
        if self._search_ops is not None:
            self._search_ops.delete_note_vectors(student_id, note_id)

    def search(
        self,
        student_id: str,
        query: str,
        limit: int = 10,
        course_id: str | None = None,
        topic_id: str | None = None,
    ) -> list[SearchResult]:
        self._ensure_search_ops()
        if self._search_ops is None:
            return []
        return self._search_ops.search(student_id, query, limit, course_id, topic_id)

    def ask(
        self,
        student_id: str,
        question: str,
        course_id: str | None = None,
        topic_id: str | None = None,
    ) -> tuple[str, list[SearchResult]]:
        self._ensure_search_ops()
        if self._search_ops is None:
            return "向量索引服务不可用", []
        return self._search_ops.ask(student_id, question, course_id, topic_id)

    def _resolve_selected_topic_ids(
        self,
        student_id: str,
        tree: KnowledgeTree,
        query: str,
        topic_id: str | None,
        topic_limit: int,
    ) -> list[str]:
        if topic_id and topic_id in tree.topics:
            return [topic_id]
        if not query.strip():
            return []
        self._ensure_topic_store()
        ranked = self._tree_ops.rank_topics(
            student_id,
            tree,
            query,
            limit=topic_limit,
            lexical_similarity_fn=self._search_ops._lexical_similarity if self._search_ops else None,
        )
        return [topic_id for topic_id, _ in ranked]

    def _candidate_note_ids_from_topics(self, tree: KnowledgeTree, topic_ids: list[str]) -> set[str]:
        note_ids: set[str] = set()
        for topic_id in topic_ids:
            note_ids.update(self._tree_ops.collect_topic_note_ids(tree, topic_id))
        return note_ids

    def _note_topic_map(self, tree: KnowledgeTree) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for topic in tree.topics.values():
            for note_id in topic.note_ids:
                mapping[note_id] = topic.id
        return mapping

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
        self._ensure_search_ops()
        if self._search_ops is None:
            return GraphResponse(
                top_k=top_k,
                min_score=min_score,
                course_id=course_id,
                query=query,
            )
        return self._search_ops.build_graph(
            student_id=student_id,
            course_id=course_id,
            top_k=top_k,
            min_score=min_score,
            max_nodes=max_nodes,
            query=query,
            topic_id=topic_id,
            topic_limit=topic_limit,
            resolve_selected_topic_ids_fn=self._resolve_selected_topic_ids,
            candidate_note_ids_from_topics_fn=self._candidate_note_ids_from_topics,
            note_topic_map_fn=self._note_topic_map,
        )

    def generate_summary(self, chunks: list[NoteChunk]) -> dict[str, str]:
        self._ensure_search_ops()
        if self._search_ops is None:
            return {"title": "", "summary": ""}
        return self._search_ops.generate_summary(chunks)
