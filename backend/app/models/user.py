from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, String
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
    # 强制首次改密；批量导入的学生与 bootstrap 创建的管理员置 True
    must_change_password: Mapped[bool] = mapped_column(default=False, nullable=False)
    password_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 登录失败次数与锁定时间（T1.5 使用）
    failed_login_count: Mapped[int] = mapped_column(default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
