from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, Iterator, TypeVar

K = TypeVar("K")
V = TypeVar("V")
_MISSING = object()


@dataclass(slots=True)
class _Node(Generic[K, V]):
    key: K
    value: V
    next: _Node[K, V] | None = None


@dataclass(slots=True)
class _Bucket(Generic[K, V]):
    tail: _Node[K, V] | None = None
    size: int = 0

    def append(self, node: _Node[K, V]) -> None:
        if self.tail is None:
            node.next = node
        else:
            node.next = self.tail.next
            self.tail.next = node
        self.tail = node
        self.size += 1

    def find(self, key: K) -> _Node[K, V] | None:
        if self.tail is None:
            return None

        current = self.tail.next
        while current is not None:
            if current.key == key:
                return current
            if current is self.tail:
                break
            current = current.next
        return None

    def delete(self, key: K) -> V | object:
        if self.tail is None:
            return _MISSING

        previous = self.tail
        current = self.tail.next
        while current is not None:
            if current.key == key:
                removed_value = current.value
                if current is self.tail and current.next is current:
                    self.tail = None
                else:
                    previous.next = current.next
                    if current is self.tail:
                        self.tail = previous
                self.size -= 1
                return removed_value
            if current is self.tail:
                break
            previous = current
            current = current.next
        return _MISSING

    def __iter__(self) -> Iterator[_Node[K, V]]:
        if self.tail is None:
            return

        current = self.tail.next
        while current is not None:
            yield current
            if current is self.tail:
                break
            current = current.next


class HashTable(Generic[K, V]):
    def __init__(self, bucket_count: int = 16, load_factor: float = 0.75) -> None:
        if bucket_count <= 0:
            raise ValueError("bucket_count must be positive")
        if not 0 < load_factor <= 1:
            raise ValueError("load_factor must be within (0, 1]")

        self._buckets: list[_Bucket[K, V] | None] = [None] * bucket_count
        self._size = 0
        self._load_factor = load_factor

    def set(self, key: K, value: V) -> None:
        bucket = self._bucket_for(key)
        if bucket is not None:
            node = bucket.find(key)
            if node is not None:
                node.value = value
                return

        if (self._size + 1) / len(self._buckets) > self._load_factor:
            self._resize()

        bucket = self._bucket_for(key, create=True)
        bucket.append(_Node(key=key, value=value))
        self._size += 1

    def get(self, key: K, default: Any = None) -> V | Any:
        bucket = self._bucket_for(key)
        if bucket is None:
            return default
        node = bucket.find(key)
        if node is None:
            return default
        return node.value

    def delete(self, key: K) -> None:
        self.pop(key)

    def pop(self, key: K, default: Any = _MISSING) -> V | Any:
        bucket_index = self._bucket_index(key)
        bucket = self._buckets[bucket_index]
        if bucket is None:
            if default is _MISSING:
                raise KeyError(key)
            return default

        removed = bucket.delete(key)
        if removed is _MISSING:
            if default is _MISSING:
                raise KeyError(key)
            return default

        self._size -= 1
        if bucket.size == 0:
            self._buckets[bucket_index] = None
        return removed

    def contains(self, key: K) -> bool:
        return self.get(key, _MISSING) is not _MISSING

    def items(self) -> Iterator[tuple[K, V]]:
        for bucket in self._buckets:
            if bucket is None:
                continue
            for node in bucket:
                yield node.key, node.value

    def keys(self) -> Iterator[K]:
        for key, _ in self.items():
            yield key

    def values(self) -> Iterator[V]:
        for _, value in self.items():
            yield value

    def to_dict(self) -> dict[K, V]:
        return {key: value for key, value in self.items()}

    def to_serializable(self) -> dict[str, Any]:
        return {
            "bucket_count": len(self._buckets),
            "size": self._size,
            "items": [{"key": key, "value": value} for key, value in self.items()],
        }

    def clear(self) -> None:
        self._buckets = [None] * len(self._buckets)
        self._size = 0

    def __contains__(self, key: K) -> bool:
        return self.contains(key)

    def __getitem__(self, key: K) -> V:
        value = self.get(key, _MISSING)
        if value is _MISSING:
            raise KeyError(key)
        return value

    def __setitem__(self, key: K, value: V) -> None:
        self.set(key, value)

    def __delitem__(self, key: K) -> None:
        self.delete(key)

    def __len__(self) -> int:
        return self._size

    def __iter__(self) -> Iterator[K]:
        return self.keys()

    def _bucket_index(self, key: K) -> int:
        return self._hash(key) % len(self._buckets)

    def _bucket_for(self, key: K, *, create: bool = False) -> _Bucket[K, V] | None:
        index = self._bucket_index(key)
        bucket = self._buckets[index]
        if bucket is None and create:
            bucket = _Bucket()
            self._buckets[index] = bucket
        return bucket

    def _hash(self, key: K) -> int:
        if isinstance(key, int):
            return key & 0x7FFFFFFF
        if isinstance(key, bytes):
            raw = key
        else:
            raw = repr(key).encode("utf-8")

        value = 0
        for byte in raw:
            value = (value * 131 + byte) & 0x7FFFFFFF
        return value

    def _resize(self) -> None:
        old_items = list(self.items())
        self._buckets = [None] * (len(self._buckets) * 2)
        self._size = 0
        for key, value in old_items:
            bucket = self._bucket_for(key, create=True)
            bucket.append(_Node(key=key, value=value))
            self._size += 1
