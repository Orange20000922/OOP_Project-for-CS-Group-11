from __future__ import annotations
from typing import Generic, TypeVar

T = TypeVar("T")


class _Node(Generic[T]):
    def __init__(self, value: T):
        self.value = value
        self.next: _Node[T] | None = None


class TaskQueue(Generic[T]):
    """手写链式队列：FIFO"""

    def __init__(self) -> None:
        self.head: _Node[T] | None = None
        self.tail: _Node[T] | None = None
        self._size = 0

    def enqueue(self, item: T) -> None:
        new_node = _Node(item)

        if self.tail is None:
            self.head = self.tail = new_node
        else:
            self.tail.next = new_node
            self.tail = new_node

        self._size += 1

    def dequeue(self) -> T | None:
        if self.is_empty():
            return None

        assert self.head is not None
        value = self.head.value
        self.head = self.head.next

        if self.head is None:
            self.tail = None

        self._size -= 1
        return value

    def peek(self) -> T | None:
        if self.is_empty():
            return None
        assert self.head is not None
        return self.head.value

    def is_empty(self) -> bool:
        return self._size == 0

    def size(self) -> int:
        return self._size

    def __len__(self) -> int:
        return self._size

    def __repr__(self) -> str:
        items = []
        current = self.head
        while current is not None:
            items.append(str(current.value))
            current = current.next
        return "TaskQueue: [" + " -> ".join(items) + "]"


if __name__ == "__main__":
    q = TaskQueue[str]()

    print("初始状态:", q)
    q.enqueue("任务1")
    q.enqueue("任务2")
    print("入队后:", q)
    print("队头元素:", q.peek())
    print("出队:", q.dequeue())
    print("出队:", q.dequeue())
    print("最终状态:", q)
