from decimal import Decimal

from app.schemas._base import ORMBase, TimestampRead


class ProgramCreate(ORMBase):
    code: str
    name: str
    college: str
    major: str
    version: str
    total_credits_required: Decimal
    note: str | None = None


class ProgramUpdate(ORMBase):
    name: str | None = None
    college: str | None = None
    major: str | None = None
    version: str | None = None
    total_credits_required: Decimal | None = None
    note: str | None = None


class ProgramRead(TimestampRead):
    code: str
    name: str
    college: str
    major: str
    version: str
    total_credits_required: Decimal
    note: str | None


class CreditBucketCreate(ORMBase):
    program_id: int
    category: str
    credits_required: Decimal
    note: str | None = None


class CreditBucketRead(TimestampRead):
    program_id: int
    category: str
    credits_required: Decimal
    note: str | None


class ProgramCourseCreate(ORMBase):
    program_id: int
    course_id: int
    bucket_id: int
    is_required: bool = False
    semester_suggested: int | None = None


class ProgramCourseRead(TimestampRead):
    program_id: int
    course_id: int
    bucket_id: int
    is_required: bool
    semester_suggested: int | None
