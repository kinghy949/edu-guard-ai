from __future__ import annotations

import io
from decimal import Decimal

from sqlalchemy import select

from app.models.course import Course
from app.models.grade import Grade
from app.models.import_batch import ImportBatch
from app.models.student import Student
from app.models.user import User
from tests.conftest import make_course, make_program_with_buckets, make_student, make_user


def _login(client, username: str, password: str):
    return client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


def _headers(client, db, *, username, role="admin"):
    make_user(db, role=role, username=username, password="GoodPass1")
    db.commit()
    r = _login(client, username, "GoodPass1")
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _upload(client, headers, kind: str, csv: str):
    files = {"file": (f"{kind}.csv", io.BytesIO(csv.encode("utf-8")), "text/csv")}
    return client.post(f"/api/v1/imports/{kind}", files=files, headers=headers)


def test_rollback_student_create_deletes_user_and_student(client, db):
    admin = _headers(client, db, username="rb_admin")
    csv = "student_no,name,enroll_year,college,major,class_name\nR0001,回一,2024,计算机学院,软件工程,软工2401\n"
    body = _upload(client, admin, "students", csv).json()
    bid = body["batch_id"]
    db.expire_all()
    assert db.scalar(select(Student).where(Student.student_no == "R0001")) is not None

    r = client.post(f"/api/v1/imports/batches/{bid}/rollback", headers=admin)
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["deleted"] == 1
    db.expire_all()
    assert db.scalar(select(Student).where(Student.student_no == "R0001")) is None
    assert db.scalar(select(User).where(User.username == "R0001")) is None
    # batch 状态变更
    assert db.get(ImportBatch, bid).status == "rolled_back"


def test_rollback_update_restores_before_snapshot(client, db):
    admin = _headers(client, db, username="rb_upd")
    base_csv = "student_no,name,enroll_year,college,major,class_name\nR0002,回二,2024,计算机学院,软件工程,软工2401\n"
    _upload(client, admin, "students", base_csv)
    upd_csv = "student_no,name,enroll_year,college,major,class_name\nR0002,回二,2024,计算机学院,人工智能,AI2401\n"
    body = _upload(client, admin, "students", upd_csv).json()
    bid = body["batch_id"]

    db.expire_all()
    s = db.scalar(select(Student).where(Student.student_no == "R0002"))
    assert s.major == "人工智能"

    r = client.post(f"/api/v1/imports/batches/{bid}/rollback", headers=admin)
    assert r.status_code == 200
    assert r.json()["restored"] == 1
    db.expire_all()
    s = db.scalar(select(Student).where(Student.student_no == "R0002"))
    assert s.major == "软件工程"
    assert s.class_name == "软工2401"


def test_rollback_blocked_when_later_batch_of_same_kind(client, db):
    admin = _headers(client, db, username="rb_block")
    csv1 = "student_no,name,enroll_year,college,major,class_name\nR0003,回三,2024,A,B,C\n"
    csv2 = "student_no,name,enroll_year,college,major,class_name\nR0004,回四,2024,A,B,C\n"
    body1 = _upload(client, admin, "students", csv1).json()
    _upload(client, admin, "students", csv2)

    r = client.post(f"/api/v1/imports/batches/{body1['batch_id']}/rollback", headers=admin)
    assert r.status_code == 409


def test_rollback_skips_student_with_existing_grade(client, db):
    admin = _headers(client, db, username="rb_skip")
    csv = "student_no,name,enroll_year,college,major,class_name\nR0005,回五,2024,A,B,C\n"
    bid = _upload(client, admin, "students", csv).json()["batch_id"]

    db.expire_all()
    student = db.scalar(select(Student).where(Student.student_no == "R0005"))
    course = Course(code="CS999", name="测试课", credits=Decimal("2"))
    db.add(course)
    db.flush()
    db.add(Grade(student_id=student.id, course_id=course.id, semester="2024-1",
                 credits_earned=Decimal("2"), score=Decimal("80"), status="completed"))
    db.commit()

    r = client.post(f"/api/v1/imports/batches/{bid}/rollback", headers=admin)
    assert r.status_code == 200
    res = r.json()
    assert res["skipped"] == 1 and res["deleted"] == 0
    assert any("成绩" in d["reason"] for d in res["skipped_details"])
    db.expire_all()
    assert db.scalar(select(Student).where(Student.student_no == "R0005")) is not None


def test_rollback_requires_admin(client, db):
    # staff（非 admin）调用应 403
    counselor = _headers(client, db, username="rb_couns", role="counselor")
    csv = "student_no,name,enroll_year,college,major,class_name\nR0006,回六,2024,A,B,C\n"
    bid = _upload(client, counselor, "students", csv).json()["batch_id"]
    r = client.post(f"/api/v1/imports/batches/{bid}/rollback", headers=counselor)
    assert r.status_code == 403


def test_cannot_rollback_dry_run_or_already_rolled_back(client, db):
    admin = _headers(client, db, username="rb_status")
    csv = "student_no,name,enroll_year,college,major,class_name\nR0007,回七,2024,A,B,C\n"
    bid = _upload(client, admin, "students", csv).json()["batch_id"]
    # 第一次回滚成功
    client.post(f"/api/v1/imports/batches/{bid}/rollback", headers=admin)
    # 再次回滚被拒绝
    r2 = client.post(f"/api/v1/imports/batches/{bid}/rollback", headers=admin)
    assert r2.status_code == 409


def test_rollback_grade_update_restores_decimal(client, db):
    admin = _headers(client, db, username="rb_grade")
    # 先准备学生与课程（避开 importer 学生测试自动设的姓名）
    program, _ = make_program_with_buckets(db)
    student = make_student(db, student_no="G0001", program=program)
    course = make_course(db, code="MATH101", name="高数")
    # 已有 grade
    db.add(Grade(student_id=student.id, course_id=course.id, semester="2024-1",
                 credits_earned=Decimal("3"), score=Decimal("85"), status="completed"))
    db.commit()
    # 通过导入更新成绩
    csv = "student_no,course_code,semester,credits_earned,score,status\nG0001,MATH101,2024-1,3,95,completed\n"
    bid = _upload(client, admin, "grades", csv).json()["batch_id"]

    db.expire_all()
    g = db.scalar(select(Grade).where(Grade.student_id == student.id, Grade.course_id == course.id))
    assert g.score == Decimal("95")

    r = client.post(f"/api/v1/imports/batches/{bid}/rollback", headers=admin)
    assert r.status_code == 200 and r.json()["restored"] == 1
    db.expire_all()
    g = db.scalar(select(Grade).where(Grade.student_id == student.id, Grade.course_id == course.id))
    assert g.score == Decimal("85")
