from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from app.config import HF_CACHE_DIR, QDRANT_DB_DIR
from app.logging_config import logger

TOPIC_VECTOR_COLLECTION = "course_note_topics"
TOPIC_VECTOR_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class TopicVectorStore:
    def __init__(
        self,
        root_dir: Path | None = None,
        cache_dir: Path | None = None,
        model_name: str = TOPIC_VECTOR_MODEL,
        collection_name: str = TOPIC_VECTOR_COLLECTION,
    ) -> None:
        self._root_dir = Path(root_dir) if root_dir is not None else (QDRANT_DB_DIR / "topic_vectors")
        self._cache_dir = Path(cache_dir) if cache_dir is not None else HF_CACHE_DIR
        self._model_name = model_name
        self._collection_name = collection_name
        self._client: Any | None = None
        self._embedder: Any | None = None
        self._vector_size: int | None = None

    def close(self) -> None:
        client = self._client
        self._client = None

        if client is not None:
            try:
                client.close()
                logger.info("Closed topic vector store client for {}", self._collection_name)
            except Exception as exc:
                logger.warning(
                    "Failed to close topic vector store client for {}: {}",
                    self._collection_name,
                    exc,
                )

        self._embedder = None

    def _load_embedder(self) -> Any:
        from sentence_transformers import SentenceTransformer

        attempts: list[tuple[str, dict[str, Any]]] = [
            ("project cache", {"cache_folder": str(self._cache_dir)}),
            ("default cache", {}),
        ]
        last_error: Exception | None = None

        for label, kwargs in attempts:
            try:
                embedder = SentenceTransformer(self._model_name, **kwargs)
                logger.info("Topic embedder initialized with {}", label)
                return embedder
            except Exception as exc:
                last_error = exc
                logger.warning("Failed to initialize topic embedder with {}: {}", label, exc)

        assert last_error is not None
        raise last_error

    def _ensure_embedder(self) -> None:
        if self._embedder is not None:
            return

        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._embedder = self._load_embedder()
        dimension_getter = getattr(self._embedder, "get_embedding_dimension", None)
        if dimension_getter is None:
            dimension_getter = getattr(self._embedder, "get_sentence_embedding_dimension")
        self._vector_size = int(dimension_getter())

    def _ensure_client(self) -> None:
        if self._client is not None:
            return

        from qdrant_client import QdrantClient, models

        self._ensure_embedder()
        self._root_dir.mkdir(parents=True, exist_ok=True)
        self._client = QdrantClient(
            path=str(self._root_dir),
            force_disable_check_same_thread=True,
        )

        if not self._client.collection_exists(self._collection_name):
            self._client.create_collection(
                collection_name=self._collection_name,
                vectors_config=models.VectorParams(
                    size=int(self._vector_size or 384),
                    distance=models.Distance.COSINE,
                    on_disk=True,
                ),
                on_disk_payload=True,
            )
            logger.info("Created topic vector collection {}", self._collection_name)

    def _encode(self, text: str) -> list[float]:
        self._ensure_embedder()
        vector = self._embedder.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return vector.tolist()

    def _course_marker(self, course_id: str | None) -> str:
        return course_id or ""

    def _topic_filter(
        self,
        student_id: str,
        course_id: str | None,
        topic_id: str | None = None,
    ):
        from qdrant_client import models

        conditions = [
            models.FieldCondition(key="student_id", match=models.MatchValue(value=student_id)),
            models.FieldCondition(
                key="course_id",
                match=models.MatchValue(value=self._course_marker(course_id)),
            ),
        ]
        if topic_id is not None:
            conditions.append(models.FieldCondition(key="topic_id", match=models.MatchValue(value=topic_id)))
        return models.Filter(must=conditions)

    def _point_id(self, student_id: str, course_id: str | None, topic_id: str) -> str:
        raw = f"{student_id}:{self._course_marker(course_id)}:{topic_id}"
        return str(uuid5(NAMESPACE_URL, raw))

    def upsert_topic(
        self,
        student_id: str,
        course_id: str | None,
        topic_id: str,
        topic_name: str,
        text: str,
    ) -> None:
        from qdrant_client import models

        self._ensure_client()
        vector = self._encode(text)
        self._client.upsert(
            collection_name=self._collection_name,
            points=[
                models.PointStruct(
                    id=self._point_id(student_id, course_id, topic_id),
                    vector=vector,
                    payload={
                        "student_id": student_id,
                        "course_id": self._course_marker(course_id),
                        "topic_id": topic_id,
                        "topic_name": topic_name,
                    },
                )
            ],
            wait=True,
        )

    def delete_topic(
        self,
        student_id: str,
        course_id: str | None,
        topic_id: str,
    ) -> None:
        from qdrant_client import models

        self._ensure_client()
        self._client.delete(
            collection_name=self._collection_name,
            points_selector=models.FilterSelector(
                filter=self._topic_filter(student_id, course_id, topic_id)
            ),
            wait=True,
        )

    def search_topics(
        self,
        student_id: str,
        course_id: str | None,
        query: str,
        limit: int,
    ) -> list[tuple[str, float]]:
        self._ensure_client()
        response = self._client.query_points(
            collection_name=self._collection_name,
            query=self._encode(query),
            query_filter=self._topic_filter(student_id, course_id),
            with_payload=True,
            limit=max(limit * 4, 10),
        )

        scores: dict[str, float] = {}
        for point in response.points:
            payload = point.payload or {}
            topic_id = str(payload.get("topic_id", ""))
            if not topic_id:
                continue
            score = float(point.score or 0.0)
            current = scores.get(topic_id)
            if current is None or score > current:
                scores[topic_id] = score

        return sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:limit]
