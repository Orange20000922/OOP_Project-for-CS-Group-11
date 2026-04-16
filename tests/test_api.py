from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
import app.routers.auth as auth_router
import app.routers.query as query_router
import app.routers.schedule as schedule_router
import app.services as services_module
import app.storage.schedule_store as schedule_store_module
import app.storage.user_store as user_store_module
from app.models.course import Course
from app.services.auth_service import AuthService
from app.services.schedule_service import ScheduleService
from app.storage.schedule_store import ScheduleStore
from app.storage.user_store import UserStore


class APIScraperStub:
    def fetch_schedule(self, account, password, semester_id, *, prefer_playwright=False):
        return [
            Course(
                id="course-api-1",
                name="Algorithms",
                teacher="Teacher Wang",
                location="Room A216",
                weekday=1,
                period_start=1,
                period_end=2,
                weeks=[1],
                week_type="all",
            )
        ]

    def parse_pdf_schedule(self, content: bytes):
        return []


@pytest.fixture
def app_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    data_dir = tmp_path / "data"
    users_file = data_dir / "users.json"
    schedules_dir = data_dir / "schedules"
    logs_dir = data_dir / "logs"

    monkeypatch.setattr(user_store_module, "USERS_FILE", users_file)
    monkeypatch.setattr(schedule_store_module, "SCHEDULES_DIR", schedules_dir)
    monkeypatch.setattr(main_module, "DATA_DIR", data_dir)
    monkeypatch.setattr(main_module, "USERS_FILE", users_file)
    monkeypatch.setattr(main_module, "SCHEDULES_DIR", schedules_dir)
    monkeypatch.setattr(main_module, "LOGS_DIR", logs_dir)
    monkeypatch.setattr(main_module, "APP_LOG_FILE", logs_dir / "app.log")

    user_store = UserStore()
    schedule_store = ScheduleStore()
    scraper = APIScraperStub()
    auth_service = AuthService(user_store)
    schedule_service = ScheduleService(schedule_store, scraper)

    monkeypatch.setattr(services_module, "user_store", user_store)
    monkeypatch.setattr(services_module, "schedule_store", schedule_store)
    monkeypatch.setattr(services_module, "scnu_scraper", scraper)
    monkeypatch.setattr(services_module, "auth_service", auth_service)
    monkeypatch.setattr(services_module, "schedule_service", schedule_service)
    monkeypatch.setattr(main_module, "auth_service", auth_service)

    monkeypatch.setattr(auth_router, "auth_service", auth_service)
    monkeypatch.setattr(schedule_router, "auth_service", auth_service)
    monkeypatch.setattr(schedule_router, "schedule_service", schedule_service)
    monkeypatch.setattr(query_router, "auth_service", auth_service)
    monkeypatch.setattr(query_router, "schedule_service", schedule_service)

    with TestClient(main_module.app) as client:
        yield client


def test_auth_cookie_flow_and_request_logging(app_client: TestClient, log_records):
    register_response = app_client.post(
        "/auth/register",
        json={
            "student_id": "20250001",
            "name": "Alice",
            "password": "password123",
            "scnu_account": "20250001",
        },
    )
    assert register_response.status_code == 201

    login_response = app_client.post(
        "/auth/login",
        json={"student_id": "20250001", "password": "password123"},
    )
    assert login_response.status_code == 200
    assert "session_token" in app_client.cookies

    me_response = app_client.get("/auth/me")
    assert me_response.status_code == 200
    assert me_response.json()["student_id"] == "20250001"

    logout_response = app_client.post("/auth/logout")
    assert logout_response.status_code == 204

    unauthorized_response = app_client.get("/auth/me")
    assert unauthorized_response.status_code == 401

    assert any("HTTP POST /auth/login -> 200" in record["message"] for record in log_records)
    assert any("HTTP GET /auth/me -> 401" in record["message"] for record in log_records)


def test_schedule_and_query_endpoints(app_client: TestClient):
    app_client.post(
        "/auth/register",
        json={
            "student_id": "20250001",
            "name": "Alice",
            "password": "password123",
            "scnu_account": "20250001",
        },
    )
    login_response = app_client.post(
        "/auth/login",
        json={"student_id": "20250001", "password": "password123"},
    )
    assert login_response.status_code == 200

    init_response = app_client.post(
        "/schedule",
        json={"semester": "2025-2026-2", "semester_start": "2026-03-02"},
    )
    assert init_response.status_code == 201

    add_response = app_client.post(
        "/schedule/course",
        json={
            "name": "OOP",
            "teacher": "Teacher Li",
            "location": "Room 101",
            "weekday": 1,
            "period_start": 1,
            "period_end": 2,
            "weeks": [1],
            "week_type": "all",
        },
    )
    assert add_response.status_code == 201

    schedule_response = app_client.get("/schedule")
    assert schedule_response.status_code == 200
    assert len(schedule_response.json()["courses"]) == 1

    week_response = app_client.get("/query/week")
    assert week_response.status_code == 200
    assert set(week_response.json().keys()) == {"1", "2", "3", "4", "5", "6", "7"}

    overview_response = app_client.get("/query/overview", params={"week_offset": 0})
    assert overview_response.status_code == 200
    assert overview_response.json()["has_schedule"] is True
    assert overview_response.json()["schedule"]["semester"] == "2025-2026-2"
    assert overview_response.json()["week_offset"] == 0


def test_query_requires_login_logs(app_client: TestClient, log_records):
    response = app_client.get("/query/week")

    assert response.status_code == 401
    assert "detail" in response.json()
    assert any("Query week request failed with auth error" in record["message"] for record in log_records)


def test_query_overview_handles_missing_schedule(app_client: TestClient):
    app_client.post(
        "/auth/register",
        json={
            "student_id": "20250001",
            "name": "Alice",
            "password": "password123",
            "scnu_account": "20250001",
        },
    )
    login_response = app_client.post(
        "/auth/login",
        json={"student_id": "20250001", "password": "password123"},
    )
    assert login_response.status_code == 200

    response = app_client.get("/query/overview")
    assert response.status_code == 200
    assert response.json()["has_schedule"] is False
    assert response.json()["schedule"] is None
    assert response.json()["week_courses"] == {
        "1": [],
        "2": [],
        "3": [],
        "4": [],
        "5": [],
        "6": [],
        "7": [],
    }


def test_page_routes_redirect_and_guard_dashboard(app_client: TestClient):
    root_response = app_client.get("/", follow_redirects=False)
    assert root_response.status_code == 307
    assert root_response.headers["location"] == "/login"

    dashboard_response = app_client.get("/dashboard", follow_redirects=False)
    assert dashboard_response.status_code == 307
    assert dashboard_response.headers["location"] == "/login"

    knowledge_workspace_response = app_client.get("/knowledge-workspace", follow_redirects=False)
    assert knowledge_workspace_response.status_code == 307
    assert knowledge_workspace_response.headers["location"] == "/login"

    login_page_response = app_client.get("/login")
    assert login_page_response.status_code == 200
    assert "/static/auth-vue.js" in login_page_response.text

    static_response = app_client.get("/static/style.css")
    assert static_response.status_code == 200
    assert ":root" in static_response.text


def test_dashboard_route_serves_html_after_login(app_client: TestClient):
    app_client.post(
        "/auth/register",
        json={
            "student_id": "20250001",
            "name": "Alice",
            "password": "password123",
            "scnu_account": "20250001",
        },
    )
    login_response = app_client.post(
        "/auth/login",
        json={"student_id": "20250001", "password": "password123"},
    )
    assert login_response.status_code == 200

    login_page_response = app_client.get("/login", follow_redirects=False)
    assert login_page_response.status_code == 307
    assert login_page_response.headers["location"] == "/dashboard"

    dashboard_response = app_client.get("/dashboard")
    assert dashboard_response.status_code == 200
    assert "dashboard-app" in dashboard_response.text
    assert "/static/dashboard-vue.js" in dashboard_response.text

    knowledge_workspace_response = app_client.get("/knowledge-workspace")
    assert knowledge_workspace_response.status_code == 200
    assert "knowledge-app" in knowledge_workspace_response.text
    assert "/static/knowledge-workspace.js" in knowledge_workspace_response.text
