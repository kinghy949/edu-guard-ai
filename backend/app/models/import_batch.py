from typing import Any

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._mixins import TimestampMixin


class ImportBatch(Base, TimestampMixin):
    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # completed / failed / rolled_back / dry_run
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="completed")
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    mapping: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    operator_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class ImportBatchRow(Base):
    __tablename__ = "import_batch_rows"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("import_batches.id", ondelete="CASCADE"), nullable=False
    )
    row_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # create / update
    op: Mapped[str] = mapped_column(String(8), nullable=False)
    table_name: Mapped[str] = mapped_column(String(32), nullable=False)
    record_pk: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # update 时记录变更字段的旧值快照，供 T2.4 回滚使用
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
