"""
BST 单元测试
运行命令: python -m pytest tests/test_bst.py -v
"""

import pytest
from app.core.bst import BinarySearchTree


class TestBinarySearchTree:

    def test_insert_and_search(self):
        """测试插入和查找"""
        bst = BinarySearchTree[int, str]()
        bst.insert(101, "课程A")
        bst.insert(201, "课程B")
        bst.insert(50, "课程C")

        assert bst.search(101) == "课程A"
        assert bst.search(201) == "课程B"
        assert bst.search(50) == "课程C"
        assert bst.search(999) is None

    def test_insert_duplicate_updates_value(self):
        """测试重复插入会更新值"""
        bst = BinarySearchTree[int, str]()
        bst.insert(101, "旧值")
        bst.insert(101, "新值")

        assert bst.search(101) == "新值"

    def test_delete_leaf_node(self):
        """测试删除叶子节点"""
        bst = BinarySearchTree[int, str]()
        bst.insert(50, "A")
        bst.insert(30, "B")
        bst.insert(70, "C")

        bst.delete(30)
        assert bst.search(30) is None
        assert bst.search(50) == "A"
        assert bst.search(70) == "C"

    def test_delete_node_with_one_child(self):
        """测试删除只有一个子节点的节点"""
        bst = BinarySearchTree[int, str]()
        bst.insert(50, "A")
        bst.insert(30, "B")
        bst.insert(20, "C")

        bst.delete(30)
        assert bst.search(30) is None
        assert bst.search(20) == "C"
        assert bst.search(50) == "A"

    def test_delete_node_with_two_children(self):
        """测试删除有两个子节点的节点"""
        bst = BinarySearchTree[int, str]()
        bst.insert(50, "A")
        bst.insert(30, "B")
        bst.insert(70, "C")
        bst.insert(20, "D")
        bst.insert(40, "E")

        bst.delete(30)
        assert bst.search(30) is None
        assert bst.search(40) == "E"
        assert bst.search(20) == "D"

    def test_delete_nonexistent_key(self):
        """测试删除不存在的键"""
        bst = BinarySearchTree[int, str]()
        bst.insert(50, "A")

        # 删除不存在的键不应该报错
        bst.delete(999)
        assert bst.search(50) == "A"

    def test_empty_tree(self):
        """测试空树"""
        bst = BinarySearchTree[int, str]()
        assert bst.search(1) is None

    def test_course_time_key_scenario(self):
        """测试课程时间索引场景：key = weekday * 100 + period_start"""
        bst = BinarySearchTree[int, str]()

        # 周一第1节 (101)
        bst.insert(101, "面向对象程序设计")
        # 周三第3节 (303)
        bst.insert(303, "数据结构")
        # 周五第5节 (505)
        bst.insert(505, "算法分析")

        assert bst.search(101) == "面向对象程序设计"
        assert bst.search(303) == "数据结构"
        assert bst.search(505) == "算法分析"
        assert bst.search(202) is None  # 周二第2节没课


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
