from sqlalchemy import Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._mixins import TimestampMixin


class Course(Base, TimestampMixin):
    """课程主数据。"""

    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    credits: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)
    hours: Mapped[int | None] = mapped_column(nullable=True)
    category_default: Mapped[str | None] = mapped_column(String(32), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
