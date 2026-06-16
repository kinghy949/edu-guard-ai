from datetime import datetime

from pydantic import ConfigDict, Field

from app.schemas._base import ORMBase


class ImportMappingBase(ORMBase):
    kind: str = Field(min_length=1, max_length=16)
    name: str = Field(min_length=1, max_length=64)
    mapping: dict[str, str]
    is_default: bool = False


class ImportMappingCreate(ImportMappingBase):
    pass


class ImportMappingUpdate(ORMBase):
    name: str | None = None
    mapping: dict[str, str] | None = None
    is_default: bool | None = None


class ImportMappingRead(ImportMappingBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_by: int | None
    created_at: datetime
    updated_at: datetime
