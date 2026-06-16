from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from decimal import Decimal
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import Base, get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models import Course, CreditBucket, Grade, Program, ProgramCourse, Student, User, Warning
from app.models.grade import GradeStatus
from app.models.user import UserRole
from app.models.warning import WarningLevel

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://eduguard:eduguard@localhost:5432/eduguard_test",
)


def _assert_test_database(url: str) -> None:
    parsed = urlparse(url.replace("+psycopg", ""))
    db_name = parsed.path.rsplit("/", 1)[-1]
    if "test" not in db_name:
        raise RuntimeError(
            "Refusing to run tests against a non-test database. "
            "Set TEST_DATABASE_URL to a database name containing 'test'."
        )


@pytest.fixture(scope="session")
def engine() -> Generator[Engine, None, None]:
    _assert_test_database(TEST_DATABASE_URL)
    test_engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True, future=True)
    Base.metadata.drop_all(test_engine)
    Base.metadata.create_all(test_engine)
    try:
        yield test_engine
    finally:
        Base.metadata.drop_all(test_engine)
        test_engine.dispose()


@pytest.fixture
def db(engine: Engine) -> Generator[Session, None, None]:
    connection = engine.connect()
    outer = connection.begin()
    TestingSessionLocal = sessionmaker(
        bind=connection,
        autoflush=False,
        autocommit=False,
        future=True,
        join_transaction_mode="create_savepoint",
    )
    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()


@pytest.fixture(autouse=True)
def _reset_login_rate_limit():
    # 进程级登录限流计数器在测试间会累加，每个用例前自动清零
    from app.core.rate_limit import reset_login_rate_limit

    reset_login_rate_limit()
    yield
    reset_login_rate_limit()


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def make_user(
    db: Session,
    *,
    role: str = UserRole.STUDENT,
    username: str | None = None,
    password: str = "Password123",
    email: str | None = None,
    phone: str | None = None,
    display_name: str | None = None,
    must_change_password: bool = False,
) -> User:
    username = username or f"{role}_{uuid.uuid4().hex[:12]}"
    user = User(
        username=username,
        password_hash=hash_password(password),
        role=role,
        email=email,
        phone=phone,
        display_name=display_name or username,
        must_change_password=must_change_password,
    )
    db.add(user)
    db.flush()
    return user


def make_student(
    db: Session,
    *,
    student_no: str = "20240001",
    name: str = "测试学生",
    enroll_year: int = 2024,
    college: str = "计算机学院",
    major: str = "软件工程",
    class_name: str = "软工2401",
    program: Program | None = None,
    user: User | None = None,
) -> Student:
    user = user or make_user(db, role=UserRole.STUDENT, username=student_no, display_name=name)
    student = Student(
        user_id=user.id,
        student_no=student_no,
        name=name,
        enroll_year=enroll_year,
        college=college,
        major=major,
        class_name=class_name,
        program_id=program.id if program else None,
    )
    db.add(student)
    db.flush()
    return student


def make_program_with_buckets(
    db: Session,
    *,
    code: str = "SE2024",
    name: str = "软件工程培养方案",
    total_credits: Decimal | str = "10",
    buckets: list[tuple[str, Decimal | str]] | None = None,
) -> tuple[Program, list[CreditBucket]]:
    program = Program(
        code=code,
        name=name,
        college="计算机学院",
        major="软件工程",
        version="2024",
        total_credits_required=Decimal(total_credits),
    )
    db.add(program)
    db.flush()
    bucket_rows: list[CreditBucket] = []
    for category, required in (buckets or [("必修", "6"), ("选修", "4")]):
        bucket = CreditBucket(
            program_id=program.id,
            category=category,
            credits_required=Decimal(required),
        )
        db.add(bucket)
        db.flush()
        bucket_rows.append(bucket)
    return program, bucket_rows


def make_course(
    db: Session,
    *,
    code: str,
    name: str,
    credits: Decimal | str = "2",
    bucket: CreditBucket | None = None,
    program: Program | None = None,
    is_required: bool = False,
    semester_suggested: int | None = None,
) -> Course:
    course = Course(code=code, name=name, credits=Decimal(credits))
    db.add(course)
    db.flush()
    if bucket and program:
        db.add(
            ProgramCourse(
                program_id=program.id,
                course_id=course.id,
                bucket_id=bucket.id,
                is_required=is_required,
                semester_suggested=semester_suggested,
            )
        )
        db.flush()
    return course


def make_grade(
    db: Session,
    *,
    student: Student,
    course: Course,
    semester: str = "2024-1",
    status: str = GradeStatus.COMPLETED,
    credits_earned: Decimal | str | None = None,
    score: Decimal | str | None = None,
) -> Grade:
    if credits_earned is None:
        credits_earned = course.credits if status == GradeStatus.COMPLETED else Decimal("0")
    grade = Grade(
        student_id=student.id,
        course_id=course.id,
        semester=semester,
        credits_earned=Decimal(credits_earned),
        score=Decimal(score) if score is not None else None,
        status=status,
    )
    db.add(grade)
    db.flush()
    return grade


def make_warning(
    db: Session,
    *,
    student: Student,
    level: str = WarningLevel.WARN,
    semester: str = "2024-2",
    summary: str = "测试预警",
    detail: dict | None = None,
) -> Warning:
    warning = Warning(
        student_id=student.id,
        level=level,
        semester=semester,
        summary=summary,
        detail=detail or {"total_required": "10", "total_gap": "4", "buckets": [], "failed_count": 0},
    )
    db.add(warning)
    db.flush()
    return warning


def auth_header(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}
