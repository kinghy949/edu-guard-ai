from __future__ import annotations

from decimal import Decimal

from app.models.grade import GradeStatus
from tests.conftest import (
    auth_header,
    make_course,
    make_grade,
    make_program_with_buckets,
    make_student,
    make_user,
)


def test_transcript_groups_by_semester(client, db):
    staff = make_user(db, role="counselor", username="tr_staff")
    program, _ = make_program_with_buckets(db)
    s = make_student(db, student_no="T0001", program=program)
    c1 = make_course(db, code="C001", name="高数", credits="4")
    c2 = make_course(db, code="C002", name="英语", credits="3")
    make_grade(db, student=s, course=c1, semester="2024-1",
               credits_earned=Decimal("4"), score=Decimal("88"),
               status=GradeStatus.COMPLETED)
    make_grade(db, student=s, course=c2, semester="2024-2",
               credits_earned=Decimal("0"), score=Decimal("40"),
               status=GradeStatus.FAILED)
    db.commit()

    r = client.get(f"/api/v1/students/{s.id}/transcript", headers=auth_header(staff))
    assert r.status_code == 200, r.text
    semesters = r.json()
    sem_map = {x["semester"]: x for x in semesters}
    assert {"2024-1", "2024-2"} <= set(sem_map.keys())
    assert sem_map["2024-1"]["courses"][0]["status"] == "completed"
    assert sem_map["2024-2"]["courses"][0]["status"] == "failed"


def test_transcript_student_can_view_self_not_others(client, db):
    staff_user = make_user(db, role="student", username="tr_owner")
    program, _ = make_program_with_buckets(db)
    me = make_student(db, student_no="T9001", program=program, user=staff_user)
    other = make_student(db, student_no="T9002", program=program)
    db.commit()

    headers = auth_header(staff_user)
    r1 = client.get(f"/api/v1/students/{me.id}/transcript", headers=headers)
    assert r1.status_code == 200
    r2 = client.get(f"/api/v1/students/{other.id}/transcript", headers=headers)
    assert r2.status_code == 403
