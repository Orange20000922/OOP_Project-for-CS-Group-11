from __future__ import annotations

from threading import Lock
from uuid import uuid4

from app.config import SCHEDULES_DIR
from app.models.course import Course, CourseCreate, Schedule
from app.storage.file_io import model_to_dict, read_json, write_json_atomic


def _sort_courses(courses: list[Course]) -> list[Course]:
    return sorted(
        courses,
        key=lambda item: (
            item.weekday,
            item.period_start,
            item.period_end,
            item.name,
            item.id,
        ),
    )


class ScheduleStore:
    def __init__(self) -> None:
        self._lock = Lock()
        SCHEDULES_DIR.mkdir(parents=True, exist_ok=True)

    def _path_for(self, student_id: str):
        return SCHEDULES_DIR / f"{student_id}.json"

    def get(self, student_id: str) -> Schedule | None:
        path = self._path_for(student_id)
        if not path.exists():
            return None
        return Schedule(**read_json(path, {}))

    def save(self, schedule: Schedule) -> Schedule:
        normalized = Schedule(
            student_id=schedule.student_id,
            semester=schedule.semester,
            semester_start=schedule.semester_start,
            courses=_sort_courses(schedule.courses),
        )
        write_json_atomic(self._path_for(schedule.student_id), model_to_dict(normalized))
        return normalized

    def initialize(self, student_id: str, semester: str, semester_start: str) -> Schedule:
        with self._lock:
            schedule = self.get(student_id)
            if schedule is None:
                schedule = Schedule(
                    student_id=student_id,
                    semester=semester,
                    semester_start=semester_start,
                    courses=[],
                )
            else:
                schedule.semester = semester
                schedule.semester_start = semester_start
            return self.save(schedule)

    def replace(self, student_id: str, semester: str, semester_start: str, courses: list[Course]) -> Schedule:
        with self._lock:
            return self.save(
                Schedule(
                    student_id=student_id,
                    semester=semester,
                    semester_start=semester_start,
                    courses=_sort_courses(courses),
                )
            )

    def add_course(self, student_id: str, course: CourseCreate) -> Course:
        with self._lock:
            schedule = self.get(student_id)
            if schedule is None:
                raise ValueError("请先初始化课表")
            created = Course(id=uuid4().hex, **model_to_dict(course))
            schedule.courses.append(created)
            self.save(schedule)
            return created

    def update_course(self, student_id: str, course_id: str, course: CourseCreate) -> Course:
        with self._lock:
            schedule = self.get(student_id)
            if schedule is None:
                raise ValueError("请先初始化课表")

            updated_course: Course | None = None
            updated_courses: list[Course] = []
            for item in schedule.courses:
                if item.id == course_id:
                    updated_course = Course(id=course_id, **model_to_dict(course))
                    updated_courses.append(updated_course)
                else:
                    updated_courses.append(item)

            if updated_course is None:
                raise ValueError("未找到对应课程")

            schedule.courses = updated_courses
            self.save(schedule)
            return updated_course

    def delete_course(self, student_id: str, course_id: str) -> None:
        with self._lock:
            schedule = self.get(student_id)
            if schedule is None:
                raise ValueError("请先初始化课表")
            new_courses = [item for item in schedule.courses if item.id != course_id]
            if len(new_courses) == len(schedule.courses):
                raise ValueError("未找到对应课程")
            schedule.courses = new_courses
            self.save(schedule)
