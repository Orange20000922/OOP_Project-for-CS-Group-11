from __future__ import annotations

import json
from typing import Any

from app.config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    QDRANT_DB_DIR,
)
from app.logging_config import logger
from app.models.note import (
    GraphLink,
    GraphNode,
    GraphResponse,
    NoteChunk,
    SearchResult,
)
from app.storage.note_store import NoteStore


class KnowledgeService:
    """Vector index, semantic search, RAG and graph-building helpers."""

    def __init__(self, note_store: NoteStore) -> None:
        self._note_store = note_store
        self._memory: Any | None = None
        self._memory_failed = False
        self._llm_client: Any | None = None
        self._llm_failed = False

    def _ensure_memory(self) -> None:
        if self._memory is not None or self._memory_failed:
            return
        try:
            from mem0 import Memory

            config = {
                "vector_store": {
                    "provider": "qdrant",
                    "config": {
                        "collection_name": "course_notes",
                        "path": str(QDRANT_DB_DIR),
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
            QDRANT_DB_DIR.mkdir(parents=True, exist_ok=True)
            self._memory = Memory.from_config(config)
            logger.info("mem0 Memory initialized with Qdrant at {}", QDRANT_DB_DIR)
        except Exception as exc:
            logger.error("Failed to initialize mem0 Memory: {}", exc)
            self._memory_failed = True

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

    def _build_graph_node(self, chunk: NoteChunk, note_title: str) -> GraphNode:
        label = chunk.heading.strip() or note_title.strip() or f"Chunk {chunk.chunk_index + 1}"
        preview = chunk.content.strip().replace("\n", " ")
        if len(preview) > 120:
            preview = f"{preview[:117]}..."
        return GraphNode(
            id=chunk.chunk_id,
            label=label,
            group=chunk.note_id,
            note_id=chunk.note_id,
            note_title=note_title,
            chunk_index=chunk.chunk_index,
            content_preview=preview,
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

    def search(self, student_id: str, query: str, limit: int = 10) -> list[SearchResult]:
        memory = self._require_memory()
        results = memory.search(query=query, user_id=student_id, limit=limit)
        return [self._build_search_result(item) for item in results]

    def ask(self, student_id: str, question: str) -> tuple[str, list[SearchResult]]:
        sources = self.search(student_id, question, limit=5)

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
    ) -> GraphResponse:
        memory = self._require_memory()

        notes = self._note_store.list_by_student(student_id, course_id)
        if not notes:
            return GraphResponse(
                top_k=top_k,
                min_score=min_score,
                course_id=course_id,
            )

        note_titles = {
            note.id: (note.title.strip() or note.filename)
            for note in notes
        }
        all_user_chunks = [
            chunk for chunk in self._note_store.list_chunks_by_student(student_id) if chunk.content.strip()
        ]
        if not all_user_chunks:
            return GraphResponse(
                top_k=top_k,
                min_score=min_score,
                course_id=course_id,
            )

        allowed_note_ids = set(note_titles)
        candidate_chunks = [
            chunk for chunk in all_user_chunks if chunk.note_id in allowed_note_ids
        ]
        truncated = len(candidate_chunks) > max_nodes
        candidate_chunks = candidate_chunks[:max_nodes]
        allowed_chunk_ids = {chunk.chunk_id for chunk in candidate_chunks}

        nodes = [
            self._build_graph_node(chunk, note_titles.get(chunk.note_id, ""))
            for chunk in candidate_chunks
        ]
        if not nodes:
            return GraphResponse(
                top_k=top_k,
                min_score=min_score,
                course_id=course_id,
                truncated=truncated,
            )

        search_limit = max(top_k + 1, len(all_user_chunks) + 1)
        edge_map: dict[tuple[str, str], GraphLink] = {}

        for chunk in candidate_chunks:
            kept_neighbors = 0
            results = memory.search(
                query=chunk.content,
                user_id=student_id,
                limit=search_limit,
            )

            for item in results:
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
            total_nodes=len(nodes),
            total_links=len(links),
            truncated=truncated,
        )
        logger.info(
            "Built knowledge graph for {} with {} nodes and {} links (course_id={}, top_k={}, min_score={})",
            student_id,
            graph.total_nodes,
            graph.total_links,
            course_id,
            top_k,
            min_score,
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
