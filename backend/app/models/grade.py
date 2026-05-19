from enum import StrEnum

from sqlalchemy import ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._mixins import TimestampMixin


class GradeStatus(StrEnum):
    COMPLETED = "completed"  # 已完成
    IN_PROGRESS = "in_progress"  # 在修
    FAILED = "failed"  # 挂科
    RETAKE = "retake"  # 重修中


class Grade(Base, TimestampMixin):
    """学生成绩 / 选课记录。"""

    __tablename__ = "grades"
    __table_args__ = (
        UniqueConstraint("student_id", "course_id", "semester", name="uq_student_course_semester"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="RESTRICT"), index=True)
    semester: Mapped[str] = mapped_column(String(16), nullable=False)  # e.g. 2024-1
    credits_earned: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False, default=0)
    score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=GradeStatus.IN_PROGRESS)
