"""
栈单元测试
运行命令: python -m pytest tests/test_stack.py -v
"""

import pytest
from app.core.stack import Stack


class TestStack:

    def test_push_and_pop(self):
        """测试压栈和弹栈"""
        stack = Stack()
        stack.push("A")
        stack.push("B")
        stack.push("C")

        assert stack.size() == 3
        assert stack.pop() == "C"
        assert stack.pop() == "B"
        assert stack.pop() == "A"
        assert stack.is_empty()

    def test_peek(self):
        """测试查看栈顶元素"""
        stack = Stack()
        stack.push("first")
        stack.push("second")

        assert stack.peek() == "second"
        assert stack.size() == 2  # peek 不移除元素

    def test_peek_empty_stack(self):
        """测试空栈的 peek"""
        stack = Stack()
        assert stack.peek() is None

    def test_pop_empty_stack(self):
        """测试空栈弹出抛出异常"""
        stack = Stack()
        with pytest.raises(IndexError, match="Stack is empty"):
            stack.pop()

    def test_is_empty(self):
        """测试空栈检查"""
        stack = Stack()
        assert stack.is_empty()

        stack.push("item")
        assert not stack.is_empty()

        stack.pop()
        assert stack.is_empty()

    def test_size(self):
        """测试栈大小"""
        stack = Stack()
        assert stack.size() == 0

        for i in range(5):
            stack.push(i)
        assert stack.size() == 5

        stack.pop()
        assert stack.size() == 4

    def test_clear(self):
        """测试清空栈"""
        stack = Stack()
        stack.push(1)
        stack.push(2)
        stack.push(3)

        stack.clear()
        assert stack.is_empty()
        assert stack.size() == 0

    def test_lifo_order(self):
        """测试后进先出顺序"""
        stack = Stack()
        items = [1, 2, 3, 4, 5]

        for item in items:
            stack.push(item)

        result = []
        while not stack.is_empty():
            result.append(stack.pop())

        assert result == [5, 4, 3, 2, 1]  # 逆序

    def test_iteration_not_supported(self):
        """测试栈不支持迭代"""
        stack = Stack()
        stack.push(1)
        stack.push(2)

        with pytest.raises(TypeError, match="does not support iteration"):
            for item in stack:
                pass

    def test_len(self):
        """测试 __len__ 方法"""
        stack = Stack()
        assert len(stack) == 0

        stack.push("a")
        stack.push("b")
        assert len(stack) == 2

    def test_repr(self):
        """测试字符串表示"""
        stack = Stack()
        stack.push("item1")
        stack.push("item2")

        repr_str = repr(stack)
        assert "Stack" in repr_str
        assert "size=2" in repr_str
        assert "item2" in repr_str


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
