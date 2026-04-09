from __future__ import annotations

from threading import Lock

from app.config import USERS_FILE
from app.models.user import User
from app.storage.file_io import ensure_json_file, model_to_dict, read_json, write_json_atomic


class UserStore:
    def __init__(self) -> None:
        self._lock = Lock()
        ensure_json_file(USERS_FILE, {"users": []})

    def _load_all(self) -> list[User]:
        payload = read_json(USERS_FILE, {"users": []})
        return [User(**item) for item in payload.get("users", [])]

    def _save_all(self, users: list[User]) -> None:
        write_json_atomic(USERS_FILE, {"users": [model_to_dict(user) for user in users]})

    def list_users(self) -> list[User]:
        return self._load_all()

    def get(self, student_id: str) -> User | None:
        for user in self._load_all():
            if user.student_id == student_id:
                return user
        return None

    def create(self, user: User) -> User:
        with self._lock:
            users = self._load_all()
            if any(item.student_id == user.student_id for item in users):
                raise ValueError("该学号已注册")
            users.append(user)
            self._save_all(users)
        return user
