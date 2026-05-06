"""
SQL 注入防护中间件
在 FastAPI 协议层拦截可疑的 SQL 注入请求
"""

import re
from typing import Callable
from urllib.parse import unquote

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.logging_config import logger


class SQLInjectionProtectionMiddleware(BaseHTTPMiddleware):
    """SQL 注入防护中间件"""

    # SQL 注入特征模式（不区分大小写）
    SQL_INJECTION_PATTERNS = [
        # 经典 SQL 注入
        r"(\bor\b|\band\b)\s+['\"]?\d+['\"]?\s*=\s*['\"]?\d+['\"]?",  # OR 1=1, AND 1=1
        r"(\bor\b|\band\b)\s+['\"]?[a-z]+['\"]?\s*=\s*['\"]?[a-z]+['\"]?",  # OR 'a'='a'

        # UNION 注入
        r"\bunion\b.*\bselect\b",

        # 注释符注入（宽松匹配：单引号后紧跟 --）
        r"'\s*--",
        r"/\*.*\*/",

        # 堆叠查询
        r";\s*(drop|delete|update|insert|create|alter|exec|execute)\b",

        # 时间盲注
        r"\b(sleep|benchmark|waitfor\s+delay)\b",

        # 数据库函数
        r"\b(concat|group_concat|load_file|into\s+outfile)\b",

        # 系统表查询
        r"\b(information_schema|sys\.\w+|mysql\.\w+|pg_catalog)\b",

        # 危险关键字组合
        r"\b(select|insert|update|delete|drop|create|alter|exec|execute)\b.*\b(from|into|where|table)\b",
    ]

    def __init__(self, app):
        super().__init__(app)
        self.patterns = [
            re.compile(pattern, re.IGNORECASE | re.MULTILINE)
            for pattern in self.SQL_INJECTION_PATTERNS
        ]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """拦截请求并检查 SQL 注入"""

        if request.url.path.startswith("/static") or request.url.path == "/health":
            return await call_next(request)

        if self._contains_sql_injection(unquote(str(request.url))):
            return self._block_request(request, "URL parameters")

        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                if body:
                    body_str = body.decode("utf-8", errors="ignore")
                    if self._contains_sql_injection(body_str):

                        async def receive():
                            return {"type": "http.request", "body": body}

                        request._receive = receive
                        return self._block_request(request, "request body")

                   
                    async def receive():
                        return {"type": "http.request", "body": body}

                    request._receive = receive
            except Exception as exc:
                logger.warning("Failed to read request body for SQL injection check: {}", exc)


        return await call_next(request)

    def _contains_sql_injection(self, text: str) -> bool:
        """检查文本是否包含 SQL 注入特征"""
        for pattern in self.patterns:
            if pattern.search(text):
                return True
        return False

    def _block_request(self, request: Request, location: str) -> JSONResponse:
        """阻止可疑请求"""
        client_ip = request.client.host if request.client else "unknown"
        logger.warning(
            "Blocked potential SQL injection attempt from {} on {} {} (detected in: {})",
            client_ip,
            request.method,
            request.url.path,
            location,
        )

        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "detail": "请求被拒绝：检测到潜在的 SQL 注入攻击",
                "error_code": "SQL_INJECTION_DETECTED",
            },
        )
