from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from app.core import Stack
from app.logging_config import logger
from app.models.knowledge import KnowledgeTopic, KnowledgeTopicCreate, KnowledgeTopicUpdate, KnowledgeTree
from app.models.note import Note, NoteChunk
from app.storage.knowledge_tree_store import KnowledgeTreeStore
from app.storage.note_store import NoteStore

if TYPE_CHECKING:
    from app.services.topic_vector_store import TopicVectorStore


class KnowledgeTreeOperations:
    """知识树 CRUD、主题管理、自动分配"""

    def __init__(
        self,
        note_store: NoteStore,
        tree_store: KnowledgeTreeStore,
        topic_vector_store: TopicVectorStore | None = None,
    ) -> None:
        self._note_store = note_store
        self._tree_store = tree_store
        self._topic_store = topic_vector_store

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

    def get_tree(self, student_id: str, course_id: str | None = None) -> KnowledgeTree:
        return self._tree_store.load(student_id, course_id)

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
        stack = Stack()
        stack.push(topic_id)
        seen: set[str] = set()

        while not stack.is_empty():
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            topic = tree.topics.get(current)
            if topic is None:
                continue
            ordered.append(current)
            for child_id in reversed(topic.child_ids):
                stack.push(child_id)
        return ordered

    def collect_topic_note_ids(self, tree: KnowledgeTree, topic_id: str) -> set[str]:
        topic_ids = self._collect_descendant_topic_ids(tree, topic_id)
        note_ids: set[str] = set()
        for tid in topic_ids:
            topic = tree.topics.get(tid)
            if topic is not None:
                note_ids.update(topic.note_ids)
        return note_ids

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

    def reindex_topic(self, student_id: str, course_id: str | None, tree: KnowledgeTree, topic_id: str) -> None:
        topic = tree.topics.get(topic_id)
        if topic is None:
            return
        if self._topic_store is None:
            return

        notes_by_id = self._notes_by_id(student_id, course_id)
        payload = self._topic_text(topic, notes_by_id).strip()
        try:
            self._topic_store.delete_topic(student_id, course_id, topic_id)
        except Exception as exc:
            logger.warning("Failed to delete stale topic vector for : {}", topic_id, exc)
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
        if self._topic_store is None:
            return
        try:
            self._topic_store.delete_topic(student_id, course_id, topic_id)
        except Exception as exc:
            logger.warning("Failed to delete topic vector for {}: {}", topic_id, exc)

    def create_topic(self, student_id: str, payload: KnowledgeTopicCreate) -> KnowledgeTree:
        tree = self.get_tree(student_id, payload.course_id)
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
        self.reindex_topic(student_id, tree.course_id, tree, topic.id)
        return tree

    def update_topic(
        self,
        student_id: str,
        course_id: str | None,
        topic_id: str,
        payload: KnowledgeTopicUpdate,
    ) -> KnowledgeTree:
        tree = self.get_tree(student_id, course_id)
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
        self.reindex_topic(student_id, tree.course_id, tree, topic.id)
        return tree

    def delete_topic(self, student_id: str, course_id: str | None, topic_id: str) -> KnowledgeTree:
        tree = self.get_tree(student_id, course_id)
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
            self.reindex_topic(student_id, tree.course_id, tree, touched_topic_id)
        return tree

    def remove_note_from_topics(
        self,
        student_id: str,
        note_id: str,
        course_id: str | None,
    ) -> KnowledgeTree:
        tree = self.get_tree(student_id, course_id)
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
            self.reindex_topic(student_id, tree.course_id, tree, topic_id)
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
        self.reindex_topic(student_id, tree.course_id, tree, topic.id)
        return tree

    def unassign_note_from_topic(
        self,
        student_id: str,
        course_id: str | None,
        topic_id: str,
        note_id: str,
    ) -> KnowledgeTree:
        tree = self.get_tree(student_id, course_id)
        topic = self._get_topic_or_raise(tree, topic_id)
        if note_id not in topic.note_ids:
            return tree
        self._remove_value(topic.note_ids, note_id)
        topic.updated_at = datetime.now().isoformat()
        self._save_tree(tree)
        self.reindex_topic(student_id, tree.course_id, tree, topic.id)
        return tree

    def refresh_topics_for_note(self, student_id: str, note: Note) -> None:
        if note.course_id is None:
            return
        tree = self.get_tree(student_id, note.course_id)
        for topic in tree.topics.values():
            if note.id in topic.note_ids:
                self.reindex_topic(student_id, tree.course_id, tree, topic.id)

    def rank_topics(
        self,
        student_id: str,
        tree: KnowledgeTree,
        query: str,
        limit: int = 3,
        lexical_similarity_fn: callable = None,
    ) -> list[tuple[str, float]]:
        if self._topic_store is not None:
            ranked = self._topic_store.search_topics(
                student_id=student_id,
                course_id=tree.course_id,
                query=query,
                limit=limit,
            )
            ranked = [
                (topic_id, score)
                for topic_id, score in ranked
                if topic_id in tree.topics
            ]
            if ranked:
                return ranked

        if lexical_similarity_fn is None:
            return []

        notes_by_id = self._notes_by_id(student_id, tree.course_id)
        scored: list[tuple[str, float]] = []
        for topic in tree.topics.values():
            score = lexical_similarity_fn(query, self._topic_text(topic, notes_by_id))
            if score > 0:
                scored.append((topic.id, score))
        scored.sort(key=lambda item: (-item[1], item[0]))
        return scored[:limit]

    def auto_assign_note(
        self,
        student_id: str,
        note: Note,
        chunks: list[NoteChunk],
        min_score: float = 0.15,
        lexical_similarity_fn: callable = None,
    ) -> str | None:
        if note.course_id is None:
            return None
        tree = self.get_tree(student_id, note.course_id)
        if not tree.topics:
            return None

        query_parts: list[str] = []
        if note.title.strip():
            query_parts.append(note.title.strip())
        if note.summary.strip():
            query_parts.append(note.summary.strip())
        for chunk in chunks[:3]:
            if chunk.heading.strip():
                query_parts.append(chunk.heading.strip())
        query = " ".join(query_parts)
        if not query.strip():
            return None

        ranked = self.rank_topics(student_id, tree, query, limit=1, lexical_similarity_fn=lexical_similarity_fn)
        if not ranked:
            return None
        topic_id, score = ranked[0]
        if score < min_score:
            return None

        try:
            self.assign_note_to_topic(student_id, note.course_id, topic_id, note.id)
            logger.info("Auto-assigned note {} to topic {} (score={:.2f})", note.id, topic_id, score)
            return topic_id
        except Exception as exc:
            logger.warning("Failed to auto-assign note {} to topic {}: {}", note.id, topic_id, exc)
            return None
