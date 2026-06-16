from datetime import datetime
from typing import Any

from pydantic import ConfigDict, Field

from app.schemas._base import ORMBase, TimestampRead


class WarningCreate(ORMBase):
    student_id: int
    level: str
    semester: str
    summary: str
    detail: dict[str, Any] | None = None


class WarningRead(TimestampRead):
    student_id: int
    level: str
    semester: str
    summary: str
    detail: dict[str, Any] | None
    resolved_at: datetime | None
    resolver_note: str | None
    status: str = "open"
    assignee_id: int | None = None


class WarningActionCreate(ORMBase):
    action: str = Field(description="comment / follow / resolve / ignore / reopen")
    note: str | None = None


class WarningActionRead(ORMBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    warning_id: int
    user_id: int | None
    action: str
    note: str | None
    created_at: datetime
