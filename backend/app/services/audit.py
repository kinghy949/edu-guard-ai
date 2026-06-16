"""操作审计：仅 db.add，跟随调用方事务一起 commit。

约定：action 形如 "资源.动作"（小写点分），如 imports.students、
warnings.resolve、llm_config.update。
"""
from __future__ import annotations

from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.user import User


def record_audit(
    db: Session,
    *,
    user: User | None,
    action: str,
    resource_type: str | None = None,
    resource_id: str | int | None = None,
    detail: dict[str, Any] | None = None,
    ip: str | None = None,
    request: Request | None = None,
) -> AuditLog:
    if ip is None and request is not None:
        forwarded = request.headers.get("x-forwarded-for")
        ip = (forwarded.split(",")[0].strip() if forwarded else None) or (
            request.client.host if request.client else None
        )
    entry = AuditLog(
        user_id=user.id if user else None,
        username=user.username if user else None,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        detail=detail,
        ip=ip,
    )
    db.add(entry)
    return entry
