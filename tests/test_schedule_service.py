from __future__ import annotations

import importlib
from datetime import date, datetime

import pytest

from app.core import HashTable
from app.models.course import CourseCreate, SCNUFetchRequest, ScheduleInit

schedule_service_module = importlib.import_module("app.services.schedule_service")


class ImmediateThread:
    def __init__(self, target, args=(), daemon=None):
        self._target = target
        self._args = args
        self.daemon = daemon

    def start(self):
        self._target(*self._args)


def test_get_current_today_and_week_courses(schedule_service, make_course, fake_clock):
    fake_clock(
        schedule_service_module,
        today=date(2026, 3, 2),
        now=datetime(2026, 3, 2, 8, 10, 0),
    )
    schedule_service.initialize_schedule(
        "20250001",
        ScheduleInit(semester="2025-2026-2", semester_start="2026-03-02"),
    )
    schedule_service.add_course("20250001", make_course())
    schedule_service.add_course(
        "20250001",
        make_course(name="数据结构", weekday=2, period_start=3, period_end=4, weeks=[1]),
    )

    current_course = schedule_service.get_current_course("20250001")
    assert current_course is not None
    assert current_course.name == "面向对象程序设计"

    today_courses = schedule_service.get_today_courses("20250001")
    assert [course.name for course in today_courses] == ["面向对象程序设计"]

    week_courses = schedule_service.get_week_courses("20250001")
    assert len(week_courses["1"]) == 1
    assert len(week_courses["2"]) == 1


def test_upload_json_object_replaces_schedule(schedule_service):
    payload = (
        '{'
        '"semester": "2025-2026-2", '
        '"semester_start": "2026-03-02", '
        '"courses": ['
        '{"name": "算法设计", "teacher": "王老师", "location": "南B216", '
        '"weekday": 3, "period_start": 5, "period_end": 6, "weeks": [1, 2], "week_type": "all"}'
        "]}"
    ).encode("utf-8")

    schedule = schedule_service.upload_schedule(
        "20250001",
        filename="schedule.json",
        content_type="application/json",
        content=payload,
    )

    assert schedule.semester == "2025-2026-2"
    assert [course.name for course in schedule.courses] == ["算法设计"]


def test_upload_json_list_requires_existing_schedule(schedule_service, log_records):
    payload = (
        '[{"name": "算法设计", "teacher": "王老师", "location": "南B216", '
        '"weekday": 3, "period_start": 5, "period_end": 6, "weeks": [1, 2], "week_type": "all"}]'
    ).encode("utf-8")

    with pytest.raises(ValueError, match="首次导入 JSON 课表前，请先初始化学期信息"):
        schedule_service.upload_schedule(
            "20250001",
            filename="schedule.json",
            content_type="application/json",
            content=payload,
        )

    assert any("before initialization" in record["message"] for record in log_records)


def test_upload_pdf_uses_scraper(schedule_service, dummy_scraper, sample_course):
    schedule_service.initialize_schedule(
        "20250001",
        ScheduleInit(semester="2025-2026-2", semester_start="2026-03-02"),
    )
    dummy_scraper.pdf_result = [sample_course]

    schedule = schedule_service.upload_schedule(
        "20250001",
        filename="schedule.pdf",
        content_type="application/pdf",
        content=b"%PDF-1.7 fake",
    )

    assert len(schedule.courses) == 1
    assert dummy_scraper.pdf_calls == [b"%PDF-1.7 fake"]


def test_upload_invalid_extension_logs(schedule_service, log_records):
    with pytest.raises(ValueError, match="仅支持上传 JSON 或 PDF 课表文件"):
        schedule_service.upload_schedule(
            "20250001",
            filename="schedule.txt",
            content_type="text/plain",
            content=b"hello",
        )

    assert any("Rejected unsupported schedule upload" in record["message"] for record in log_records)


def test_submit_scnu_fetch_task_success(
    schedule_service,
    dummy_scraper,
    sample_course,
    monkeypatch,
):
    assert isinstance(schedule_service._tasks, HashTable)

    monkeypatch.setattr(schedule_service_module, "Thread", ImmediateThread)
    schedule_service.initialize_schedule(
        "20250001",
        ScheduleInit(semester="2025-2026-2", semester_start="2026-03-02"),
    )
    dummy_scraper.fetch_result = [sample_course]

    task = schedule_service.submit_scnu_fetch(
        "20250001",
        SCNUFetchRequest(
            scnu_account="20250001",
            scnu_password="password123",
            semester_id="2025-2026-2",
            prefer_playwright=True,
        ),
    )
    final_task = schedule_service.get_fetch_task(task.task_id)

    assert final_task.status == "succeeded"
    assert final_task.schedule_updated is True
    assert dummy_scraper.fetch_calls[0]["prefer_playwright"] is True


def test_submit_scnu_fetch_task_failure_logs(
    schedule_service,
    dummy_scraper,
    monkeypatch,
    log_records,
):
    monkeypatch.setattr(schedule_service_module, "Thread", ImmediateThread)
    schedule_service.initialize_schedule(
        "20250001",
        ScheduleInit(semester="2025-2026-2", semester_start="2026-03-02"),
    )
    dummy_scraper.fetch_exception = RuntimeError("教务系统连接失败")

    task = schedule_service.submit_scnu_fetch(
        "20250001",
        SCNUFetchRequest(scnu_password="password123", semester_id="2025-2026-2"),
    )
    final_task = schedule_service.get_fetch_task(task.task_id)

    assert final_task.status == "failed"
    assert final_task.message == "教务系统连接失败"
    assert any("SCNU fetch task" in record["message"] and record["level"].name == "ERROR" for record in log_records)


def test_invalid_course_and_date_validation_logs(schedule_service, log_records):
    with pytest.raises(ValueError, match="结束节次不能早于开始节次"):
        schedule_service.add_course(
            "20250001",
            CourseCreate(
                name="算法设计",
                teacher="王老师",
                location="南B216",
                weekday=1,
                period_start=4,
                period_end=2,
                weeks=[1],
                week_type="all",
            ),
        )

    with pytest.raises(ValueError, match="日期必须使用 YYYY-MM-DD 格式"):
        schedule_service.initialize_schedule(
            "20250001",
            ScheduleInit(semester="2025-2026-2", semester_start="2026/03/02"),
        )

    assert any("invalid period range" in record["message"] for record in log_records)
    assert any("invalid ISO date" in record["message"] for record in log_records)


def test_get_fetch_task_missing_logs(schedule_service, log_records):
    with pytest.raises(ValueError, match="未找到抓取任务"):
        schedule_service.get_fetch_task("missing-task")

    assert any("Requested missing fetch task" in record["message"] for record in log_records)
