"""Tests for SCNUScraper.fetch_schedule_via_playwright (SSO → JSON API path)."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from app.services.scnu_scraper import SCNUScraper

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FAKE_COOKIES = {"JSESSIONID": "abc123", "route": "xyz"}

FAKE_SCHEDULE_PAYLOAD = {
    "kbList": [
        {
            "kcmc": "面向对象程序设计",
            "xm": "李老师",
            "cdmc": "理工楼A101",
            "xqj": "1",
            "jcs": "1-2",
            "zcd": "1-16周",
        },
        {
            "kcmc": "数据结构",
            "xm": "王老师",
            "cdmc": "南B216",
            "xqj": "3",
            "jcs": "3-4",
            "zcd": "1-16周(单)",
        },
    ]
}


@pytest.fixture
def scraper():
    return SCNUScraper(base_url="https://jwxt.scnu.edu.cn")


# ---------------------------------------------------------------------------
# _sso_login_via_playwright
# ---------------------------------------------------------------------------


def _build_mock_playwright(final_url="https://jwxt.scnu.edu.cn/xtgl/index.html"):
    """Build a mock Playwright stack (pw → browser → context → page)."""
    page = MagicMock()
    page.url = "https://sso.scnu.edu.cn/AccountService/openapi/auth.html"

    code_input = MagicMock()
    code_input.count.return_value = 0
    page.locator.return_value = code_input

    def fake_wait_for_url(pattern, **kwargs):
        page.url = final_url

    page.wait_for_url.side_effect = fake_wait_for_url

    context = MagicMock()
    context.new_page.return_value = page
    context.cookies.return_value = [
        {"name": "JSESSIONID", "value": "abc123"},
        {"name": "route", "value": "xyz"},
    ]

    browser = MagicMock()
    browser.new_context.return_value = context

    pw = MagicMock()
    pw.chromium.launch.return_value = browser

    pw_ctx = MagicMock()
    pw_ctx.__enter__ = MagicMock(return_value=pw)
    pw_ctx.__exit__ = MagicMock(return_value=False)

    return pw_ctx, pw, browser, context, page


class TestSSOLogin:
    """Tests for _sso_login_via_playwright."""

    @patch("playwright.sync_api.sync_playwright")
    def test_success(self, mock_sync_pw, scraper):
        pw_ctx, pw, browser, context, page = _build_mock_playwright()
        mock_sync_pw.return_value = pw_ctx

        cookies = scraper._sso_login_via_playwright("20250001", "password123")

        assert cookies == FAKE_COOKIES
        page.fill.assert_any_call("#account", "20250001")
        page.fill.assert_any_call("#password", "password123")
        page.click.assert_called_once_with("#btn-password-login")
        page.evaluate.assert_called_once_with("gotoApp()")
        browser.close.assert_called_once()

    @patch("playwright.sync_api.sync_playwright")
    def test_captcha_raises(self, mock_sync_pw, scraper):
        pw_ctx, pw, browser, context, page = _build_mock_playwright()
        mock_sync_pw.return_value = pw_ctx

        code_input = MagicMock()
        code_input.count.return_value = 1
        code_input.get_attribute.return_value = "display: block"
        page.locator.return_value = code_input

        with pytest.raises(RuntimeError, match="验证码"):
            scraper._sso_login_via_playwright("20250001", "password123")

    @patch("playwright.sync_api.sync_playwright")
    def test_captcha_hidden_passes(self, mock_sync_pw, scraper):
        """Captcha element exists but hidden (display:none) — should not raise."""
        pw_ctx, pw, browser, context, page = _build_mock_playwright()
        mock_sync_pw.return_value = pw_ctx

        code_input = MagicMock()
        code_input.count.return_value = 1
        code_input.get_attribute.return_value = "display:none"
        page.locator.return_value = code_input

        cookies = scraper._sso_login_via_playwright("20250001", "pass")
        assert cookies == FAKE_COOKIES

    @patch("playwright.sync_api.sync_playwright")
    def test_redirect_failure(self, mock_sync_pw, scraper):
        pw_ctx, pw, browser, context, page = _build_mock_playwright()
        mock_sync_pw.return_value = pw_ctx

        page.wait_for_url.side_effect = Exception("timeout")

        with pytest.raises(RuntimeError, match="未成功跳转"):
            scraper._sso_login_via_playwright("20250001", "wrong_pass")

    @patch("playwright.sync_api.sync_playwright")
    def test_goto_app_failure(self, mock_sync_pw, scraper):
        pw_ctx, pw, browser, context, page = _build_mock_playwright()
        mock_sync_pw.return_value = pw_ctx

        page.evaluate.side_effect = Exception("gotoApp not defined")

        with pytest.raises(RuntimeError, match="确认跳转失败"):
            scraper._sso_login_via_playwright("20250001", "bad_pass")

    @patch("playwright.sync_api.sync_playwright")
    def test_browser_always_closed(self, mock_sync_pw, scraper):
        """Browser.close() is called even on error."""
        pw_ctx, pw, browser, context, page = _build_mock_playwright()
        mock_sync_pw.return_value = pw_ctx

        page.evaluate.side_effect = Exception("boom")

        with pytest.raises(RuntimeError):
            scraper._sso_login_via_playwright("x", "y")

        browser.close.assert_called_once()


# ---------------------------------------------------------------------------
# fetch_schedule_via_playwright (integration of SSO + API call)
# ---------------------------------------------------------------------------


class TestFetchScheduleViaPlaywright:
    """Tests for fetch_schedule_via_playwright."""

    def test_success(self, scraper):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = FAKE_SCHEDULE_PAYLOAD

        mock_session = MagicMock()
        mock_session.post.return_value = mock_resp

        with (
            patch.object(scraper, "_sso_login_via_playwright", return_value=FAKE_COOKIES),
            patch("app.services.scnu_scraper.requests.Session", return_value=mock_session),
        ):
            courses = scraper.fetch_schedule_via_playwright("user", "pass", "2025-2026-2")

        assert len(courses) == 2
        assert courses[0].name == "面向对象程序设计"
        assert courses[0].weekday == 1
        assert courses[0].period_start == 1
        assert courses[0].period_end == 2
        assert courses[1].name == "数据结构"
        assert courses[1].week_type == "odd"

        mock_session.post.assert_called_once()
        call_data = mock_session.post.call_args
        assert call_data.kwargs.get("data") == {"xnm": "2025", "xqm": "12"} or \
               call_data[1].get("data") == {"xnm": "2025", "xqm": "12"}

    def test_empty_courses_raises(self, scraper):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"kbList": []}

        mock_session = MagicMock()
        mock_session.post.return_value = mock_resp

        with (
            patch.object(scraper, "_sso_login_via_playwright", return_value=FAKE_COOKIES),
            patch("app.services.scnu_scraper.requests.Session", return_value=mock_session),
        ):
            with pytest.raises(RuntimeError, match="未解析到课表数据"):
                scraper.fetch_schedule_via_playwright("user", "pass", "2025-2026-2")

    def test_non_json_response_raises(self, scraper):
        mock_resp = MagicMock()
        mock_resp.json.side_effect = json.JSONDecodeError("msg", "doc", 0)

        mock_session = MagicMock()
        mock_session.post.return_value = mock_resp

        with (
            patch.object(scraper, "_sso_login_via_playwright", return_value=FAKE_COOKIES),
            patch("app.services.scnu_scraper.requests.Session", return_value=mock_session),
        ):
            with pytest.raises(RuntimeError, match="未返回 JSON"):
                scraper.fetch_schedule_via_playwright("user", "pass", "2025-2026-2")

    def test_sso_login_error_propagates(self, scraper):
        with patch.object(
            scraper,
            "_sso_login_via_playwright",
            side_effect=RuntimeError("SSO 登录触发了验证码"),
        ):
            with pytest.raises(RuntimeError, match="验证码"):
                scraper.fetch_schedule_via_playwright("user", "pass", "2025-2026-2")

    def test_strategy_dispatch(self, scraper):
        """fetch_schedule with prefer_playwright=True routes to Playwright path."""
        with patch.object(scraper, "fetch_schedule_via_playwright", return_value=[]) as mock_pw:
            try:
                scraper.fetch_schedule("u", "p", "2025-2026-2", prefer_playwright=True)
            except RuntimeError:
                pass  # may raise due to empty list; we just check dispatch
            mock_pw.assert_called_once_with("u", "p", "2025-2026-2")


# ---------------------------------------------------------------------------
# Helpers already present — quick sanity tests
# ---------------------------------------------------------------------------


class TestNormalizeSemester:
    def test_standard(self, scraper):
        assert scraper._normalize_semester("2025-2026-2") == ("2025", "12")

    def test_term1(self, scraper):
        assert scraper._normalize_semester("2025-2026-1") == ("2025", "3")

    def test_invalid(self, scraper):
        with pytest.raises(RuntimeError, match="格式"):
            scraper._normalize_semester("2025")


class TestParseWeekSpec:
    def test_all_weeks(self, scraper):
        weeks, wtype = scraper._parse_week_spec("1-16周")
        assert weeks == list(range(1, 17))
        assert wtype == "all"

    def test_odd_weeks(self, scraper):
        weeks, wtype = scraper._parse_week_spec("1-16周(单)")
        assert wtype == "odd"
        assert all(w % 2 == 1 for w in weeks)

    def test_even_weeks(self, scraper):
        weeks, wtype = scraper._parse_week_spec("2-16周(双)")
        assert wtype == "even"
        assert all(w % 2 == 0 for w in weeks)


class TestParsePeriodRange:
    def test_range(self, scraper):
        assert scraper._parse_period_range("1-2节") == (1, 2)

    def test_single(self, scraper):
        assert scraper._parse_period_range("5") == (5, 5)

    def test_invalid(self, scraper):
        with pytest.raises(RuntimeError):
            scraper._parse_period_range("无")


class TestParseSchedulePayload:
    def test_standard_payload(self, scraper):
        courses = scraper.parse_schedule_payload(FAKE_SCHEDULE_PAYLOAD)
        assert len(courses) == 2
        assert courses[0].name == "面向对象程序设计"
        assert courses[1].location == "南B216"

    def test_empty_kblist(self, scraper):
        assert scraper.parse_schedule_payload({"kbList": []}) == []

    def test_deduplication(self, scraper):
        dup_payload = {
            "kbList": [
                FAKE_SCHEDULE_PAYLOAD["kbList"][0],
                FAKE_SCHEDULE_PAYLOAD["kbList"][0],
            ]
        }
        courses = scraper.parse_schedule_payload(dup_payload)
        assert len(courses) == 1
