from sqlalchemy import ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._mixins import TimestampMixin


class Program(Base, TimestampMixin):
    """培养方案。"""

    __tablename__ = "programs"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    college: Mapped[str] = mapped_column(String(64), nullable=False)
    major: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)  # e.g. 2023
    total_credits_required: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class CreditBucket(Base, TimestampMixin):
    """培养方案下的学分分类要求（必修/限选/任选/通识/实践/创新创业 等）。"""

    __tablename__ = "credit_buckets"
    __table_args__ = (UniqueConstraint("program_id", "category", name="uq_program_category"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(ForeignKey("programs.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    credits_required: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class ProgramCourse(Base, TimestampMixin):
    """培养方案 × 课程，落到具体学分桶。"""

    __tablename__ = "program_courses"
    __table_args__ = (
        UniqueConstraint("program_id", "course_id", name="uq_program_course"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(ForeignKey("programs.id", ondelete="CASCADE"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    bucket_id: Mapped[int] = mapped_column(ForeignKey("credit_buckets.id", ondelete="RESTRICT"))
    is_required: Mapped[bool] = mapped_column(default=False, nullable=False)
    semester_suggested: Mapped[int | None] = mapped_column(nullable=True)
