from __future__ import annotations

from threading import Lock

from app.config import USERS_FILE
from app.core import HashTable
from app.logging_config import logger
from app.models.user import User
from app.storage.file_io import ensure_json_file, model_to_dict, read_json, write_json_atomic


class UserStore:
    def __init__(self) -> None:
        self._lock = Lock()
        ensure_json_file(USERS_FILE, {"users": []})
        self._users = HashTable[str, User](bucket_count=32)
        self._load_index()
        logger.debug("UserStore initialized with {}", USERS_FILE)

    def _read_all_from_disk(self) -> list[User]:
        payload = read_json(USERS_FILE, {"users": []})
        return [User(**item) for item in payload.get("users", [])]

    def _load_index(self) -> None:
        self._users.clear()
        for user in self._read_all_from_disk():
            self._users[user.student_id] = user
        logger.debug("Loaded {} users into in-memory index", len(self._users))

    def _save_all(self, users: list[User]) -> None:
        write_json_atomic(USERS_FILE, {"users": [model_to_dict(user) for user in users]})

    def list_users(self) -> list[User]:
        return sorted(self._users.values(), key=lambda user: user.student_id)

    def get(self, student_id: str) -> User | None:
        return self._users.get(student_id)

    def create(self, user: User) -> User:
        with self._lock:
            if user.student_id in self._users:
                logger.warning("Attempted to create duplicate user {}", user.student_id)
                raise ValueError("该学号已注册")
            users = self.list_users()
            users.append(user)
            self._save_all(users)
            self._users[user.student_id] = user
            logger.info("Created user {}", user.student_id)
        return user
