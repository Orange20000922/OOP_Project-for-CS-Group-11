from __future__ import annotations

import json

import pytest

from app.core.hash_table import HashTable


def test_set_get_update_and_contains():
    table = HashTable[str, int](bucket_count=4)

    table.set("alice", 1)
    table.set("bob", 2)
    table.set("alice", 3)

    assert len(table) == 2
    assert table.get("alice") == 3
    assert table.get("bob") == 2
    assert table.get("missing") is None
    assert "alice" in table
    assert "missing" not in table


def test_collision_chain_keeps_all_values(monkeypatch: pytest.MonkeyPatch):
    table = HashTable[str, int](bucket_count=2)
    monkeypatch.setattr(table, "_hash", lambda key: 1)

    table.set("a", 10)
    table.set("b", 20)
    table.set("c", 30)

    assert table.get("a") == 10
    assert table.get("b") == 20
    assert table.get("c") == 30
    assert list(table.items()) == [("a", 10), ("b", 20), ("c", 30)]


def test_delete_head_middle_and_tail_under_collision(monkeypatch: pytest.MonkeyPatch):
    table = HashTable[str, int](bucket_count=2)
    monkeypatch.setattr(table, "_hash", lambda key: 1)

    table.set("a", 10)
    table.set("b", 20)
    table.set("c", 30)

    table.delete("a")
    assert list(table.items()) == [("b", 20), ("c", 30)]

    table.delete("b")
    assert list(table.items()) == [("c", 30)]

    table.delete("c")
    assert len(table) == 0
    assert list(table.items()) == []


def test_delete_missing_key_raises_key_error():
    table = HashTable[str, int]()

    with pytest.raises(KeyError):
        table.delete("missing")


def test_resize_preserves_entries():
    table = HashTable[str, int](bucket_count=2, load_factor=0.5)

    for index in range(6):
        table.set(f"key-{index}", index)

    assert len(table) == 6
    for index in range(6):
        assert table.get(f"key-{index}") == index


def test_to_dict_and_to_serializable_are_json_compatible():
    table = HashTable[str, object](bucket_count=4)
    table.set("name", "course-system")
    table.set("meta", {"semester": "2025-2026-2", "weeks": [1, 2, 3]})

    dumped_dict = json.dumps(table.to_dict(), ensure_ascii=False)
    dumped_payload = json.dumps(table.to_serializable(), ensure_ascii=False)

    assert '"name": "course-system"' in dumped_dict
    assert '"bucket_count"' in dumped_payload
    assert '"semester": "2025-2026-2"' in dumped_payload


def test_clear_removes_all_entries():
    table = HashTable[str, int]()
    table.set("x", 1)
    table.set("y", 2)

    table.clear()

    assert len(table) == 0
    assert list(table.keys()) == []
    assert table.get("x") is None
