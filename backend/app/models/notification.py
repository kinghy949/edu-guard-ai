from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._mixins import TimestampMixin


class NotificationChannel(StrEnum):
    INBOX = "inbox"
    EMAIL = "email"
    WECOM = "wecom"
    DINGTALK = "dingtalk"
    SMS = "sms"


class NotificationStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class Notification(Base, TimestampMixin):
    """单条通知发送记录。"""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    warning_id: Mapped[int | None] = mapped_column(
        ForeignKey("warnings.id", ondelete="SET NULL"), index=True, nullable=True
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    target: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=NotificationStatus.PENDING)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class NotificationConfig(Base, TimestampMixin):
    """通知渠道全局配置。"""

    __tablename__ = "notification_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    channel: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(default=False, nullable=False)
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
