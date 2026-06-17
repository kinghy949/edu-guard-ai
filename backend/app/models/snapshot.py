from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Float, ForeignKey, Integer, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class StudentProgressSnapshot(Base):
    __tablename__ = "student_progress_snapshots"

    student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("students.id", ondelete="CASCADE"), primary_key=True
    )
    total_required: Mapped[Decimal] = mapped_column(Numeric(6, 1), nullable=False, default=Decimal("0"))
    total_earned: Mapped[Decimal] = mapped_column(Numeric(6, 1), nullable=False, default=Decimal("0"))
    total_in_progress: Mapped[Decimal] = mapped_column(Numeric(6, 1), nullable=False, default=Decimal("0"))
    total_gap: Mapped[Decimal] = mapped_column(Numeric(6, 1), nullable=False, default=Decimal("0"))
    completion_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
