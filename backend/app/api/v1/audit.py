from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.api.deps import DbSession, require_admin
from app.models.audit import AuditLog
from app.schemas.audit import AuditLogPage, AuditLogRead

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/audit-logs", response_model=AuditLogPage, summary="查询操作审计日志")
def list_audit_logs(
    db: DbSession,
    action: str | None = None,
    user_id: int | None = None,
    since: datetime | None = Query(None, description="ISO 时间，>=since"),
    until: datetime | None = Query(None, description="ISO 时间，<until"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=500),
):
    stmt = select(AuditLog)
    count_stmt = select(func.count(AuditLog.id))
    if action:
        stmt = stmt.where(AuditLog.action == action)
        count_stmt = count_stmt.where(AuditLog.action == action)
    if user_id is not None:
        stmt = stmt.where(AuditLog.user_id == user_id)
        count_stmt = count_stmt.where(AuditLog.user_id == user_id)
    if since:
        stmt = stmt.where(AuditLog.created_at >= since)
        count_stmt = count_stmt.where(AuditLog.created_at >= since)
    if until:
        stmt = stmt.where(AuditLog.created_at < until)
        count_stmt = count_stmt.where(AuditLog.created_at < until)
    stmt = stmt.order_by(AuditLog.id.desc()).offset((page - 1) * size).limit(size)
    items = list(db.scalars(stmt))
    total = db.scalar(count_stmt) or 0
    return AuditLogPage(items=[AuditLogRead.model_validate(i) for i in items], total=total)
