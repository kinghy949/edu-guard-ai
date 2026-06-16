from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._mixins import TimestampMixin


class WarningRuleORM(Base, TimestampMixin):
    """预警规则；命名 WarningRuleORM 是为了与 services.warning_engine 中的
    WarningRule 数据类区分。"""

    __tablename__ = "warning_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    # 作用域：均为空 = 全局规则
    scope_college: Mapped[str | None] = mapped_column(String(64), nullable=True)
    scope_major: Mapped[str | None] = mapped_column(String(64), nullable=True)
    severe_total_gap_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    warn_total_gap_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.25)
    severe_required_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    warn_category_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    required_category_keywords: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=lambda: ["必修"])
    stage_total_semesters: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
