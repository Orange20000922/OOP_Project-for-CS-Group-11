
from typing import Any


class Stack:
    # 简单的栈实现 - 用于知识树DFS等算法
    def __init__(self):
        self._items: list[Any] = []

    def push(self, item: Any) -> None:
        self._items.append(item)

    def pop(self) -> Any:
        if self.is_empty():
            raise IndexError("Stack is empty")
        return self._items.pop()

    def peek(self) -> Any:
        if self.is_empty():
            return None
        return self._items[-1]

    def is_empty(self) -> bool:
        return len(self._items) == 0

    def size(self) -> int:
        return len(self._items)

    def clear(self) -> None:
        self._items.clear()

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self):
        """不支持迭代 - 栈不应该被随机访问"""
        raise TypeError("Stack does not support iteration")

    def __repr__(self) -> str:
        return f"Stack(size={len(self._items)}, top={self.peek()})"
