from __future__ import annotations

import json
import re
from typing import Any

from app.config import DEEPSEEK_MODEL
from app.logging_config import logger
from app.models.knowledge import KnowledgeTree
from app.models.note import GraphLink, GraphNode, GraphResponse, NoteChunk, SearchResult
from app.storage.knowledge_tree_store import KnowledgeTreeStore
from app.storage.note_store import NoteStore


class KnowledgeSearchOperations:
    """检索、问答、图谱构建"""

    def __init__(
        self,
        note_store: NoteStore,
        tree_store: KnowledgeTreeStore,
        memory: Any | None = None,
        llm_client: Any | None = None,
        collect_topic_note_ids_fn: callable = None,
    ) -> None:
        self._note_store = note_store
        self._tree_store = tree_store
        self._memory = memory
        self._llm_client = llm_client
        self._collect_topic_note_ids = collect_topic_note_ids_fn

    def _tokenize(self, text: str) -> list[str]:
        return re.findall(r"[A-Za-z0-9_]+|[一-鿿]", text.casefold())

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

    def _chunk_search_text(self, chunk: NoteChunk, note_title: str = "") -> str:
        parts = [chunk.heading.strip(), note_title.strip(), chunk.content.strip()]
        return "\n".join(part for part in parts if part)

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

    def _search_lexically(
        self,
        student_id: str,
        query: str,
        limit: int,
        course_id: str | None = None,
        topic_id: str | None = None,
    ) -> list[SearchResult]:
        allowed_note_ids: set[str] | None = None
        if topic_id is not None and self._collect_topic_note_ids is not None:
            tree = self._tree_store.load(student_id, course_id)
            allowed_note_ids = self._collect_topic_note_ids(tree, topic_id)
            if not allowed_note_ids:
                return []

        notes = self._note_store.list_by_student(student_id, course_id)
        if not notes:
            return []

        if allowed_note_ids is not None:
            notes = [note for note in notes if note.id in allowed_note_ids]
            if not notes:
                return []

        note_titles = {
            note.id: (note.title.strip() or note.filename)
            for note in notes
        }
        scored_chunks: list[tuple[float, NoteChunk]] = []
        for chunk in self._note_store.list_chunks_by_student(student_id, course_id):
            if allowed_note_ids is not None and chunk.note_id not in allowed_note_ids:
                continue
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
        if self._memory is None:
            raise RuntimeError("向量索引服务不可用")

        count = 0
        for chunk in chunks:
            if not chunk.content.strip():
                continue
            self._memory.add(
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
        topic_id: str | None = None,
    ) -> list[SearchResult]:
        if self._memory is None:
            logger.warning(
                "Chunk memory unavailable; falling back to lexical search for {} (course_id={}, topic_id={})",
                student_id,
                course_id,
                topic_id,
            )
            return self._search_lexically(student_id, query, limit, course_id, topic_id)

        allowed_note_ids: set[str] | None = None
        fetch_limit = max(limit, 1)

        if topic_id is not None and self._collect_topic_note_ids is not None:
            tree = self._tree_store.load(student_id, course_id)
            topic_note_ids = self._collect_topic_note_ids(tree, topic_id)
            if not topic_note_ids:
                return []
            allowed_note_ids = topic_note_ids
            fetch_limit = max(limit * 4, 20)
        elif course_id is not None:
            allowed_note_ids = {
                note.id for note in self._note_store.list_by_student(student_id, course_id)
            }
            if not allowed_note_ids:
                return []
            fetch_limit = max(limit * 4, 20)

        raw_results = self._memory.search(query=query, filters={"user_id": student_id}, limit=fetch_limit)

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
        topic_id: str | None = None,
    ) -> tuple[str, list[SearchResult]]:
        sources = self.search(student_id, question, limit=5, course_id=course_id, topic_id=topic_id)

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
        resolve_selected_topic_ids_fn: callable = None,
        candidate_note_ids_from_topics_fn: callable = None,
        note_topic_map_fn: callable = None,
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

        tree = self._tree_store.load(student_id, course_id)
        selected_topic_ids: list[str] = []
        routing_applied = False
        allowed_note_ids = set(note_titles)
        if tree.topics and (query.strip() or topic_id) and resolve_selected_topic_ids_fn is not None:
            selected_topic_ids = resolve_selected_topic_ids_fn(
                student_id=student_id,
                tree=tree,
                query=query,
                topic_id=topic_id,
                topic_limit=topic_limit,
            )
            routing_applied = True
            if candidate_note_ids_from_topics_fn is not None:
                allowed_note_ids = candidate_note_ids_from_topics_fn(tree, selected_topic_ids)

        candidate_chunks = [
            chunk for chunk in all_course_chunks if chunk.note_id in allowed_note_ids
        ]
        truncated = len(candidate_chunks) > max_nodes
        candidate_chunks = candidate_chunks[:max_nodes]
        allowed_chunk_ids = {chunk.chunk_id for chunk in candidate_chunks}
        note_topic_map = note_topic_map_fn(tree) if note_topic_map_fn is not None else {}

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
            "Built knowledge graph for  with {} nodes and {} links (course_id={}, top_k={}, min_score={}, selected_topics={})",
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
