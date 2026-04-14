"""
双向链表单元测试
运行命令: python -m pytest tests/test_doubly_linked_list.py -v
"""

import pytest
from app.core.doubly_linked_list import DoublyLinkedList


class TestDoublyLinkedList:
    
    def test_append(self):
        """测试尾部添加"""
        dll = DoublyLinkedList()
        dll.append("课程A")
        dll.append("课程B")
        dll.append("课程C")
        assert len(dll) == 3
        assert dll.to_list() == ["课程A", "课程B", "课程C"]
    
    def test_prepend(self):
        """测试头部添加"""
        dll = DoublyLinkedList()
        dll.prepend("课程B")
        dll.prepend("课程A")
        assert len(dll) == 2
        assert dll.to_list() == ["课程A", "课程B"]
    
    def test_insert_after(self):
        """测试中间插入"""
        dll = DoublyLinkedList()
        dll.append("课程A")
        dll.append("课程C")
        dll.insert_after("课程A", "课程B")
        assert dll.to_list() == ["课程A", "课程B", "课程C"]
    
    def test_insert_after_not_found(self):
        """测试插入到不存在的节点后"""
        dll = DoublyLinkedList()
        dll.append("课程A")
        result = dll.insert_after("不存在", "课程B")
        assert result is False
        assert dll.to_list() == ["课程A"]
    
    def test_remove(self):
        """测试删除节点"""
        dll = DoublyLinkedList()
        dll.append("课程A")
        dll.append("课程B")
        dll.append("课程C")
        
        # 删除中间节点
        assert dll.remove("课程B") is True
        assert dll.to_list() == ["课程A", "课程C"]
        
        # 删除头节点
        assert dll.remove("课程A") is True
        assert dll.to_list() == ["课程C"]
        
        # 删除尾节点
        assert dll.remove("课程C") is True
        assert dll.is_empty()
    
    def test_remove_not_found(self):
        """测试删除不存在的节点"""
        dll = DoublyLinkedList()
        dll.append("课程A")
        result = dll.remove("不存在")
        assert result is False
        assert len(dll) == 1
    
    def test_find(self):
        """测试查找节点"""
        dll = DoublyLinkedList()
        dll.append("课程A")
        dll.append("课程B")
        
        node = dll.find("课程B")
        assert node is not None
        assert node.data == "课程B"
        
        node = dll.find("不存在")
        assert node is None
    
    def test_from_list(self):
        """测试从列表重建"""
        dll = DoublyLinkedList()
        dll.from_list(["课程1", "课程2", "课程3"])
        assert len(dll) == 3
        assert dll.to_list() == ["课程1", "课程2", "课程3"]
    
    def test_iteration(self):
        """测试迭代器"""
        dll = DoublyLinkedList()
        dll.append("课程A")
        dll.append("课程B")
        
        result = []
        for data in dll:
            result.append(data)
        assert result == ["课程A", "课程B"]
    
    def test_empty_list(self):
        """测试空链表"""
        dll = DoublyLinkedList()
        assert dll.is_empty()
        assert len(dll) == 0
        assert dll.to_list() == []
        assert dll.head is None
        assert dll.tail is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])