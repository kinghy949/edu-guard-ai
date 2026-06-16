from datetime import datetime

from pydantic import ConfigDict, Field, field_validator

from app.schemas._base import ORMBase


class WarningRuleBase(ORMBase):
    name: str = Field(min_length=1, max_length=64)
    scope_college: str | None = None
    scope_major: str | None = None
    severe_total_gap_ratio: float = Field(0.5, ge=0, le=1)
    warn_total_gap_ratio: float = Field(0.25, ge=0, le=1)
    severe_required_ratio: float = Field(0.5, ge=0, le=1)
    warn_category_ratio: float = Field(0.7, ge=0, le=1)
    required_category_keywords: list[str] = Field(default_factory=lambda: ["必修"])
    stage_total_semesters: int = Field(8, ge=1, le=16)
    enabled: bool = True
    priority: int = 0

    @field_validator("required_category_keywords")
    @classmethod
    def _no_empty(cls, v: list[str]) -> list[str]:
        return [s for s in v if s and s.strip()] or ["必修"]


class WarningRuleCreate(WarningRuleBase):
    pass


class WarningRuleUpdate(ORMBase):
    name: str | None = None
    scope_college: str | None = None
    scope_major: str | None = None
    severe_total_gap_ratio: float | None = Field(None, ge=0, le=1)
    warn_total_gap_ratio: float | None = Field(None, ge=0, le=1)
    severe_required_ratio: float | None = Field(None, ge=0, le=1)
    warn_category_ratio: float | None = Field(None, ge=0, le=1)
    required_category_keywords: list[str] | None = None
    stage_total_semesters: int | None = Field(None, ge=1, le=16)
    enabled: bool | None = None
    priority: int | None = None


class WarningRuleRead(WarningRuleBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    updated_by: int | None
    created_at: datetime
    updated_at: datetime
