from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Student, User
from app.models.user import UserRole
from tests.conftest import auth_header, make_user


def test_import_students_csv_returns_created_count(client: TestClient, db: Session) -> None:
    admin = make_user(db, role=UserRole.ADMIN, username="import-admin")
    db.commit()
    content = (
        "student_no,name,enroll_year,college,major,class_name,gender,email,phone\n"
        "I1001,导入学生,2024,计算机学院,软件工程,软工2401,女,student@example.edu,13800000000\n"
    ).encode()

    response = client.post(
        "/api/v1/imports/students",
        files={"file": ("students.csv", content, "text/csv")},
        headers=auth_header(admin),
    )

    assert response.status_code == 200
    assert response.json()["created"] == 1
    assert response.json()["updated"] == 0
    assert response.json()["errors"] == []
    assert db.scalar(select(Student).where(Student.student_no == "I1001")) is not None
    assert db.scalar(select(User).where(User.username == "I1001")) is not None


def test_import_students_all_error_file_rolls_back(client: TestClient, db: Session) -> None:
    admin = make_user(db, role=UserRole.ADMIN, username="import-admin-errors")
    before_students = db.scalar(select(func.count()).select_from(Student))
    before_users = db.scalar(select(func.count()).select_from(User))
    db.commit()
    content = (
        "student_no,name,enroll_year,college,major\n"
        ",缺学号,2024,计算机学院,软件工程\n"
        "I2002,年份错误,bad,计算机学院,软件工程\n"
    ).encode()

    response = client.post(
        "/api/v1/imports/students",
        files={"file": ("students.csv", content, "text/csv")},
        headers=auth_header(admin),
    )
    after_students = db.scalar(select(func.count()).select_from(Student))
    after_users = db.scalar(select(func.count()).select_from(User))

    assert response.status_code == 200
    assert response.json()["created"] == 0
    assert len(response.json()["errors"]) == 2
    assert after_students == before_students
    assert after_users == before_users
