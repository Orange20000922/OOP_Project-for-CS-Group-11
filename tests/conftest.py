from __future__ import annotations

from datetime import date as real_date
from datetime import datetime as real_datetime
from pathlib import Path

import pytest

import app.storage.schedule_store as schedule_store_module
import app.storage.user_store as user_store_module
from app.logging_config import configure_logging, logger
from app.models.course import Course, CourseCreate
from app.models.user import UserCreate
from app.services.auth_service import AuthService
from app.services.schedule_service import ScheduleService
from app.storage.schedule_store import ScheduleStore
from app.storage.user_store import UserStore


class DummyScraper:
    def __init__(self) -> None:
        self.fetch_result: list[Course] = []
        self.fetch_exception: Exception | None = None
        self.fetch_calls: list[dict[str, object]] = []
        self.pdf_result: list[Course] = []
        self.pdf_exception: Exception | None = None
        self.pdf_calls: list[bytes] = []

    def fetch_schedule(
        self,
        account: str,
        password: str,
        semester_id: str,
        *,
        prefer_playwright: bool = False,
    ) -> list[Course]:
        self.fetch_calls.append(
            {
                "account": account,
                "password": password,
                "semester_id": semester_id,
                "prefer_playwright": prefer_playwright,
            }
        )
        if self.fetch_exception is not None:
            raise self.fetch_exception
        return list(self.fetch_result)

    def parse_pdf_schedule(self, content: bytes) -> list[Course]:
        self.pdf_calls.append(content)
        if self.pdf_exception is not None:
            raise self.pdf_exception
        return list(self.pdf_result)


@pytest.fixture(autouse=True)
def isolated_logging(tmp_path: Path):
    configure_logging(log_file=tmp_path / "logs" / "test.log", force=True)
    yield


@pytest.fixture
def log_records():
    records: list[dict] = []
    sink_id = logger.add(lambda message: records.append(message.record), level="DEBUG")
    try:
        yield records
    finally:
        logger.remove(sink_id)


@pytest.fixture
def storage_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    data_dir = tmp_path / "data"
    users_file = data_dir / "users.json"
    schedules_dir = data_dir / "schedules"
    monkeypatch.setattr(user_store_module, "USERS_FILE", users_file)
    monkeypatch.setattr(schedule_store_module, "SCHEDULES_DIR", schedules_dir)
    return {
        "data_dir": data_dir,
        "users_file": users_file,
        "schedules_dir": schedules_dir,
    }


@pytest.fixture
def user_store(storage_paths):
    return UserStore()


@pytest.fixture
def schedule_store(storage_paths):
    return ScheduleStore()


@pytest.fixture
def auth_service(user_store):
    return AuthService(user_store)


@pytest.fixture
def dummy_scraper():
    return DummyScraper()


@pytest.fixture
def schedule_service(schedule_store, dummy_scraper):
    return ScheduleService(schedule_store, dummy_scraper)


@pytest.fixture
def make_course():
    def factory(**overrides) -> CourseCreate:
        payload = {
            "name": "面向对象程序设计",
            "teacher": "李老师",
            "location": "理工楼A101",
            "weekday": 1,
            "period_start": 1,
            "period_end": 2,
            "weeks": [1, 2, 3],
            "week_type": "all",
        }
        payload.update(overrides)
        return CourseCreate(**payload)

    return factory


@pytest.fixture
def make_user():
    def factory(**overrides) -> UserCreate:
        payload = {
            "student_id": "20250001",
            "name": "张三",
            "password": "password123",
            "scnu_account": "20250001",
        }
        payload.update(overrides)
        return UserCreate(**payload)

    return factory


@pytest.fixture
def sample_course() -> Course:
    return Course(
        id="course-1",
        name="面向对象程序设计",
        teacher="李老师",
        location="理工楼A101",
        weekday=1,
        period_start=1,
        period_end=2,
        weeks=[1, 2, 3],
        week_type="all",
    )


@pytest.fixture
def fake_clock(monkeypatch: pytest.MonkeyPatch):
    def apply(module, *, today: real_date, now: real_datetime) -> None:
        class FakeDate(real_date):
            @classmethod
            def today(cls):
                return cls(today.year, today.month, today.day)

        class FakeDatetime(real_datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(
                    now.year,
                    now.month,
                    now.day,
                    now.hour,
                    now.minute,
                    now.second,
                    now.microsecond,
                    tzinfo=tz,
                )

        monkeypatch.setattr(module, "date", FakeDate)
        monkeypatch.setattr(module, "datetime", FakeDatetime)

    return apply
