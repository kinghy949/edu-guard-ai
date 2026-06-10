from __future__ import annotations

from decimal import Decimal

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Course, Grade, Program, ProgramCourse, Student, User
from app.models.grade import GradeStatus
from app.services.importer import import_courses, import_grades, import_program, import_students

from tests.conftest import make_course, make_student


def test_import_students_creates_updates_and_reports_errors_without_recreating_user(db: Session) -> None:
    created = import_students(
        db,
        pd.DataFrame(
            [
                {
                    "student_no": "20240001",
                    "name": "张三",
                    "enroll_year": "2024",
                    "college": "计算机学院",
                    "major": "软件工程",
                    "class_name": "软工2401",
                    "gender": "男",
                    "email": "zhang@example.edu",
                    "phone": "13800000000",
                },
                {"student_no": "", "name": "缺学号", "enroll_year": "2024", "college": "计算机学院", "major": "软件工程"},
                {"student_no": "20240002", "name": "年份错", "enroll_year": "bad", "college": "计算机学院", "major": "软件工程"},
            ]
        ),
    )
    db.flush()
    student = db.scalar(select(Student).where(Student.student_no == "20240001"))
    user = db.scalar(select(User).where(User.username == "20240001"))

    updated = import_students(
        db,
        pd.DataFrame(
            [
                {
                    "student_no": "20240001",
                    "name": "张三三",
                    "enroll_year": "2024",
                    "college": "人工智能学院",
                    "major": "人工智能",
                    "class_name": "智科2401",
                }
            ]
        ),
    )
    db.flush()
    user_after = db.scalar(select(User).where(User.username == "20240001"))
    student_after = db.scalar(select(Student).where(Student.student_no == "20240001"))

    assert created.created == 1
    assert len(created.errors) == 2
    assert student is not None
    assert user is not None
    assert updated.updated == 1
    assert user_after is not None
    assert user_after.id == user.id
    assert student_after is not None
    assert student_after.name == "张三三"
    assert student_after.college == "人工智能学院"


def test_import_courses_creates_updates_and_reports_errors(db: Session) -> None:
    first = import_courses(
        db,
        pd.DataFrame(
            [
                {"code": "CS101", "name": "程序设计", "credits": "3", "hours": "48", "category_default": "必修"},
                {"code": "", "name": "缺编码", "credits": "2"},
                {"code": "CS102", "name": "坏学分", "credits": "bad"},
            ]
        ),
    )
    db.flush()
    second = import_courses(
        db,
        pd.DataFrame(
            [
                {
                    "code": "CS101",
                    "name": "高级程序设计",
                    "credits": "4",
                    "hours": "",
                    "category_default": "专业必修",
                    "description": "updated",
                }
            ]
        ),
    )
    course = db.scalar(select(Course).where(Course.code == "CS101"))

    assert first.created == 1
    assert len(first.errors) == 2
    assert second.updated == 1
    assert course is not None
    assert course.name == "高级程序设计"
    assert Decimal(course.credits) == Decimal("4")
    assert course.hours is None


def test_import_program_creates_and_updates_program_rows_and_reports_errors(db: Session) -> None:
    first = import_program(
        db,
        pd.DataFrame(
            [
                {
                    "program_code": "SE2024",
                    "program_name": "软件工程",
                    "college": "计算机学院",
                    "major": "软件工程",
                    "version": "2024",
                    "total_credits": "10",
                    "course_code": "CS101",
                    "course_name": "程序设计",
                    "credits": "3",
                    "category": "必修",
                    "category_required_credits": "6",
                    "is_required": "是",
                    "semester_suggested": "1",
                },
                {
                    "program_code": "SE2024",
                    "program_name": "软件工程",
                    "college": "计算机学院",
                    "major": "软件工程",
                    "version": "2024",
                    "total_credits": "10",
                    "course_code": "CS999",
                    "course_name": "",
                    "credits": "",
                    "category": "必修",
                    "category_required_credits": "6",
                },
            ]
        ),
    )
    db.flush()
    second = import_program(
        db,
        pd.DataFrame(
            [
                {
                    "program_code": "SE2024",
                    "program_name": "软件工程",
                    "college": "计算机学院",
                    "major": "软件工程",
                    "version": "2024",
                    "total_credits": "10",
                    "course_code": "CS101",
                    "course_name": "程序设计",
                    "credits": "3",
                    "category": "必修",
                    "category_required_credits": "6",
                    "is_required": "false",
                    "semester_suggested": "2",
                }
            ]
        ),
    )
    program = db.scalar(select(Program).where(Program.code == "SE2024"))
    pc = db.scalar(select(ProgramCourse))

    assert first.created == 1
    assert len(first.errors) == 1
    assert second.updated == 1
    assert program is not None
    assert pc is not None
    assert pc.is_required is False
    assert pc.semester_suggested == 2


def test_import_grades_creates_updates_and_reports_errors(db: Session) -> None:
    student = make_student(db, student_no="20240003")
    course = make_course(db, code="CS201", name="离散数学", credits="2")

    first = import_grades(
        db,
        pd.DataFrame(
            [
                {
                    "student_no": student.student_no,
                    "course_code": course.code,
                    "semester": "2024-1",
                    "credits_earned": "2",
                    "score": "88",
                    "status": "已完成",
                },
                {
                    "student_no": "missing",
                    "course_code": course.code,
                    "semester": "2024-1",
                    "credits_earned": "2",
                },
                {
                    "student_no": student.student_no,
                    "course_code": "missing",
                    "semester": "2024-1",
                    "credits_earned": "2",
                },
                {
                    "student_no": student.student_no,
                    "course_code": course.code,
                    "semester": "2024-2",
                    "credits_earned": "bad",
                },
            ]
        ),
    )
    db.flush()
    second = import_grades(
        db,
        pd.DataFrame(
            [
                {
                    "student_no": student.student_no,
                    "course_code": course.code,
                    "semester": "2024-1",
                    "credits_earned": "0",
                    "score": "55",
                    "status": "挂科",
                }
            ]
        ),
    )
    grade = db.scalar(select(Grade).where(Grade.student_id == student.id, Grade.course_id == course.id))

    assert first.created == 1
    assert len(first.errors) == 3
    assert second.updated == 1
    assert grade is not None
    assert grade.status == GradeStatus.FAILED
    assert Decimal(grade.credits_earned) == Decimal("0")
