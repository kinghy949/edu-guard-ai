from datetime import datetime
from typing import Any

from pydantic import ConfigDict

from app.schemas._base import ORMBase


class AuditLogRead(ORMBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None
    username: str | None
    action: str
    resource_type: str | None
    resource_id: str | None
    detail: dict[str, Any] | None
    ip: str | None
    created_at: datetime


class AuditLogPage(ORMBase):
    items: list[AuditLogRead]
    total: int
