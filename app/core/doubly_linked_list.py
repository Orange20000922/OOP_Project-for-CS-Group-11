"""
双向链表 - 用于课表存储
每个节点存储一门课程的数据
"""

from typing import Any, Optional, List


class Node:
    """双向链表节点"""
    
    def __init__(self, data: Any):
        self.data = data      # 存储课程数据（Course对象或字典）
        self.prev: Optional['Node'] = None
        self.next: Optional['Node'] = None


class DoublyLinkedList:
    """双向链表 - 按时间顺序存储每日课程"""
    
    def __init__(self):
        self.head: Optional[Node] = None   # 头节点（第一节课）
        self.tail: Optional[Node] = None   # 尾节点（最后一节课）
        self._size: int = 0                # 链表长度
    
    # ========== 添加操作 ==========
    
    def append(self, data: Any) -> None:
        """尾部添加节点"""
        new_node = Node(data)
        if self.head is None:
            self.head = new_node
            self.tail = new_node
        else:
            self.tail.next = new_node
            new_node.prev = self.tail
            self.tail = new_node
        self._size += 1
    
    def prepend(self, data: Any) -> None:
        """头部添加节点"""
        new_node = Node(data)
        if self.head is None:
            self.head = new_node
            self.tail = new_node
        else:
            new_node.next = self.head
            self.head.prev = new_node
            self.head = new_node
        self._size += 1
    
    def insert_after(self, target_data: Any, new_data: Any) -> bool:
        """
        在指定数据后插入新节点
        返回: 是否插入成功
        """
        current = self.head
        while current:
            if current.data == target_data:
                new_node = Node(new_data)
                new_node.next = current.next
                new_node.prev = current
                if current.next:
                    current.next.prev = new_node
                else:
                    self.tail = new_node
                current.next = new_node
                self._size += 1
                return True
            current = current.next
        return False
    
    # ========== 删除操作 ==========
    
    def remove(self, data: Any) -> bool:
        """删除第一个匹配的节点，返回是否删除成功"""
        current = self.head
        while current:
            if current.data == data:
                # 更新前后节点的指针
                if current.prev:
                    current.prev.next = current.next
                else:
                    self.head = current.next  # 删除的是头节点
                
                if current.next:
                    current.next.prev = current.prev
                else:
                    self.tail = current.prev  # 删除的是尾节点
                
                self._size -= 1
                return True
            current = current.next
        return False
    
    # ========== 查找操作 ==========
    
    def find(self, data: Any) -> Optional[Node]:
        """查找第一个匹配的节点，返回节点或None"""
        current = self.head
        while current:
            if current.data == data:
                return current
            current = current.next
        return None
    
    def find_by(self, predicate) -> Optional[Node]:
        """
        按条件查找节点
        用法: dll.find_by(lambda node: node.data['id'] == '123')
        """
        current = self.head
        while current:
            if predicate(current.data):
                return current
            current = current.next
        return None
    
    # ========== 遍历操作 ==========
    
    def to_list(self) -> List[Any]:
        """转换为Python列表（用于JSON序列化）"""
        result = []
        current = self.head
        while current:
            result.append(current.data)
            current = current.next
        return result
    
    def from_list(self, data_list: List[Any]) -> None:
        """从列表重建链表（清空现有数据）"""
        self.clear()
        for data in data_list:
            self.append(data)
    
    def __iter__(self):
        """支持 for node in dll 遍历"""
        current = self.head
        while current:
            yield current.data
            current = current.next
    
    # ========== 辅助方法 ==========
    
    def clear(self) -> None:
        """清空链表"""
        self.head = None
        self.tail = None
        self._size = 0
    
    def __len__(self) -> int:
        return self._size
    
    def is_empty(self) -> bool:
        return self._size == 0
    
    def __str__(self) -> str:
        return f"DoublyLinkedList(size={self._size}, data={self.to_list()})"