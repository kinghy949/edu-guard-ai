"""通知分发器。

职责：
- 从 ``notification_configs`` 读取启用的渠道与配置
- 按 ``channels`` 列表逐个适配器发送
- 每次发送都落 ``notifications`` 记录，包含状态、错误、payload
- 提供为某条 ``Warning`` 一次性多渠道分发的便捷入口
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from jinja2 import Template
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.notification import Notification, NotificationConfig, NotificationStatus
from app.models.student import Student
from app.models.user import User
from app.models.warning import Warning
from app.notifiers import REGISTRY


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
    succeeded: int
    failed: int


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
    # detail.buckets 中各桶字段是字符串小数；这里仅展示总值占位
    try:
        from decimal import Decimal
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
    """对单一收件人发送一次通知，跨多渠道。

    target_overrides 用于覆盖各渠道收件地址（如 email/sms 用具体地址；wecom/dingtalk 仅为标签）。
    若未提供，则按渠道自动从 user 字段推断。
    """
    cfgs = _enabled_configs(db)
    use = list(channels) if channels else list(cfgs.keys())

    ids: list[int] = []
    ok = err = 0
    for ch in use:
        cfg = cfgs.get(ch)
        if cfg is None:
            ids.append(_record(db, warning_id, user, ch, "-", NotificationStatus.FAILED, "渠道未启用", None))
            err += 1
            continue
        notifier = REGISTRY.get(ch)
        if not notifier:
            ids.append(_record(db, warning_id, user, ch, "-", NotificationStatus.FAILED, "未知渠道", None))
            err += 1
            continue

        target = _resolve_target(ch, user, target_overrides)
        if not target:
            ids.append(_record(db, warning_id, user, ch, "-", NotificationStatus.FAILED, "缺少收件人", None))
            err += 1
            continue

        outcome = notifier.send(target, subject, content, cfg)
        status = NotificationStatus.SENT if outcome.ok else NotificationStatus.FAILED
        ids.append(_record(db, warning_id, user, ch, target, status, outcome.detail, outcome.payload))
        if outcome.ok:
            ok += 1
        else:
            err += 1

    db.commit()
    return DispatchSummary(notification_ids=ids, succeeded=ok, failed=err)


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
    # wecom / dingtalk 群机器人不依赖个人 target
    return user.display_name or user.username


def _record(
    db: Session,
    warning_id: int | None,
    user: User | None,
    channel: str,
    target: str,
    status: str,
    detail: str,
    payload: dict[str, Any] | None,
) -> int:
    n = Notification(
        warning_id=warning_id,
        user_id=user.id if user else None,
        channel=channel,
        target=target,
        status=status,
        error=None if status == NotificationStatus.SENT else detail,
        sent_at=datetime.now(timezone.utc) if status == NotificationStatus.SENT else None,
        payload=payload,
    )
    db.add(n)
    db.flush()
    return n.id


def dispatch_warning(
    db: Session,
    warning: Warning,
    *,
    channels: Iterable[str] | None = None,
) -> DispatchSummary:
    student = db.get(Student, warning.student_id)
    if not student:
        return DispatchSummary([], 0, 0)
    user = db.get(User, student.user_id) if student.user_id else None
    subject, body = render_warning(warning, student)
    return dispatch(
        db,
        user=user,
        target_overrides=None,
        subject=subject,
        content=body,
        channels=channels,
        warning_id=warning.id,
    )
