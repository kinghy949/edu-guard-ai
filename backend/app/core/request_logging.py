"""请求日志中间件：注入 request_id 并记录 http_request 事件。"""
from __future__ import annotations

import time
import uuid

import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import get_logger
from app.core.security import decode_token

log = get_logger("http")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=rid)

        # 解析当前用户（仅作为日志字段，不影响业务鉴权）
        auth = request.headers.get("authorization")
        if auth and auth.lower().startswith("bearer "):
            payload = decode_token(auth.split(" ", 1)[1])
            if payload and "sub" in payload:
                structlog.contextvars.bind_contextvars(user_id=payload["sub"])

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = int((time.perf_counter() - start) * 1000)
            log.exception(
                "http_request",
                method=request.method,
                path=request.url.path,
                status=500,
                duration_ms=duration_ms,
                client_ip=_client_ip(request),
            )
            raise

        duration_ms = int((time.perf_counter() - start) * 1000)
        # 健康检查日志降噪
        if request.url.path != "/health":
            log.info(
                "http_request",
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                duration_ms=duration_ms,
                client_ip=_client_ip(request),
            )
        response.headers["X-Request-ID"] = rid
        return response


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
