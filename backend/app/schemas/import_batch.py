from datetime import datetime
from typing import Any

from pydantic import ConfigDict

from app.schemas._base import ORMBase


class ImportBatchSummary(ORMBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    filename: str | None
    status: str
    dry_run: bool
    total_rows: int
    created_count: int
    updated_count: int
    skipped_count: int
    error_count: int
    operator_id: int | None
    created_at: datetime
    updated_at: datetime


class ImportBatchDetail(ImportBatchSummary):
    errors: list[dict[str, Any]] | None = None
    mapping: dict[str, Any] | None = None


class ImportBatchPage(ORMBase):
    items: list[ImportBatchSummary]
    total: int
