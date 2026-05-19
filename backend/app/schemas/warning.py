from datetime import datetime
from typing import Any

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
