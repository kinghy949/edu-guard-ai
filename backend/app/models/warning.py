from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._mixins import TimestampMixin


class WarningLevel(StrEnum):
    INFO = "info"        # 提示
    WARN = "warn"        # 警告
    SEVERE = "severe"    # 严重


class Warning(Base, TimestampMixin):
    """预警记录。"""

    __tablename__ = "warnings"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    level: Mapped[str] = mapped_column(String(16), nullable=False)
    semester: Mapped[str] = mapped_column(String(16), nullable=False)
    summary: Mapped[str] = mapped_column(String(255), nullable=False)
    detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolver_note: Mapped[str | None] = mapped_column(Text, nullable=True)
