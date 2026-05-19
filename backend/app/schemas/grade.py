from decimal import Decimal

from app.schemas._base import ORMBase, TimestampRead


class GradeCreate(ORMBase):
    student_id: int
    course_id: int
    semester: str
    credits_earned: Decimal = Decimal("0")
    score: Decimal | None = None
    status: str = "in_progress"


class GradeUpdate(ORMBase):
    credits_earned: Decimal | None = None
    score: Decimal | None = None
    status: str | None = None


class GradeRead(TimestampRead):
    student_id: int
    course_id: int
    semester: str
    credits_earned: Decimal
    score: Decimal | None
    status: str
