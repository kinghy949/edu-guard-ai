from sqlalchemy import ForeignKey, String, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._mixins import TimestampMixin


class Student(Base, TimestampMixin):
    """学生扩展信息（一对一关联 User）。"""

    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    student_no: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    gender: Mapped[str | None] = mapped_column(String(8), nullable=True)
    enroll_year: Mapped[int] = mapped_column(Integer, nullable=False)
    college: Mapped[str] = mapped_column(String(64), nullable=False)
    major: Mapped[str] = mapped_column(String(64), nullable=False)
    class_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    program_id: Mapped[int | None] = mapped_column(ForeignKey("programs.id", ondelete="SET NULL"))
