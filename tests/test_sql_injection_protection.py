"""
SQL 注入防护中间件测试
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


class TestSQLInjectionProtection:

    def test_normal_request_passes(self):
        """正常请求不被拦截"""
        resp = client.get("/login")
        assert resp.status_code != 400

    def test_normal_search_passes(self):
        """正常搜索参数不被拦截"""
        resp = client.get("/query/now")
        assert resp.status_code != 400

    def test_blocks_union_select_in_url(self):
        """拦截 URL 中的 UNION SELECT 注入"""
        resp = client.get("/login?id=1 UNION SELECT * FROM users")
        assert resp.status_code == 400
        assert resp.json()["error_code"] == "SQL_INJECTION_DETECTED"

    def test_blocks_or_1_equals_1_in_url(self):
        """拦截 URL 中的 OR 1=1 注入"""
        resp = client.get("/login?id=1 OR 1=1")
        assert resp.status_code == 400

    def test_blocks_drop_table_in_body(self):
        """拦截请求体中的 DROP TABLE 注入"""
        resp = client.post(
            "/auth/login",
            json={"student_id": "test'; DROP TABLE notes;--", "password": "123"},
        )
        assert resp.status_code == 400

    def test_blocks_sleep_injection_in_url(self):
        """拦截 URL 中的时间盲注"""
        resp = client.get("/login?id=1 AND SLEEP(5)")
        assert resp.status_code == 400

    def test_blocks_information_schema_in_url(self):
        """拦截 URL 中的系统表查询"""
        resp = client.get("/login?id=1 AND SELECT * FROM information_schema.tables")
        assert resp.status_code == 400

    def test_blocks_comment_injection_in_body(self):
        """拦截请求体中的注释符注入"""
        resp = client.post(
            "/auth/login",
            json={"student_id": "admin'-- ", "password": "x"},
        )
        assert resp.status_code == 400

    def test_blocks_stacked_queries_in_body(self):
        """拦截请求体中的堆叠查询"""
        resp = client.post(
            "/auth/login",
            json={"student_id": "test; DELETE FROM notes", "password": "x"},
        )
        assert resp.status_code == 400

    def test_static_files_not_checked(self):
        """静态文件请求跳过检查"""
        resp = client.get("/static/style.css")
        assert resp.status_code != 400

    def test_chinese_content_passes(self):
        """中文内容不被误拦截"""
        resp = client.post(
            "/auth/login",
            json={"student_id": "什么是面向对象程序设计中的多态", "password": "123"},
        )
        assert resp.status_code != 400

    def test_normal_code_snippet_passes(self):
        """正常代码片段不被误拦截"""
        resp = client.post(
            "/auth/login",
            json={"student_id": "20210001", "password": "if x == 1"},
        )
        assert resp.status_code != 400


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
