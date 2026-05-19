from datetime import datetime
from typing import Any

from app.schemas._base import ORMBase, TimestampRead


class NotificationRead(TimestampRead):
    warning_id: int | None
    user_id: int | None
    channel: str
    target: str
    status: str
    sent_at: datetime | None
    error: str | None
    payload: dict[str, Any] | None


class NotificationConfigRead(TimestampRead):
    channel: str
    enabled: bool
    config: dict[str, Any] | None
    updated_by: int | None


class NotificationConfigUpdate(ORMBase):
    enabled: bool | None = None
    config: dict[str, Any] | None = None
