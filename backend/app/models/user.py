from enum import StrEnum

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._mixins import TimestampMixin


class UserRole(StrEnum):
    STUDENT = "student"
    COUNSELOR = "counselor"
    ADMIN = "admin"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default=UserRole.STUDENT)
    email: Mapped[str | None] = mapped_column(String(128), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
