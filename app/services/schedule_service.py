from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from pathlib import Path
from threading import Lock, Thread
from uuid import uuid4

from app.config import PERIOD_TIMES
from app.models.course import Course, CourseCreate, FetchTaskStatus, SCNUFetchRequest, Schedule, ScheduleInit
from app.storage.file_io import model_to_dict
from app.storage.schedule_store import ScheduleStore
from app.services.scnu_scraper import SCNUScraper


class ScheduleService:
    def __init__(self, schedule_store: ScheduleStore, scnu_scraper: SCNUScraper) -> None:
        self._schedule_store = schedule_store
        self._scnu_scraper = scnu_scraper
        self._tasks: dict[str, FetchTaskStatus] = {}
        self._task_lock = Lock()

    def get_schedule(self, student_id: str) -> Schedule:
        schedule = self._schedule_store.get(student_id)
        if schedule is None:
            raise ValueError("请先初始化课表")
        return schedule

    def initialize_schedule(self, student_id: str, payload: ScheduleInit) -> Schedule:
        self._parse_iso_date(payload.semester_start)
        return self._schedule_store.initialize(
            student_id,
            payload.semester.strip(),
            payload.semester_start,
        )

    def upload_schedule(
        self,
        student_id: str,
        filename: str,
        content_type: str | None,
        content: bytes,
    ) -> Schedule:
        suffix = Path(filename or "").suffix.lower()
        if suffix == ".json" or content_type == "application/json":
            return self._import_json_schedule(student_id, content)
        if suffix == ".pdf" or content_type == "application/pdf":
            schedule = self.get_schedule(student_id)
            courses = self._scnu_scraper.parse_pdf_schedule(content)
            return self._schedule_store.replace(
                student_id,
                schedule.semester,
                schedule.semester_start,
                courses,
            )
        raise ValueError("仅支持上传 JSON 或 PDF 课表文件")

    def add_course(self, student_id: str, payload: CourseCreate) -> Course:
        self._validate_course_payload(payload)
        return self._schedule_store.add_course(student_id, payload)

    def update_course(self, student_id: str, course_id: str, payload: CourseCreate) -> Course:
        self._validate_course_payload(payload)
        return self._schedule_store.update_course(student_id, course_id, payload)

    def delete_course(self, student_id: str, course_id: str) -> None:
        self._schedule_store.delete_course(student_id, course_id)

    def get_current_course(self, student_id: str) -> Course | None:
        schedule = self.get_schedule(student_id)
        today = date.today()
        week_number = self._calculate_week_number(schedule.semester_start, today)
        weekday = today.isoweekday()
        current_period = self._find_period(datetime.now().time())
        if current_period is None:
            return None
        for course in self._iter_courses_for_day(schedule, week_number, weekday):
            if course.period_start <= current_period <= course.period_end:
                return course
        return None

    def get_today_courses(self, student_id: str) -> list[Course]:
        schedule = self.get_schedule(student_id)
        today = date.today()
        week_number = self._calculate_week_number(schedule.semester_start, today)
        return list(self._iter_courses_for_day(schedule, week_number, today.isoweekday()))

    def get_week_courses(self, student_id: str, week_offset: int = 0) -> dict[str, list[Course]]:
        schedule = self.get_schedule(student_id)
        target_day = date.today() + timedelta(days=week_offset * 7)
        week_number = self._calculate_week_number(schedule.semester_start, target_day)
        result: dict[str, list[Course]] = {str(day): [] for day in range(1, 8)}
        for course in schedule.courses:
            if self._course_matches_week(course, week_number):
                result[str(course.weekday)].append(course)
        return result

    def submit_scnu_fetch(self, student_id: str, payload: SCNUFetchRequest) -> FetchTaskStatus:
        now = self._now_iso()
        task = FetchTaskStatus(
            task_id=uuid4().hex,
            status="queued",
            message="抓取任务已入队",
            created_at=now,
            updated_at=now,
            schedule_updated=False,
        )
        with self._task_lock:
            self._tasks[task.task_id] = task

        Thread(
            target=self._run_fetch_task,
            args=(task.task_id, student_id, payload),
            daemon=True,
        ).start()
        return task

    def get_fetch_task(self, task_id: str) -> FetchTaskStatus:
        with self._task_lock:
            task = self._tasks.get(task_id)
        if task is None:
            raise ValueError("未找到抓取任务")
        return task

    def _run_fetch_task(self, task_id: str, student_id: str, payload: SCNUFetchRequest) -> None:
        self._update_task(task_id, status="running", message="正在连接教务系统")
        try:
            schedule = self.get_schedule(student_id)
            semester_id = payload.semester_id or schedule.semester
            account = payload.scnu_account or student_id
            courses = self._scnu_scraper.fetch_schedule(
                account=account,
                password=payload.scnu_password,
                semester_id=semester_id,
                prefer_playwright=payload.prefer_playwright,
            )
            self._schedule_store.replace(
                student_id,
                schedule.semester,
                schedule.semester_start,
                courses,
            )
            self._update_task(
                task_id,
                status="succeeded",
                message=f"抓取完成，共导入 {len(courses)} 门课程",
                schedule_updated=True,
            )
        except Exception as exc:
            self._update_task(
                task_id,
                status="failed",
                message=str(exc),
                schedule_updated=False,
            )

    def _update_task(self, task_id: str, **changes) -> None:
        with self._task_lock:
            current = self._tasks.get(task_id)
            if current is None:
                return
            data = model_to_dict(current)
            data.update(changes)
            data["updated_at"] = self._now_iso()
            self._tasks[task_id] = FetchTaskStatus(**data)

    def _import_json_schedule(self, student_id: str, content: bytes) -> Schedule:
        try:
            payload = json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("上传的 JSON 文件格式无效") from exc

        existing = self._schedule_store.get(student_id)
        if isinstance(payload, list):
            if existing is None:
                raise ValueError("首次导入 JSON 课表前，请先初始化学期信息")
            courses = [self._course_from_payload(item) for item in payload]
            return self._schedule_store.replace(
                student_id,
                existing.semester,
                existing.semester_start,
                courses,
            )

        if not isinstance(payload, dict):
            raise ValueError("JSON 课表必须是对象或课程数组")

        semester = str(payload.get("semester") or (existing.semester if existing else "")).strip()
        semester_start = str(payload.get("semester_start") or (existing.semester_start if existing else "")).strip()
        if not semester or not semester_start:
            raise ValueError("JSON 中缺少 semester 或 semester_start")

        self._parse_iso_date(semester_start)
        raw_courses = payload.get("courses", [])
        if not isinstance(raw_courses, list):
            raise ValueError("JSON 中的 courses 必须是数组")

        return self._schedule_store.replace(
            student_id,
            semester,
            semester_start,
            [self._course_from_payload(item) for item in raw_courses],
        )

    def _course_from_payload(self, payload: dict) -> Course:
        if not isinstance(payload, dict):
            raise ValueError("课程数据格式无效")
        if payload.get("id"):
            course = Course(**payload)
            self._validate_course(course)
            return course
        created = CourseCreate(**payload)
        self._validate_course_payload(created)
        return Course(id=uuid4().hex, **model_to_dict(created))

    def _iter_courses_for_day(self, schedule: Schedule, week_number: int, weekday: int):
        for course in schedule.courses:
            if course.weekday != weekday:
                continue
            if not self._course_matches_week(course, week_number):
                continue
            yield course

    def _course_matches_week(self, course: Course, week_number: int) -> bool:
        if week_number <= 0:
            return False
        if course.weeks and week_number not in course.weeks:
            return False
        if course.week_type == "odd" and week_number % 2 == 0:
            return False
        if course.week_type == "even" and week_number % 2 != 0:
            return False
        return True

    def _calculate_week_number(self, semester_start: str, target_day: date) -> int:
        start_date = self._parse_iso_date(semester_start)
        return (target_day - start_date).days // 7 + 1

    def _find_period(self, current_time: time) -> int | None:
        for period, (start_raw, end_raw) in PERIOD_TIMES.items():
            if time.fromisoformat(start_raw) <= current_time <= time.fromisoformat(end_raw):
                return period
        return None

    def _validate_course_payload(self, payload: CourseCreate) -> None:
        self._validate_course(Course(id="preview", **model_to_dict(payload)))

    def _validate_course(self, course: Course) -> None:
        if course.period_end < course.period_start:
            raise ValueError("结束节次不能早于开始节次")
        if any(week <= 0 for week in course.weeks):
            raise ValueError("周次必须为正整数")

    def _parse_iso_date(self, raw: str) -> date:
        try:
            return date.fromisoformat(raw)
        except ValueError as exc:
            raise ValueError("日期必须使用 YYYY-MM-DD 格式") from exc

    def _now_iso(self) -> str:
        return datetime.now().isoformat(timespec="seconds")
