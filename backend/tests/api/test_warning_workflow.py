from __future__ import annotations

from app.models.warning import WarningStatus
from tests.conftest import (
    auth_header,
    make_program_with_buckets,
    make_student,
    make_user,
    make_warning,
)


def _staff(db):
    u = make_user(db, role="counselor", username="wf_staff")
    db.commit()
    return u


def test_legal_transitions_open_to_following_to_resolved(client, db):
    staff = _staff(db)
    program, _ = make_program_with_buckets(db)
    student = make_student(db, program=program)
    warn = make_warning(db, student=student)
    db.commit()
    headers = auth_header(staff)

    # open → follow
    r1 = client.post(f"/api/v1/warnings/{warn.id}/actions",
                     json={"action": "follow", "note": "已联系学生"}, headers=headers)
    assert r1.status_code == 200 and r1.json()["status"] == WarningStatus.FOLLOWING
    assert r1.json()["assignee_id"] == staff.id

    # following → resolve
    r2 = client.post(f"/api/v1/warnings/{warn.id}/actions",
                     json={"action": "resolve", "note": "已修读补救课"}, headers=headers)
    assert r2.status_code == 200 and r2.json()["status"] == WarningStatus.RESOLVED
    assert r2.json()["resolved_at"] is not None

    # 时间线含 2 条
    timeline = client.get(f"/api/v1/warnings/{warn.id}/actions", headers=headers).json()
    assert {t["action"] for t in timeline} >= {"follow", "resolve"}


def test_illegal_transition_returns_409(client, db):
    staff = _staff(db)
    program, _ = make_program_with_buckets(db)
    student = make_student(db, program=program)
    warn = make_warning(db, student=student)
    db.commit()
    headers = auth_header(staff)

    # 先 resolve
    client.post(f"/api/v1/warnings/{warn.id}/actions",
                json={"action": "resolve"}, headers=headers)
    # resolved 不能再 follow
    bad = client.post(f"/api/v1/warnings/{warn.id}/actions",
                      json={"action": "follow"}, headers=headers)
    assert bad.status_code == 409


def test_reopen_path(client, db):
    staff = _staff(db)
    program, _ = make_program_with_buckets(db)
    student = make_student(db, program=program)
    warn = make_warning(db, student=student)
    db.commit()
    headers = auth_header(staff)

    client.post(f"/api/v1/warnings/{warn.id}/actions",
                json={"action": "ignore"}, headers=headers)
    r = client.post(f"/api/v1/warnings/{warn.id}/actions",
                    json={"action": "reopen"}, headers=headers)
    assert r.status_code == 200 and r.json()["status"] == WarningStatus.OPEN
    assert r.json()["resolved_at"] is None


def test_comment_does_not_change_status(client, db):
    staff = _staff(db)
    program, _ = make_program_with_buckets(db)
    student = make_student(db, program=program)
    warn = make_warning(db, student=student)
    db.commit()
    headers = auth_header(staff)

    r = client.post(f"/api/v1/warnings/{warn.id}/actions",
                    json={"action": "comment", "note": "学生申请缓考"}, headers=headers)
    assert r.status_code == 200 and r.json()["status"] == WarningStatus.OPEN
    timeline = client.get(f"/api/v1/warnings/{warn.id}/actions", headers=headers).json()
    assert any(t["action"] == "comment" for t in timeline)


def test_legacy_resolve_endpoint_still_works(client, db):
    staff = _staff(db)
    program, _ = make_program_with_buckets(db)
    student = make_student(db, program=program)
    warn = make_warning(db, student=student)
    db.commit()
    headers = auth_header(staff)

    r = client.post(f"/api/v1/warnings/{warn.id}/resolve",
                    json={"note": "解决"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == WarningStatus.RESOLVED


def test_status_filter_and_student_actions_forbidden(client, db):
    staff = _staff(db)
    program, _ = make_program_with_buckets(db)
    student = make_student(db, program=program)
    warn = make_warning(db, student=student)
    db.commit()
    staff_headers = auth_header(staff)
    client.post(f"/api/v1/warnings/{warn.id}/actions",
                json={"action": "follow"}, headers=staff_headers)

    listed = client.get("/api/v1/warnings?status_=following", headers=staff_headers).json()
    assert any(w["id"] == warn.id for w in listed)

    # 学生 403 访问 actions 列表
    student_user = make_user(db, role="student", username="wf_stu")
    db.commit()
    r = client.get(f"/api/v1/warnings/{warn.id}/actions", headers=auth_header(student_user))
    assert r.status_code == 403
