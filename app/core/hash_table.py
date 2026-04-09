from __future__ import annotations

from typing import Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")


class HashTable(Generic[K, V]):
    """占位接口，后续替换为手写哈希表实现。"""

    def set(self, key: K, value: V) -> None:
        raise NotImplementedError

    def get(self, key: K) -> V | None:
        raise NotImplementedError

    def delete(self, key: K) -> None:
        raise NotImplementedError
