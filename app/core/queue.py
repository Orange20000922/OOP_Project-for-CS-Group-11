class Node:
    def __init__(self, value):
        self.value = value
        self.next = None


class Queue:
    def __init__(self):
        self.head = None
        self.tail = None
        self._size = 0

    def enqueue(self, item):
        new_node = Node(item)

        if self.tail is None:
            self.head = self.tail = new_node
        else:
            self.tail.next = new_node
            self.tail = new_node

        self._size += 1

    def dequeue(self):
        if self.is_empty():
            raise IndexError("Queue is empty")

        value = self.head.value
        self.head = self.head.next

        if self.head is None:
            self.tail = None

        self._size -= 1
        return value

    def peek(self):
        if self.is_empty():
            return None
        return self.head.value

    def is_empty(self):
        return self._size == 0

    def size(self):
        return self._size

    def __repr__(self):
        items = []
        current = self.head
        while current:
            items.append(str(current.value))
            current = current.next
        return "Queue: [" + " -> ".join(items) + "]"
