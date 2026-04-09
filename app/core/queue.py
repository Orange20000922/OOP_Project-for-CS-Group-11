from __future__ import annotations

from typing import Generic, TypeVar

T = TypeVar("T")


class TaskQueue(Generic[T]):
    """占位接口，后续替换为手写队列实现。"""

    def enqueue(self, item: T) -> None:
        raise NotImplementedError

    def dequeue(self) -> T | None:
        raise NotImplementedError

    def is_empty(self) -> bool:
        raise NotImplementedError
