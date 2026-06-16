from __future__ import annotations

from sqlalchemy import select

from app.models.audit import AuditLog
from tests.conftest import make_user


def _login(client, username: str, password: str):
    return client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


def _bearer(client, db, *, role="admin", username):
    make_user(db, role=role, username=username, password="GoodPass1")
    db.commit()
    r = _login(client, username, "GoodPass1")
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_login_success_and_failure_are_audited(client, db):
    make_user(db, username="aud_user", password="GoodPass1")
    db.commit()
    _login(client, "aud_user", "WrongPwd1")
    _login(client, "aud_user", "GoodPass1")

    actions = [a.action for a in db.scalars(select(AuditLog).order_by(AuditLog.id))]
    assert "auth.login.failed" in actions
    assert "auth.login.success" in actions


def test_change_password_is_audited(client, db):
    headers = _bearer(client, db, role="student", username="aud_chg")
    client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "GoodPass1", "new_password": "Other123x"},
        headers=headers,
    )
    rows = [a.action for a in db.scalars(select(AuditLog))]
    assert "auth.change_password" in rows


def test_admin_can_list_audit_logs_student_cannot(client, db):
    admin_headers = _bearer(client, db, role="admin", username="aud_admin")
    student_headers = _bearer(client, db, role="student", username="aud_stu")

    r_ok = client.get("/api/v1/admin/audit-logs", headers=admin_headers)
    assert r_ok.status_code == 200
    body = r_ok.json()
    assert "items" in body and "total" in body
    assert body["total"] >= 2  # 至少包含两次 login.success

    r_forbidden = client.get("/api/v1/admin/audit-logs", headers=student_headers)
    assert r_forbidden.status_code == 403


def test_filter_by_action_and_pagination(client, db):
    headers = _bearer(client, db, role="admin", username="aud_admin2")
    r = client.get(
        "/api/v1/admin/audit-logs",
        params={"action": "auth.login.success", "page": 1, "size": 10},
        headers=headers,
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert all(i["action"] == "auth.login.success" for i in items)
