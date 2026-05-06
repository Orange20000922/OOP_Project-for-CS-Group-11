"""
集成测试：验证数据结构在 storage 和 service 层的集成
"""

import pytest
from datetime import date

from app.models.course import Course, Schedule
from app.storage.schedule_index import ScheduleIndex


class TestScheduleIndex:

    def test_rebuild_and_find_course_at_time(self):
        """测试 BST 时间索引查找"""
        courses = [
            Course(
                id="1",
                name="面向对象程序设计",
                teacher="李老师",
                location="理工楼A101",
                weekday=1,
                period_start=1,
                period_end=2,
                weeks=list(range(1, 17)),
                week_type="all",
            ),
            Course(
                id="2",
                name="数据结构",
                teacher="王老师",
                location="理工楼B202",
                weekday=3,
                period_start=3,
                period_end=4,
                weeks=list(range(1, 17)),
                week_type="all",
            ),
        ]

        index = ScheduleIndex()
        index.rebuild_from_courses(courses)

        # BST 查找：周一第1节
        course = index.find_course_at_time(1, 1)
        assert course is not None
        assert course.name == "面向对象程序设计"

        # BST 查找：周三第3节
        course = index.find_course_at_time(3, 3)
        assert course is not None
        assert course.name == "数据结构"

        # BST 查找：不存在的时间
        course = index.find_course_at_time(2, 2)
        assert course is None

    def test_get_courses_for_day(self):
        """测试双向链表遍历当天课程"""
        courses = [
            Course(
                id="1",
                name="课程A",
                teacher="老师A",
                location="A101",
                weekday=1,
                period_start=1,
                period_end=2,
                weeks=list(range(1, 17)),
                week_type="all",
            ),
            Course(
                id="2",
                name="课程B",
                teacher="老师B",
                location="B202",
                weekday=1,
                period_start=3,
                period_end=4,
                weeks=list(range(1, 17)),
                week_type="all",
            ),
            Course(
                id="3",
                name="课程C",
                teacher="老师C",
                location="C303",
                weekday=2,
                period_start=1,
                period_end=2,
                weeks=list(range(1, 17)),
                week_type="all",
            ),
        ]

        index = ScheduleIndex()
        index.rebuild_from_courses(courses)

        # 查询周一的课程
        monday_courses = index.get_courses_for_day(1, 1)
        assert len(monday_courses) == 2
        assert monday_courses[0].name == "课程A"
        assert monday_courses[1].name == "课程B"

        # 查询周二的课程
        tuesday_courses = index.get_courses_for_day(2, 1)
        assert len(tuesday_courses) == 1
        assert tuesday_courses[0].name == "课程C"

        # 查询周三的课程（没有）
        wednesday_courses = index.get_courses_for_day(3, 1)
        assert len(wednesday_courses) == 0

    def test_week_type_filtering(self):
        """测试单双周过滤"""
        courses = [
            Course(
                id="1",
                name="单周课程",
                teacher="老师A",
                location="A101",
                weekday=1,
                period_start=1,
                period_end=2,
                weeks=list(range(1, 17)),
                week_type="odd",
            ),
            Course(
                id="2",
                name="双周课程",
                teacher="老师B",
                location="B202",
                weekday=1,
                period_start=3,
                period_end=4,
                weeks=list(range(1, 17)),
                week_type="even",
            ),
        ]

        index = ScheduleIndex()
        index.rebuild_from_courses(courses)

        # 第1周（单周）
        week1_courses = index.get_courses_for_day(1, 1)
        assert len(week1_courses) == 1
        assert week1_courses[0].name == "单周课程"

        # 第2周（双周）
        week2_courses = index.get_courses_for_day(1, 2)
        assert len(week2_courses) == 1
        assert week2_courses[0].name == "双周课程"

    def test_add_and_remove_course(self):
        """测试动态添加和删除课程"""
        index = ScheduleIndex()

        course1 = Course(
            id="1",
            name="课程A",
            teacher="老师A",
            location="A101",
            weekday=1,
            period_start=1,
            period_end=2,
            weeks=list(range(1, 17)),
            week_type="all",
        )

        index.add_course(course1)
        assert len(index.get_all_courses()) == 1

        found = index.find_course_at_time(1, 1)
        assert found is not None
        assert found.name == "课程A"

        # 删除课程
        result = index.remove_course("1")
        assert result is True
        assert len(index.get_all_courses()) == 0

        found = index.find_course_at_time(1, 1)
        assert found is None

    def test_sorted_order_maintained(self):
        """测试双向链表保持时间排序"""
        courses = [
            Course(
                id="3",
                name="周三课程",
                teacher="老师C",
                location="C303",
                weekday=3,
                period_start=1,
                period_end=2,
                weeks=list(range(1, 17)),
                week_type="all",
            ),
            Course(
                id="1",
                name="周一课程",
                teacher="老师A",
                location="A101",
                weekday=1,
                period_start=1,
                period_end=2,
                weeks=list(range(1, 17)),
                week_type="all",
            ),
            Course(
                id="2",
                name="周二课程",
                teacher="老师B",
                location="B202",
                weekday=2,
                period_start=1,
                period_end=2,
                weeks=list(range(1, 17)),
                week_type="all",
            ),
        ]

        index = ScheduleIndex()
        index.rebuild_from_courses(courses)

        all_courses = index.get_all_courses()
        assert len(all_courses) == 3
        assert all_courses[0].name == "周一课程"
        assert all_courses[1].name == "周二课程"
        assert all_courses[2].name == "周三课程"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
