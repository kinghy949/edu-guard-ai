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
    email: str | None = None
    phone: str | None = None
    enroll_year: int
    college: str
    major: str
    class_name: str | None
    program_id: int | None


class StudentListItem(StudentRead):
    """学生列表展示项：附完成度（来自快照）与最高未处理预警级别。"""
    completion_ratio: float | None = None
    open_warning_level: str | None = None


class StudentListPage(ORMBase):
    items: list[StudentListItem]
    total: int
