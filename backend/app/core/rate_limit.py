"""轻量内存级 IP 限流，专用于 /api/v1/auth/login 防暴力破解。

约束：仅在单 worker 部署下精确（计数器在进程内存）。生产部署
请在 docker-compose / uvicorn 启动参数中保持 --workers=1，与 APScheduler
的 advisory lock 共同满足单实例假设。
"""
from __future__ import annotations

import time
from collections import deque
from threading import Lock

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings


class _SlidingWindowCounter:
    """每个 IP 一个时间戳队列，O(1) 摊销追加 + 过期清理。"""

    def __init__(self, window_seconds: int = 60):
        self.window = window_seconds
        self._data: dict[str, deque[float]] = {}
        self._lock = Lock()

    def hit_and_check(self, key: str, limit: int) -> bool:
        """记录一次访问，返回是否允许（True=放行，False=超限）。"""
        if limit <= 0:
            return True
        now = time.monotonic()
        threshold = now - self.window
        with self._lock:
            dq = self._data.setdefault(key, deque())
            while dq and dq[0] < threshold:
                dq.popleft()
            if len(dq) >= limit:
                return False
            dq.append(now)
            # 防止内存无限增长：偶发清理空队列
            if len(self._data) > 1024:
                for k in [k for k, v in self._data.items() if not v]:
                    self._data.pop(k, None)
            return True

    def reset(self) -> None:
        with self._lock:
            self._data.clear()


_login_counter = _SlidingWindowCounter(window_seconds=60)


def reset_login_rate_limit() -> None:
    """测试用：清空计数器。"""
    _login_counter.reset()


class LoginRateLimitMiddleware(BaseHTTPMiddleware):
    """对 POST /api/v1/auth/login 按客户端 IP 限流。"""

    LOGIN_PATH = "/api/v1/auth/login"

    async def dispatch(self, request: Request, call_next):
        if request.method == "POST" and request.url.path == self.LOGIN_PATH:
            ip = (request.client.host if request.client else "unknown") or "unknown"
            forwarded = request.headers.get("x-forwarded-for")
            if forwarded:
                ip = forwarded.split(",")[0].strip() or ip
            if not _login_counter.hit_and_check(ip, settings.LOGIN_IP_RATE_LIMIT):
                return Response(
                    content='{"detail":"登录请求过于频繁，请稍后再试"}',
                    status_code=429,
                    media_type="application/json",
                )
        return await call_next(request)
