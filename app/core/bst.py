from __future__ import annotations

from typing import Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")


class BinarySearchTree(Generic[K, V]):
    """占位接口，后续替换为手写 BST 实现。"""

    def insert(self, key: K, value: V) -> None:
        raise NotImplementedError

    def search(self, key: K) -> V | None:
        raise NotImplementedError

    def delete(self, key: K) -> None:
        raise NotImplementedError
