from __future__ import annotations

from typing import Generic, Iterator, TypeVar

T = TypeVar("T")


class DoublyLinkedList(Generic[T]):
    """占位接口，后续替换为手写双向链表实现。"""

    def append(self, value: T) -> None:
        raise NotImplementedError

    def remove(self, value: T) -> None:
        raise NotImplementedError

    def __iter__(self) -> Iterator[T]:
        raise NotImplementedError
