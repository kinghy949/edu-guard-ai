from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, require_admin, require_staff
from app.api.v1._helpers import apply_updates, get_or_404
from app.models.notification import Notification, NotificationConfig, NotificationStatus
from app.models.user import UserRole
from app.models.warning import Warning
from app.schemas.notification import (
    NotificationConfigRead,
    NotificationConfigUpdate,
    NotificationRead,
)
from app.services.audit import record_audit
from app.services.notification_secrets import encrypt_config_for_write, mask_config_for_read
from app.services.notify_dispatcher import dispatch, dispatch_warning

router = APIRouter()


# ----- 通知记录 -----

@router.get("", response_model=list[NotificationRead])
def list_notifications(
    db: DbSession,
    current: CurrentUser,
    channel: str | None = None,
    status_: str | None = None,
    skip: int = 0,
    limit: int = 100,
):
    stmt = select(Notification)
    if current.role == UserRole.STUDENT:
        stmt = stmt.where(Notification.user_id == current.id)
    if channel:
        stmt = stmt.where(Notification.channel == channel)
    if status_:
        stmt = stmt.where(Notification.status == status_)
    return db.scalars(stmt.order_by(Notification.created_at.desc()).offset(skip).limit(limit)).all()


@router.get("/{notification_id:int}", response_model=NotificationRead)
def get_notification(notification_id: int, db: DbSession, current: CurrentUser):
    n = get_or_404(db, Notification, notification_id, "通知")
    if current.role == UserRole.STUDENT and n.user_id != current.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权访问该通知")
    return n


# ----- 渠道配置（管理员） -----

def _mask_for_read(cfg: NotificationConfig) -> dict:
    return {
        "id": cfg.id,
        "created_at": cfg.created_at,
        "updated_at": cfg.updated_at,
        "channel": cfg.channel,
        "enabled": cfg.enabled,
        "config": mask_config_for_read(cfg.channel, cfg.config or {}),
        "updated_by": cfg.updated_by,
    }


@router.get("/configs/all", response_model=list[NotificationConfigRead], dependencies=[Depends(require_admin)])
def list_configs(db: DbSession):
    return [_mask_for_read(c) for c in db.scalars(select(NotificationConfig)).all()]


@router.put("/configs/{channel}", response_model=NotificationConfigRead, dependencies=[Depends(require_admin)])
def upsert_config(channel: str, payload: NotificationConfigUpdate, db: DbSession, current: CurrentUser, request: Request):
    from app.notifiers import REGISTRY

    # 仅当 enabled=True 且提供了 config 时做强校验
    if payload.enabled and payload.config is not None:
        notifier = REGISTRY.get(channel)
        if notifier and hasattr(notifier, "validate_config"):
            errs = notifier.validate_config(payload.config)
            if errs:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "；".join(errs))
    cfg = db.scalar(select(NotificationConfig).where(NotificationConfig.channel == channel))
    if not cfg:
        cfg = NotificationConfig(
            channel=channel,
            enabled=bool(payload.enabled),
            config=encrypt_config_for_write(channel, payload.config),
            updated_by=current.id,
        )
        db.add(cfg)
    else:
        data = payload.model_dump(exclude_unset=True)
        if "config" in data:
            data["config"] = encrypt_config_for_write(channel, data["config"], existing=cfg.config or {})
        apply_updates(cfg, data)
        cfg.updated_by = current.id
    # detail 中 config 仅记录键集合，避免泄露密文/明文
    detail_data = payload.model_dump(exclude_unset=True)
    if "config" in detail_data and isinstance(detail_data["config"], dict):
        detail_data["config"] = {"keys": sorted(detail_data["config"].keys())}
    record_audit(
        db, user=current, action="notifications.upsert_config",
        resource_type="notification_config", resource_id=channel,
        detail=detail_data, request=request,
    )
    db.commit()
    db.refresh(cfg)
    return _mask_for_read(cfg)


# ----- 测试 / 触发 -----

class TestSendRequest(BaseModel):
    channel: str
    target: str
    subject: str = "EduGuard-AI 通知测试"
    content: str = "这是一条测试通知。"


@router.post("/test", dependencies=[Depends(require_admin)], summary="测试发送一条通知")
def test_send(payload: TestSendRequest, db: DbSession):
    summary = dispatch(
        db,
        user=None,
        target_overrides={payload.channel: payload.target},
        subject=payload.subject,
        content=payload.content,
        channels=[payload.channel],
    )
    return summary.__dict__


class DispatchWarningRequest(BaseModel):
    channels: list[str] | None = None


@router.post("/warnings/{warning_id}/dispatch", dependencies=[Depends(require_staff)], summary="为某条预警入队通知")
def dispatch_for_warning(warning_id: int, payload: DispatchWarningRequest, db: DbSession):
    w = get_or_404(db, Warning, warning_id, "预警")
    summary = dispatch_warning(db, w, channels=payload.channels)
    return {"queued": summary.queued, "sent": summary.sent, "failed": summary.failed,
            "notification_ids": summary.notification_ids}


@router.post("/{notification_id}/resend", dependencies=[Depends(require_staff)], summary="重置失败/任意通知到队列重发")
def resend(notification_id: int, db: DbSession):
    from datetime import datetime, timezone

    n = get_or_404(db, Notification, notification_id, "通知")
    n.status = NotificationStatus.PENDING
    n.retry_count = 0
    n.next_attempt_at = datetime.now(timezone.utc)
    n.error = None
    db.commit()
    db.refresh(n)
    return {"ok": True, "id": n.id, "status": n.status}
