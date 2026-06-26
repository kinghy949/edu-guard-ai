from __future__ import annotations

from datetime import datetime, timezone

from app.models.notification import Notification, NotificationStatus
from tests.conftest import auth_header, make_user


def _inbox(db, user, *, subject: str, read: bool = False) -> Notification:
    n = Notification(
        user_id=user.id,
        channel="inbox",
        target=user.username,
        status=NotificationStatus.SENT,
        subject=subject,
        content=f"{subject} content",
        sent_at=datetime.now(timezone.utc),
        read_at=datetime.now(timezone.utc) if read else None,
    )
    db.add(n)
    db.flush()
    return n


def test_my_notifications_pagination_and_unread_count(client, db):
    user = make_user(db, role="student", username="msg_user")
    other = make_user(db, role="student", username="msg_other")
    _inbox(db, user, subject="未读 1")
    _inbox(db, user, subject="已读", read=True)
    _inbox(db, user, subject="未读 2")
    _inbox(db, other, subject="别人消息")
    db.commit()

    r = client.get("/api/v1/notifications/me?page=1&size=2", headers=auth_header(user))

    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 3
    assert data["unread_count"] == 2
    assert len(data["items"]) == 2
    assert {x["subject"] for x in data["items"]} <= {"未读 1", "已读", "未读 2"}


def test_unread_only_filter(client, db):
    user = make_user(db, role="student", username="msg_unread")
    _inbox(db, user, subject="未读")
    _inbox(db, user, subject="已读", read=True)
    db.commit()

    r = client.get("/api/v1/notifications/me?unread_only=true", headers=auth_header(user))

    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["subject"] == "未读"


def test_mark_read_only_owner(client, db):
    user = make_user(db, role="student", username="msg_owner")
    other = make_user(db, role="student", username="msg_intruder")
    n = _inbox(db, user, subject="我的消息")
    db.commit()

    forbidden = client.post(f"/api/v1/notifications/{n.id}/read", headers=auth_header(other))
    assert forbidden.status_code == 403

    ok = client.post(f"/api/v1/notifications/{n.id}/read", headers=auth_header(user))
    assert ok.status_code == 200
    assert ok.json()["read_at"] is not None


def test_read_all_marks_current_user_only(client, db):
    user = make_user(db, role="student", username="msg_all")
    other = make_user(db, role="student", username="msg_all_other")
    _inbox(db, user, subject="1")
    _inbox(db, user, subject="2")
    other_msg = _inbox(db, other, subject="other")
    db.commit()

    r = client.post("/api/v1/notifications/me/read-all", headers=auth_header(user))

    assert r.status_code == 200
    assert r.json()["updated"] == 2
    db.refresh(other_msg)
    assert other_msg.read_at is None
