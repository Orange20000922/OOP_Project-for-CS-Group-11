from __future__ import annotations

from typing import Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")

class BSTNode(Generic[K, V]):
    def __init__(self, key: K, value: V):
        self.key = key
        self.value = value
        self.left: BSTNode[K, V] | None = None
        self.right: BSTNode[K, V] | None = None

class BinarySearchTree(Generic[K, V]):
    def insert(self, key: K, value: V) -> None:
        def _insert(node: BSTNode[K, V] | None, key: K, value: V) -> BSTNode[K, V]:
            if node is None:
                return BSTNode(key, value)
            if key < node.key:
                node.left = _insert(node.left, key, value)
            elif key > node.key:
                node.right = _insert(node.right, key, value)
            else:
                node.value = value
            return node
        self.root = _insert(self.root, key, value)

    def search(self, key: K) -> V | None:
        def _search(node: BSTNode[K, V] | None, key: K) -> V | None:
            if node is None or node.key == key:
                return node.value if node else None
            if key < node.key:
                return _search(node.left, key)
            return _search(node.right, key)
        return _search(self.root, key)

    def delete(self, key: K) -> None:
        def _find_min(node: BSTNode[K, V]) -> BSTNode[K, V]:
            current = node
            while current.left is not None:
                current = current.left
            return current
        def _delete(node: BSTNode[K, V] | None, key: K) -> BSTNode[K, V] | None:
            if node is None:
                return None
            if key < node.key:
                node.left = _delete(node.left, key)
            elif key > node.key:
                node.right = _delete(node.right, key)
            else:
                if node.left is None:
                    return node.right
                if node.right is None:
                    return node.left
                min_node = _find_min(node.right)
                node.key = min_node.key
                node.value = min_node.value
                node.right = _delete(node.right, min_node.key)
            return node
        self.root = _delete(self.root, key)