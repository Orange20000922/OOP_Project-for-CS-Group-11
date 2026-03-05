from typing import Literal
from pydantic import BaseModel


class Course(BaseModel):
    id: str
    name: str
    teacher: str
    location: str
    weekday: int          # 1=周一, 7=周日
    period_start: int     # 第几节开始（1-12）
    period_end: int
    weeks: list[int]      # 上课的周次列表，如 [1, 2, ..., 16]
    week_type: Literal["all", "odd", "even"] = "all"


class CourseCreate(BaseModel):
    name: str
    teacher: str
    location: str
    weekday: int
    period_start: int
    period_end: int
    weeks: list[int]
    week_type: Literal["all", "odd", "even"] = "all"


class Schedule(BaseModel):
    student_id: str
    semester: str          # 如 "2025-2026-2"
    semester_start: str    # 学期第一周周一，ISO 格式 "YYYY-MM-DD"
    courses: list[Course]


class ScheduleInit(BaseModel):
    semester: str
    semester_start: str    # ISO 格式 "YYYY-MM-DD"


class SCNUFetchRequest(BaseModel):
    scnu_password: str
    semester_id: str | None = None  # 不填则自动获取当前学期
