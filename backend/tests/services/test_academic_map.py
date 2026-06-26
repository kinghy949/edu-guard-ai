from __future__ import annotations

from decimal import Decimal

from app.models.grade import GradeStatus
from app.services.credit_compare import build_academic_map
from tests.conftest import (
    auth_header,
    make_course,
    make_grade,
    make_program_with_buckets,
    make_student,
    make_user,
)


def test_status_completed_in_progress_failed_retake_and_not_taken(client, db):
    program, buckets = make_program_with_buckets(
        db, total_credits="20",
        buckets=[("必修", "10"), ("选修", "10")],
    )
    s = make_student(db, student_no="AM0001", program=program)
    c_done = make_course(db, code="DONE", name="完成课", credits="2",
                         bucket=buckets[0], program=program, is_required=True,
                         semester_suggested=1)
    c_in_prog = make_course(db, code="INPR", name="在修课", credits="2",
                            bucket=buckets[0], program=program, is_required=True,
                            semester_suggested=2)
    c_failed = make_course(db, code="FAIL", name="挂科课", credits="2",
                           bucket=buckets[0], program=program, is_required=True,
                           semester_suggested=3)
    c_retake = make_course(db, code="RETK", name="重修课", credits="2",
                           bucket=buckets[0], program=program, is_required=True,
                           semester_suggested=4)
    make_course(db, code="NONE", name="未修课", credits="2",
                bucket=buckets[1], program=program, is_required=False,
                semester_suggested=5)
    make_grade(db, student=s, course=c_done, semester="2024-1",
               credits_earned=Decimal("2"), score=Decimal("80"),
               status=GradeStatus.COMPLETED)
    make_grade(db, student=s, course=c_in_prog, semester="2024-2",
               status=GradeStatus.IN_PROGRESS)
    # 挂科：仅有 failed 历史
    make_grade(db, student=s, course=c_failed, semester="2024-2",
               status=GradeStatus.FAILED)
    make_grade(db, student=s, course=c_retake, semester="2024-2",
               status=GradeStatus.RETAKE)
    db.commit()

    m = build_academic_map(db, s)
    by_code = {x["code"]: x for b in m["buckets"] for x in b["courses"]}
    assert by_code["DONE"]["status"] == "completed"
    assert by_code["INPR"]["status"] == "in_progress"
    assert by_code["FAIL"]["status"] == "failed"
    assert by_code["RETK"]["status"] == "retake"
    assert by_code["NONE"]["status"] == "not_taken"

    # 推荐补修包含未修课
    rec_codes = {r["code"] for r in m["recommended"]}
    assert "NONE" in rec_codes


def test_retake_then_completed_reports_completed(client, db):
    program, buckets = make_program_with_buckets(db)
    s = make_student(db, student_no="AM0002", program=program)
    c = make_course(db, code="REP", name="重修通过", credits="2",
                    bucket=buckets[0], program=program, is_required=True)
    make_grade(db, student=s, course=c, semester="2024-1",
               status=GradeStatus.FAILED)
    make_grade(db, student=s, course=c, semester="2024-2",
               credits_earned=Decimal("2"), score=Decimal("70"),
               status=GradeStatus.COMPLETED)
    db.commit()
    m = build_academic_map(db, s)
    target = next(x for b in m["buckets"] for x in b["courses"] if x["code"] == "REP")
    assert target["status"] == "completed"


def test_student_without_program_returns_empty(client, db):
    s = make_student(db, student_no="AM0003", program=None)
    db.commit()
    m = build_academic_map(db, s)
    assert m["buckets"] == []
    assert m["recommended"] == []


def test_academic_map_api_permissions(client, db):
    program, buckets = make_program_with_buckets(db)
    student_user = make_user(db, role="student", username="map_student")
    student = make_student(db, student_no="AM0004", program=program, user=student_user)
    c = make_course(
        db,
        code="MAPAPI",
        name="地图接口课",
        credits="2",
        bucket=buckets[0],
        program=program,
        is_required=True,
    )
    make_grade(
        db,
        student=student,
        course=c,
        semester="2024-1",
        credits_earned=Decimal("2"),
        status=GradeStatus.COMPLETED,
    )
    staff = make_user(db, role="counselor", username="map_counselor")
    other_user = make_user(db, role="student", username="map_other")
    make_student(db, student_no="AM0005", user=other_user)
    db.commit()

    me = client.get("/api/v1/progress/me/map", headers=auth_header(student_user))
    assert me.status_code == 200
    assert me.json()["buckets"][0]["courses"][0]["status"] == "completed"

    staff_view = client.get(f"/api/v1/progress/{student.id}/map", headers=auth_header(staff))
    assert staff_view.status_code == 200

    forbidden = client.get(f"/api/v1/progress/{student.id}/map", headers=auth_header(other_user))
    assert forbidden.status_code == 403
