"""结构化日志配置。

- dev：彩色 ConsoleRenderer，便于本地阅读
- prod：JSONRenderer，便于采集到 ELK / 文件
- 统一接管 uvicorn / sqlalchemy 等第三方 logger 级别
- 通过 contextvars 注入 request_id，可在任意业务点 logger.info 自动携带
"""
from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

from app.core.config import settings


def setup_logging() -> None:
    """进程启动时调用一次。重复调用幂等。"""
    level = logging.DEBUG if settings.APP_ENV != "prod" else logging.INFO

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.APP_ENV == "prod":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())

    structlog.configure(
        processors=shared_processors + [renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # 接管标准库 logger，避免 uvicorn/sqlalchemy 仍走默认格式
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    for noisy in ("uvicorn", "uvicorn.error", "uvicorn.access", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.INFO if noisy != "sqlalchemy.engine" else logging.WARNING)


def get_logger(name: str | None = None):
    return structlog.get_logger(name) if name else structlog.get_logger()
