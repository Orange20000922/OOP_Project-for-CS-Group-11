from __future__ import annotations

import re
from pathlib import Path
from threading import Lock

from app.config import DATA_DIR
from app.logging_config import logger
from app.models.knowledge import KnowledgeTree
from app.storage.file_io import model_to_dict, read_json, write_json_atomic


class KnowledgeTreeStore:
    def __init__(self, root_dir: Path | None = None) -> None:
        self._root_dir = Path(root_dir) if root_dir is not None else (DATA_DIR / "knowledge_trees")
        self._root_dir.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        logger.debug("KnowledgeTreeStore initialized with {}", self._root_dir)

    def _course_key(self, course_id: str | None) -> str:
        raw = course_id or "_uncategorized"
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", raw).strip("._")
        return safe or "_uncategorized"

    def _path(self, student_id: str, course_id: str | None) -> Path:
        return self._root_dir / student_id / f"{self._course_key(course_id)}.json"

    def load(self, student_id: str, course_id: str | None = None) -> KnowledgeTree:
        default = KnowledgeTree(student_id=student_id, course_id=course_id)
        payload = read_json(self._path(student_id, course_id), default.model_dump())
        return KnowledgeTree(**payload)

    def save(self, tree: KnowledgeTree) -> KnowledgeTree:
        with self._lock:
            write_json_atomic(
                self._path(tree.student_id, tree.course_id),
                model_to_dict(tree),
            )
        logger.info(
            "Saved knowledge tree for {} (course_id={}, topics={})",
            tree.student_id,
            tree.course_id,
            len(tree.topics),
        )
        return tree

    def delete(self, student_id: str, course_id: str | None = None) -> None:
        path = self._path(student_id, course_id)
        if not path.exists():
            return
        with self._lock:
            path.unlink(missing_ok=True)
        logger.info("Deleted knowledge tree for {} (course_id={})", student_id, course_id)
