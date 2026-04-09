from __future__ import annotations

import base64
import json
import re
import tempfile
import time
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin
from uuid import uuid4

import requests

from app.config import (
    SCNU_JWXT_BASE,
    SCNU_LOGIN_PATH,
    SCNU_PUBLIC_KEY_PATH,
    SCNU_SCHEDULE_QUERY_PATH,
)
from app.models.course import Course


class SCNUScraper:
    def __init__(self, base_url: str = SCNU_JWXT_BASE) -> None:
        self.base_url = base_url.rstrip("/")

    def fetch_schedule(
        self,
        account: str,
        password: str,
        semester_id: str,
        *,
        prefer_playwright: bool = False,
    ) -> list[Course]:
        if prefer_playwright:
            return self.fetch_schedule_via_playwright(account, password, semester_id)
        return self.fetch_schedule_via_reverse(account, password, semester_id)

    def fetch_schedule_via_reverse(
        self,
        account: str,
        password: str,
        semester_id: str,
    ) -> list[Course]:
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/135.0.0.0 Safari/537.36"
                )
            }
        )

        login_url = urljoin(self.base_url, SCNU_LOGIN_PATH)
        login_page = session.get(login_url, timeout=20)
        login_page.raise_for_status()
        csrf_token = self._extract_csrf_token(login_page.text)
        public_key = self._get_public_key(session)
        encrypted_password = self.encrypt_password(
            password,
            public_key["modulus"],
            public_key["exponent"],
        )

        login_response = session.post(
            login_url,
            data={
                "csrftoken": csrf_token,
                "yhm": account,
                "mm": encrypted_password,
                "language": "zh_CN",
            },
            headers={"Referer": login_url},
            timeout=20,
            allow_redirects=True,
        )
        login_response.raise_for_status()
        if "用户登录" in login_response.text and "统一身份认证" in login_response.text:
            raise RuntimeError("SCNU 教务登录失败，可能需要统一认证/验证码或接口参数已变化")

        xnm, xqm = self._normalize_semester(semester_id)
        query_response = session.post(
            urljoin(self.base_url, SCNU_SCHEDULE_QUERY_PATH),
            data={"xnm": xnm, "xqm": xqm},
            timeout=20,
        )
        query_response.raise_for_status()
        try:
            payload = query_response.json()
        except json.JSONDecodeError as exc:
            raise RuntimeError("课表接口未返回 JSON，可能需要补充逆向参数") from exc

        courses = self.parse_schedule_payload(payload)
        if not courses:
            raise RuntimeError("未解析到课表数据，请检查 semester_id 或接口字段")
        return courses

    def fetch_schedule_via_playwright(
        self,
        account: str,
        password: str,
        semester_id: str,
    ) -> list[Course]:
        raise RuntimeError("Playwright 登录和 PDF 下载回退路径已预留，尚需按 SCNU 当前页面补选择器")

    def parse_pdf_schedule(self, content: bytes) -> list[Course]:
        try:
            import pdfplumber
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("缺少 pdfplumber，无法解析 PDF 课表") from exc

        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                temp_file.write(content)
                temp_path = Path(temp_file.name)

            courses: list[Course] = []
            with pdfplumber.open(str(temp_path)) as pdf:
                for page in pdf.pages:
                    for table in page.extract_tables() or []:
                        courses.extend(self._parse_pdf_table(table))
            deduped = self._deduplicate_courses(courses)
            if deduped:
                return deduped
        finally:
            if temp_path and temp_path.exists():
                temp_path.unlink(missing_ok=True)

        raise RuntimeError("未能从 PDF 中解析出课程，请改用标准 JSON 上传或手动录入")

    def parse_schedule_payload(self, payload: dict) -> list[Course]:
        rows = payload.get("kbList") or payload.get("data") or []
        courses: list[Course] = []
        for item in rows:
            name = (item.get("kcmc") or item.get("courseName") or "").strip()
            if not name:
                continue
            weekday_raw = item.get("xqj") or item.get("weekday")
            try:
                weekday = int(str(weekday_raw))
            except (TypeError, ValueError):
                continue

            period_start, period_end = self._parse_period_range(
                str(item.get("jcs") or item.get("jc") or item.get("kkjc") or "")
            )
            weeks, week_type = self._parse_week_spec(str(item.get("zcd") or item.get("kkzc") or ""))
            if not weeks:
                continue

            courses.append(
                Course(
                    id=uuid4().hex,
                    name=name,
                    teacher=(item.get("xm") or item.get("jsxm") or "").strip(),
                    location=(item.get("cdmc") or item.get("jsmc") or "").strip(),
                    weekday=weekday,
                    period_start=period_start,
                    period_end=period_end,
                    weeks=weeks,
                    week_type=week_type,
                )
            )
        return self._deduplicate_courses(courses)

    def encrypt_password(self, password: str, modulus_b64: str, exponent_b64: str) -> str:
        try:
            import rsa
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("缺少 rsa 依赖，无法执行新版正方登录加密") from exc

        modulus = int.from_bytes(base64.b64decode(modulus_b64), "big")
        exponent = int.from_bytes(base64.b64decode(exponent_b64), "big")
        public_key = rsa.PublicKey(modulus, exponent)
        return base64.b64encode(rsa.encrypt(password.encode("utf-8"), public_key)).decode("ascii")

    def _get_public_key(self, session: requests.Session) -> dict[str, str]:
        timestamp = str(int(time.time() * 1000))
        response = session.get(
            urljoin(self.base_url, SCNU_PUBLIC_KEY_PATH),
            params={"time": timestamp, "_": timestamp},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        modulus = payload.get("modulus")
        exponent = payload.get("exponent")
        if not modulus or not exponent:
            raise RuntimeError("未获取到教务系统公钥")
        return {"modulus": modulus, "exponent": exponent}

    def _extract_csrf_token(self, html: str) -> str:
        match = re.search(r'name="csrftoken"\s+value="([^"]+)"', html)
        if not match:
            raise RuntimeError("未在登录页中找到 csrftoken")
        return match.group(1)

    def _normalize_semester(self, semester_id: str) -> tuple[str, str]:
        try:
            start_year, _, term = semester_id.split("-")
        except ValueError as exc:
            raise RuntimeError("semester_id 格式应为 2025-2026-2") from exc

        term_mapping = {"1": "3", "2": "12", "3": "16"}
        return start_year, term_mapping.get(term, term)

    def _parse_period_range(self, raw: str) -> tuple[int, int]:
        matches = re.findall(r"\d+", raw)
        if not matches:
            raise RuntimeError(f"无法解析节次信息: {raw}")
        start = int(matches[0])
        end = int(matches[1]) if len(matches) > 1 else start
        return start, end

    def _parse_week_spec(self, raw: str) -> tuple[list[int], str]:
        text = raw.replace("（", "(").replace("）", ")").replace("周", "")
        week_type = "all"
        if "单" in text:
            week_type = "odd"
        elif "双" in text:
            week_type = "even"

        weeks: set[int] = set()
        for start_raw, end_raw in re.findall(r"(\d+)(?:-(\d+))?", text):
            start = int(start_raw)
            end = int(end_raw) if end_raw else start
            for week in range(start, end + 1):
                if week_type == "odd" and week % 2 == 0:
                    continue
                if week_type == "even" and week % 2 != 0:
                    continue
                weeks.add(week)
        return sorted(weeks), week_type

    def _deduplicate_courses(self, courses: Iterable[Course]) -> list[Course]:
        deduped: dict[tuple, Course] = {}
        for course in courses:
            key = (
                course.name,
                course.teacher,
                course.location,
                course.weekday,
                course.period_start,
                course.period_end,
                tuple(course.weeks),
                course.week_type,
            )
            deduped[key] = course
        return list(deduped.values())

    def _parse_pdf_table(self, table: list[list[str | None]]) -> list[Course]:
        if len(table) < 2:
            return []

        courses: list[Course] = []
        for row_index, row in enumerate(table[1:], start=1):
            if not row or len(row) < 2:
                continue
            default_period = (row_index, row_index)
            period_label = (row[0] or "").strip()
            if period_label:
                try:
                    default_period = self._parse_period_range(period_label)
                except RuntimeError:
                    pass
            for weekday, cell in enumerate(row[1:8], start=1):
                if not cell or not cell.strip():
                    continue
                courses.extend(
                    self._parse_pdf_cell(cell, weekday=weekday, default_period=default_period)
                )
        return courses

    def _parse_pdf_cell(
        self,
        raw: str,
        *,
        weekday: int,
        default_period: tuple[int, int],
    ) -> list[Course]:
        blocks = [block.strip() for block in re.split(r"\n{2,}", raw) if block.strip()]
        parsed: list[Course] = []
        for block in blocks:
            lines = [line.strip() for line in block.splitlines() if line.strip()]
            if not lines:
                continue
            weeks_line = next((line for line in lines if "周" in line), "")
            if not weeks_line:
                continue
            weeks, week_type = self._parse_week_spec(weeks_line)
            if not weeks:
                continue

            period_line = next((line for line in lines if "节" in line), "")
            if period_line:
                try:
                    period_start, period_end = self._parse_period_range(period_line)
                except RuntimeError:
                    period_start, period_end = default_period
            else:
                period_start, period_end = default_period

            parsed.append(
                Course(
                    id=uuid4().hex,
                    name=lines[0],
                    teacher=lines[1] if len(lines) > 1 else "",
                    location=lines[2] if len(lines) > 2 else "",
                    weekday=weekday,
                    period_start=period_start,
                    period_end=period_end,
                    weeks=weeks,
                    week_type=week_type,
                )
            )
        return parsed
