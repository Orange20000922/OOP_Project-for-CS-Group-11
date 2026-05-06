"""
课表索引层 - 使用课程要求的数据结构
- DoublyLinkedList: 按时间顺序存储课程（支持前后导航）
- BinarySearchTree: 时间索引，key = weekday*100 + period_start（O(log n) 查找当前课）
"""

from __future__ import annotations

from app.core import BinarySearchTree, DoublyLinkedList
from app.models.course import Course


class ScheduleIndex:
    """单个学生的课表索引"""

    def __init__(self):
        # 双向链表：按 (weekday, period_start) 排序存储所有课程
        self.courses_list = DoublyLinkedList()

        # BST 时间索引：key = weekday*100 + period_start, value = Course
        # 用于快速查找"某个时间点有哪门课"
        self.time_index = BinarySearchTree[int, Course]()

    def rebuild_from_courses(self, courses: list[Course]) -> None:
        """从课程列表重建索引"""
        # 清空现有索引
        self.courses_list.clear()
        self.time_index = BinarySearchTree[int, Course]()

        # 按时间排序
        sorted_courses = sorted(
            courses,
            key=lambda c: (c.weekday, c.period_start, c.period_end, c.name, c.id),
        )

        # 填充双向链表
        for course in sorted_courses:
            self.courses_list.append(course)

        # 填充 BST 时间索引
        for course in courses:
            time_key = course.weekday * 100 + course.period_start
            # 如果同一时间有多门课（冲突），BST 会覆盖为最后一门
            # 实际场景中应该避免时间冲突，这里简化处理
            self.time_index.insert(time_key, course)

    def find_course_at_time(self, weekday: int, period: int) -> Course | None:
        """
        使用 BST 查找指定时间的课程
        时间复杂度: O(log n)
        """
        time_key = weekday * 100 + period
        return self.time_index.search(time_key)

    def get_courses_for_day(self, weekday: int, week_number: int) -> list[Course]:
        """
        使用双向链表遍历指定星期的所有课程
        时间复杂度: O(n)，但实际只遍历当天课程
        """
        result = []
        for course in self.courses_list:
            if course.weekday == weekday:
                # 检查该课程是否在指定周次上课
                if self._course_matches_week(course, week_number):
                    result.append(course)
        return result

    def get_all_courses(self) -> list[Course]:
        """获取所有课程（按时间排序）"""
        return self.courses_list.to_list()

    def add_course(self, course: Course) -> None:
        """添加单门课程到索引"""
        # 找到插入位置（保持排序）
        inserted = False
        current = self.courses_list.head

        while current:
            existing = current.data
            if (course.weekday, course.period_start) < (existing.weekday, existing.period_start):
                # 应该插入到 current 之前
                # 由于 DoublyLinkedList 没有 insert_before，我们用 insert_after 前一个节点
                if current.prev:
                    self.courses_list.insert_after(current.prev.data, course)
                else:
                    self.courses_list.prepend(course)
                inserted = True
                break
            current = current.next

        if not inserted:
            self.courses_list.append(course)

        # 更新 BST 索引
        time_key = course.weekday * 100 + course.period_start
        self.time_index.insert(time_key, course)

    def remove_course(self, course_id: str) -> bool:
        """从索引中删除课程"""
        # 从双向链表中查找并删除
        target_course = None
        for course in self.courses_list:
            if course.id == course_id:
                target_course = course
                break

        if target_course is None:
            return False

        self.courses_list.remove(target_course)

        # 从 BST 中删除
        time_key = target_course.weekday * 100 + target_course.period_start
        self.time_index.delete(time_key)

        return True

    def update_course(self, course_id: str, updated_course: Course) -> bool:
        """更新课程（先删除再添加）"""
        if self.remove_course(course_id):
            self.add_course(updated_course)
            return True
        return False

    @staticmethod
    def _course_matches_week(course: Course, week_number: int) -> bool:
        """检查课程是否在指定周次上课"""
        if week_number <= 0:
            return False
        if course.weeks and week_number not in course.weeks:
            return False
        if course.week_type == "odd" and week_number % 2 == 0:
            return False
        if course.week_type == "even" and week_number % 2 != 0:
            return False
        return True
