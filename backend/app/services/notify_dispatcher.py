"""通知分发器：Outbox 模式。

- ``dispatch()`` 不再直接调外部 SMTP/webhook，而是把每个渠道写一条
  ``notifications`` 记录（status=pending），立刻返回，由调度器周期消费。
- inbox 渠道本身就是落库，直接置 sent，无需异步。
- 失败渠道与缺收件人等"永久错误"直接置 failed，不进入重试。
- ``deliver_pending()`` 由 APScheduler 30s 跑一次：取 pending 且
  next_attempt_at<=now，逐条调 notifier；失败按 [1,5,30] 分钟指数退避，
  达 3 次置 failed。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Iterable

from jinja2 import Template
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.notification import Notification, NotificationConfig, NotificationStatus
from app.models.student import Student
from app.models.user import User
from app.models.warning import Warning
from app.notifiers import REGISTRY

log = get_logger("notify")

# 指数退避（分钟）；总尝试次数 = MAX_RETRIES + 1（首次 + N 次重试）
_BACKOFF_MINUTES = [1, 5, 30]
MAX_RETRIES = len(_BACKOFF_MINUTES)


WARNING_SUBJECT_TPL = Template("【学业预警-{{ level_cn }}】{{ student_name }}（{{ student_no }}）")

WARNING_BODY_TPL = Template(
    """同学你好，本学期学业完成情况评估如下：

{{ summary }}

总学分要求：{{ total_required }}
已修学分  ：{{ total_earned }}
在修学分  ：{{ total_in_progress }}
学分缺口  ：{{ total_gap }}

各分类完成情况：
{%- for b in buckets %}
- {{ b.category }}：要求 {{ b.required }}，已修 {{ b.earned }}，在修 {{ b.in_progress }}，缺口 {{ b.gap }}
{%- endfor %}
{% if failed_count %}
⚠️ 存在 {{ failed_count }} 门挂科未通过，请尽快重修。
{% endif %}
请登录 EduGuard-AI 查看详细缺口与推荐补修课程。
"""
)

LEVEL_CN = {"info": "提示", "warn": "警告", "severe": "严重"}


@dataclass
class DispatchSummary:
    notification_ids: list[int]
    queued: int
    sent: int
    failed: int

    @property
    def succeeded(self) -> int:
        """兼容旧字段名。"""
        return self.sent


def _enabled_configs(db: Session) -> dict[str, dict[str, Any]]:
    from app.services.notification_secrets import decrypt_config_for_send

    rows = db.scalars(select(NotificationConfig).where(NotificationConfig.enabled.is_(True))).all()
    return {row.channel: decrypt_config_for_send(row.channel, row.config or {}) for row in rows}


def render_warning(warning: Warning, student: Student) -> tuple[str, str]:
    detail = warning.detail or {}
    ctx = {
        "level_cn": LEVEL_CN.get(warning.level, warning.level),
        "student_name": student.name,
        "student_no": student.student_no,
        "summary": warning.summary,
        "total_required": detail.get("total_required", "-"),
        "total_earned": sum_text(detail, "earned"),
        "total_in_progress": sum_text(detail, "in_progress"),
        "total_gap": detail.get("total_gap", "-"),
        "buckets": detail.get("buckets", []),
        "failed_count": detail.get("failed_count", 0),
    }
    return WARNING_SUBJECT_TPL.render(**ctx), WARNING_BODY_TPL.render(**ctx)


def sum_text(detail: dict[str, Any], key: str) -> str:
    try:
        total = sum((Decimal(b.get(key, "0")) for b in detail.get("buckets", [])), Decimal("0"))
        return str(total)
    except Exception:
        return "-"


def dispatch(
    db: Session,
    *,
    user: User | None,
    target_overrides: dict[str, str] | None,
    subject: str,
    content: str,
    channels: Iterable[str] | None = None,
    warning_id: int | None = None,
) -> DispatchSummary:
    """对单一收件人入队多渠道通知。

    - inbox 渠道：直接置 sent（写库即完成）
    - 其他渠道：写 pending，由 deliver_pending 异步消费
    - 永久错误（未启用/未知渠道/缺收件人）：直接 failed 不进入重试
    """
    cfgs = _enabled_configs(db)
    use = list(channels) if channels else list(cfgs.keys())

    ids: list[int] = []
    queued = sent = failed = 0
    now = datetime.now(timezone.utc)

    for ch in use:
        if ch not in cfgs:
            ids.append(_record_terminal(db, warning_id, user, ch, "-", subject, content,
                                        "渠道未启用"))
            failed += 1
            continue
        if ch not in REGISTRY:
            ids.append(_record_terminal(db, warning_id, user, ch, "-", subject, content,
                                        "未知渠道"))
            failed += 1
            continue
        target = _resolve_target(ch, user, target_overrides)
        if not target:
            ids.append(_record_terminal(db, warning_id, user, ch, "-", subject, content,
                                        "缺少收件人"))
            failed += 1
            continue

        if ch == "inbox":
            # 站内信本身就是数据库记录，写库即送达
            n = Notification(
                warning_id=warning_id, user_id=user.id if user else None,
                channel=ch, target=target, subject=subject, content=content,
                status=NotificationStatus.SENT, sent_at=now,
            )
            db.add(n)
            db.flush()
            ids.append(n.id)
            sent += 1
        else:
            n = Notification(
                warning_id=warning_id, user_id=user.id if user else None,
                channel=ch, target=target, subject=subject, content=content,
                status=NotificationStatus.PENDING, next_attempt_at=now,
            )
            db.add(n)
            db.flush()
            ids.append(n.id)
            queued += 1

    db.commit()
    return DispatchSummary(notification_ids=ids, queued=queued, sent=sent, failed=failed)


def _resolve_target(channel: str, user: User | None, overrides: dict[str, str] | None) -> str | None:
    if overrides and overrides.get(channel):
        return overrides[channel]
    if not user:
        return None
    if channel == "email":
        return user.email
    if channel == "sms":
        return user.phone
    if channel == "inbox":
        return user.username
    return user.display_name or user.username


def _record_terminal(
    db: Session, warning_id: int | None, user: User | None, channel: str,
    target: str, subject: str, content: str, reason: str,
) -> int:
    n = Notification(
        warning_id=warning_id, user_id=user.id if user else None,
        channel=channel, target=target, subject=subject, content=content,
        status=NotificationStatus.FAILED, error=reason,
    )
    db.add(n)
    db.flush()
    log.warning("notify_terminal_failed", channel=channel, target=target, reason=reason)
    return n.id


def dispatch_warning(
    db: Session,
    warning: Warning,
    *,
    channels: Iterable[str] | None = None,
) -> DispatchSummary:
    student = db.get(Student, warning.student_id)
    if not student:
        return DispatchSummary([], 0, 0, 0)
    user = db.get(User, student.user_id) if student.user_id else None
    subject, body = render_warning(warning, student)
    return dispatch(
        db, user=user, target_overrides=None, subject=subject,
        content=body, channels=channels, warning_id=warning.id,
    )


# ----- 异步消费 -----

def deliver_pending(db: Session, limit: int = 50) -> dict[str, int]:
    """取出 pending 通知逐条发送；失败按指数退避。

    使用 SELECT ... FOR UPDATE SKIP LOCKED，确保多消费者下不会重复处理。
    """
    now = datetime.now(timezone.utc)
    cfgs = _enabled_configs(db)

    stmt = (
        select(Notification)
        .where(
            Notification.status == NotificationStatus.PENDING,
            Notification.next_attempt_at.is_not(None),
            Notification.next_attempt_at <= now,
        )
        .order_by(Notification.id.asc())
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    rows = list(db.scalars(stmt))
    sent = failed = retried = 0

    for n in rows:
        cfg = cfgs.get(n.channel)
        notifier = REGISTRY.get(n.channel)
        if cfg is None or notifier is None:
            n.status = NotificationStatus.FAILED
            n.error = "渠道未启用或不支持"
            failed += 1
            continue
        outcome = notifier.send(n.target, n.subject or "", n.content or "", cfg)
        if outcome.ok:
            n.status = NotificationStatus.SENT
            n.sent_at = datetime.now(timezone.utc)
            n.error = None
            n.payload = outcome.payload
            sent += 1
        else:
            n.retry_count = (n.retry_count or 0) + 1
            n.error = outcome.detail
            n.payload = outcome.payload
            if n.retry_count >= MAX_RETRIES:
                n.status = NotificationStatus.FAILED
                failed += 1
            else:
                delay = _BACKOFF_MINUTES[n.retry_count - 1]
                n.next_attempt_at = datetime.now(timezone.utc) + timedelta(minutes=delay)
                retried += 1

    db.commit()
    if rows:
        log.info("notify_deliver", picked=len(rows), sent=sent, retried=retried, failed=failed)
    return {"picked": len(rows), "sent": sent, "retried": retried, "failed": failed}
