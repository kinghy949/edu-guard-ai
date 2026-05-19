from decimal import Decimal

from app.schemas._base import ORMBase, TimestampRead


class CourseCreate(ORMBase):
    code: str
    name: str
    credits: Decimal
    hours: int | None = None
    category_default: str | None = None
    description: str | None = None


class CourseUpdate(ORMBase):
    name: str | None = None
    credits: Decimal | None = None
    hours: int | None = None
    category_default: str | None = None
    description: str | None = None


class CourseRead(TimestampRead):
    code: str
    name: str
    credits: Decimal
    hours: int | None
    category_default: str | None
    description: str | None
