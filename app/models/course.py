from typing import Literal

from pydantic import BaseModel, Field


class Course(BaseModel):
    id: str
    name: str
    teacher: str
    location: str
    weekday: int
    period_start: int
    period_end: int
    weeks: list[int]
    week_type: Literal["all", "odd", "even"] = "all"


class CourseCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    teacher: str = Field(default="", max_length=64)
    location: str = Field(default="", max_length=128)
    weekday: int = Field(..., ge=1, le=7)
    period_start: int = Field(..., ge=1, le=12)
    period_end: int = Field(..., ge=1, le=12)
    weeks: list[int] = Field(default_factory=list)
    week_type: Literal["all", "odd", "even"] = "all"


class Schedule(BaseModel):
    student_id: str
    semester: str
    semester_start: str
    courses: list[Course]


class ScheduleInit(BaseModel):
    semester: str = Field(..., min_length=1, max_length=32)
    semester_start: str = Field(..., min_length=10, max_length=10)


class SCNUFetchRequest(BaseModel):
    scnu_password: str = Field(..., min_length=1, max_length=128)
    scnu_account: str | None = Field(default=None, max_length=64)
    semester_id: str | None = Field(default=None, max_length=32)
    prefer_playwright: bool = False


class FetchTaskStatus(BaseModel):
    task_id: str
    status: Literal["queued", "running", "succeeded", "failed"]
    message: str
    created_at: str
    updated_at: str
    schedule_updated: bool = False
