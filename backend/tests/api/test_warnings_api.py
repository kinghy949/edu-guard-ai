from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import UserRole
from app.models.warning import Warning, WarningLevel
from tests.conftest import (
    auth_header,
    make_program_with_buckets,
    make_student,
    make_user,
    make_warning,
)


def test_student_only_sees_own_warnings(client: TestClient, db: Session) -> None:
    own_user = make_user(db, role=UserRole.STUDENT, username="warn-own")
    other_user = make_user(db, role=UserRole.STUDENT, username="warn-other")
    own_student = make_student(db, student_no="W1001", user=own_user)
    other_student = make_student(db, student_no="W1002", user=other_user)
    own_warning = make_warning(db, student=own_student, level=WarningLevel.WARN)
    other_warning = make_warning(db, student=other_student, level=WarningLevel.SEVERE)
    db.commit()

    response = client.get("/api/v1/warnings", headers=auth_header(own_user))
    forbidden = client.get(f"/api/v1/warnings/{other_warning.id}", headers=auth_header(own_user))
    own = client.get(f"/api/v1/warnings/{own_warning.id}", headers=auth_header(own_user))

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [own_warning.id]
    assert forbidden.status_code == 403
    assert own.status_code == 200
    assert own.json()["id"] == own_warning.id


def test_generate_warnings_full_flow(client: TestClient, db: Session) -> None:
    admin = make_user(db, role=UserRole.ADMIN, username="warn-admin")
    program, _ = make_program_with_buckets(db, total_credits="10", buckets=[("必修", "10")])
    student = make_student(db, student_no="W2001", enroll_year=2022, program=program)
    db.commit()

    response = client.post(
        "/api/v1/warnings/generate",
        json={"student_ids": [student.id], "semester": "2024-2"},
        headers=auth_header(admin),
    )
    warnings = list(db.scalars(select(Warning).where(Warning.student_id == student.id)))

    assert response.status_code == 200
    assert response.json()["created"] == 1
    assert response.json()["by_level"][WarningLevel.SEVERE.value] == 1
    assert len(warnings) == 1
    assert warnings[0].semester == "2024-2"
    assert warnings[0].level == WarningLevel.SEVERE.value
