from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.core import HashTable
from app.models.user import UserLogin


def test_register_login_and_logout_flow(auth_service, make_user):
    assert isinstance(auth_service._sessions, HashTable)

    created = auth_service.register(make_user())
    assert created.student_id == "20250001"
    assert created.scnu_account == "20250001"

    token, current_user = auth_service.login(
        UserLogin(student_id="20250001", password="password123")
    )
    assert token
    assert current_user.student_id == "20250001"

    fetched = auth_service.get_current_user(token)
    assert fetched.student_id == "20250001"

    auth_service.logout(token)
    with pytest.raises(PermissionError, match="登录状态已失效"):
        auth_service.get_student_id(token)


def test_login_with_invalid_password_logs(auth_service, make_user, log_records):
    auth_service.register(make_user())

    with pytest.raises(PermissionError, match="学号或密码错误"):
        auth_service.login(UserLogin(student_id="20250001", password="wrong-password"))

    assert any(
        record["level"].name == "WARNING" and "Failed login attempt" in record["message"]
        for record in log_records
    )


def test_get_student_id_without_token_logs(auth_service, log_records):
    with pytest.raises(PermissionError, match="未登录"):
        auth_service.get_student_id(None)

    assert any("without login" in record["message"] for record in log_records)


def test_expired_session_is_removed(auth_service, make_user, log_records):
    auth_service.register(make_user())
    token, _ = auth_service.login(UserLogin(student_id="20250001", password="password123"))
    auth_service._sessions[token].expires_at = datetime.now() - timedelta(seconds=1)

    with pytest.raises(PermissionError, match="登录已过期"):
        auth_service.get_student_id(token)

    assert token not in auth_service._sessions
    assert any("Session expired" in record["message"] for record in log_records)


def test_missing_user_for_active_session_logs(auth_service, user_store, make_user, monkeypatch, log_records):
    auth_service.register(make_user())
    token, _ = auth_service.login(UserLogin(student_id="20250001", password="password123"))

    original_get = user_store.get

    def fake_get(student_id: str):
        if student_id == "20250001":
            return None
        return original_get(student_id)

    monkeypatch.setattr(user_store, "get", fake_get)

    with pytest.raises(PermissionError, match="登录状态已失效"):
        auth_service.get_current_user(token)

    assert any("lost backing user record" in record["message"] for record in log_records)
