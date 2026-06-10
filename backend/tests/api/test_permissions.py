from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import UserRole

from tests.conftest import (
    auth_header,
    make_program_with_buckets,
    make_student,
    make_user,
)


@dataclass(frozen=True)
class EndpointCase:
    name: str
    method: str
    path: Callable[[dict[str, int]], str]
    kwargs: Callable[[dict[str, int]], dict]
    expected: dict[str, int]


def _json(payload: dict) -> dict:
    return {"json": payload}


def _import_file(_: dict[str, int]) -> dict:
    content = (
        "student_no,name,enroll_year,college,major,class_name\n"
        "PX001,权限测试学生,2024,计算机学院,软件工程,软工2401\n"
    ).encode()
    return {"files": {"file": ("students.csv", content, "text/csv")}}


CASES = [
    EndpointCase(
        name="import_students",
        method="post",
        path=lambda ids: "/api/v1/imports/students",
        kwargs=_import_file,
        expected={"admin": 200, "counselor": 200, "student": 403, "anonymous": 401},
    ),
    EndpointCase(
        name="generate_warnings",
        method="post",
        path=lambda ids: "/api/v1/warnings/generate",
        kwargs=lambda ids: _json({"student_ids": [ids["student_id"]], "semester": "2024-2"}),
        expected={"admin": 200, "counselor": 200, "student": 403, "anonymous": 401},
    ),
    EndpointCase(
        name="notification_config",
        method="put",
        path=lambda ids: "/api/v1/notifications/configs/email",
        kwargs=lambda ids: _json({"enabled": False, "config": {}}),
        expected={"admin": 200, "counselor": 403, "student": 403, "anonymous": 401},
    ),
    EndpointCase(
        name="llm_config",
        method="put",
        path=lambda ids: "/api/v1/admin/llm-config",
        kwargs=lambda ids: _json(
            {
                "base_url": "https://example.test/v1",
                "api_key": "sk-test",
                "model": "test-model",
                "enabled": True,
            }
        ),
        expected={"admin": 200, "counselor": 403, "student": 403, "anonymous": 401},
    ),
    EndpointCase(
        name="students_list",
        method="get",
        path=lambda ids: "/api/v1/students",
        kwargs=lambda ids: {},
        expected={"admin": 200, "counselor": 200, "student": 403, "anonymous": 401},
    ),
    EndpointCase(
        name="warnings_list",
        method="get",
        path=lambda ids: "/api/v1/warnings",
        kwargs=lambda ids: {},
        expected={"admin": 200, "counselor": 200, "student": 200, "anonymous": 401},
    ),
    EndpointCase(
        name="student_progress",
        method="get",
        path=lambda ids: f"/api/v1/progress/{ids['student_id']}",
        kwargs=lambda ids: {},
        expected={"admin": 200, "counselor": 200, "student": 403, "anonymous": 401},
    ),
]


@pytest.fixture
def permission_context(db: Session) -> dict:
    program, _ = make_program_with_buckets(db, total_credits="10", buckets=[("必修", "10")])
    target_student = make_student(db, student_no="PM1001", enroll_year=2022, program=program)
    users = {
        "admin": make_user(db, role=UserRole.ADMIN, username="perm-admin"),
        "counselor": make_user(db, role=UserRole.COUNSELOR, username="perm-counselor"),
        "student": make_user(db, role=UserRole.STUDENT, username="perm-student"),
    }
    make_student(db, student_no="PM1002", user=users["student"], enroll_year=2024)
    db.commit()
    return {"users": users, "ids": {"student_id": target_student.id}}


@pytest.mark.parametrize("case", CASES, ids=[case.name for case in CASES])
@pytest.mark.parametrize("actor", ["admin", "counselor", "student", "anonymous"])
def test_permission_matrix(case: EndpointCase, actor: str, client: TestClient, permission_context: dict) -> None:
    headers = {}
    if actor != "anonymous":
        headers = auth_header(permission_context["users"][actor])
    request = getattr(client, case.method)

    response = request(case.path(permission_context["ids"]), headers=headers, **case.kwargs(permission_context["ids"]))

    assert response.status_code == case.expected[actor]
