from app.schemas._base import ORMBase, TimestampRead


class StudentCreate(ORMBase):
    user_id: int
    student_no: str
    name: str
    gender: str | None = None
    enroll_year: int
    college: str
    major: str
    class_name: str | None = None
    program_id: int | None = None


class StudentUpdate(ORMBase):
    name: str | None = None
    gender: str | None = None
    college: str | None = None
    major: str | None = None
    class_name: str | None = None
    program_id: int | None = None


class StudentRead(TimestampRead):
    user_id: int
    student_no: str
    name: str
    gender: str | None
    enroll_year: int
    college: str
    major: str
    class_name: str | None
    program_id: int | None
