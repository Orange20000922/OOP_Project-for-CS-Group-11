from __future__ import annotations

from pathlib import Path

import pytest

from app.core import HashTable
from app.models.user import User
from app.storage.file_io import ensure_json_file, read_json
from app.storage.user_store import UserStore


def test_ensure_json_file_creates_default(storage_paths):
    path = storage_paths["data_dir"] / "sample.json"
    ensure_json_file(path, {"ok": True})

    assert path.exists()
    assert read_json(path, {}) == {"ok": True}


def test_read_json_invalid_logs(storage_paths, log_records):
    broken = Path(storage_paths["data_dir"]) / "broken.json"
    broken.parent.mkdir(parents=True, exist_ok=True)
    broken.write_text("{broken", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid JSON"):
        read_json(broken, {})

    assert any("Failed to decode JSON file" in record["message"] for record in log_records)


def test_user_store_duplicate_user_logs(user_store, log_records):
    assert isinstance(user_store._users, HashTable)

    user = User(
        student_id="20250001",
        name="张三",
        password_hash="hashed",
        scnu_account="20250001",
    )
    user_store.create(user)

    with pytest.raises(ValueError, match="该学号已注册"):
        user_store.create(user)

    assert any("duplicate user" in record["message"] for record in log_records)


def test_user_store_loads_existing_users_into_hash_index(storage_paths):
    storage_paths["users_file"].parent.mkdir(parents=True, exist_ok=True)
    storage_paths["users_file"].write_text(
        (
            '{"users": ['
            '{"student_id": "20250002", "name": "李四", "password_hash": "h2", "scnu_account": "scnu02"},'
            '{"student_id": "20250001", "name": "张三", "password_hash": "h1", "scnu_account": "scnu01"}'
            "]}"
        ),
        encoding="utf-8",
    )

    store = UserStore()

    assert isinstance(store._users, HashTable)
    assert store.get("20250001") is not None
    assert [user.student_id for user in store.list_users()] == ["20250001", "20250002"]


def test_schedule_store_add_update_delete(schedule_store, make_course):
    schedule_store.initialize("20250001", "2025-2026-2", "2026-03-02")

    created = schedule_store.add_course("20250001", make_course())
    assert created.id

    updated = schedule_store.update_course(
        "20250001",
        created.id,
        make_course(name="数据结构", weekday=3, period_start=3, period_end=4),
    )
    assert updated.name == "数据结构"

    schedule = schedule_store.get("20250001")
    assert schedule is not None
    assert [course.name for course in schedule.courses] == ["数据结构"]

    schedule_store.delete_course("20250001", created.id)
    assert schedule_store.get("20250001").courses == []


def test_schedule_store_missing_schedule_logs(schedule_store, make_course, log_records):
    with pytest.raises(ValueError, match="请先初始化课表"):
        schedule_store.add_course("20250001", make_course())

    assert any("before schedule initialization" in record["message"] for record in log_records)


def test_schedule_store_missing_course_logs(schedule_store, make_course, log_records):
    schedule_store.initialize("20250001", "2025-2026-2", "2026-03-02")

    with pytest.raises(ValueError, match="未找到对应课程"):
        schedule_store.update_course("20250001", "missing-course", make_course())

    with pytest.raises(ValueError, match="未找到对应课程"):
        schedule_store.delete_course("20250001", "missing-course")

    assert any("missing course" in record["message"] for record in log_records)
