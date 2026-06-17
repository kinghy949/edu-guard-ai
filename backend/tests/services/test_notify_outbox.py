from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models.notification import Notification, NotificationConfig, NotificationStatus
from app.services.notify_dispatcher import (
    MAX_RETRIES,
    deliver_pending,
    dispatch,
)
from tests.conftest import make_user


def _enable_channel(db, channel, config=None):
    cfg = NotificationConfig(channel=channel, enabled=True, config=config or {})
    db.add(cfg)
    db.flush()
    return cfg


def test_dispatch_inbox_is_sent_immediately(client, db):
    u = make_user(db, username="ob_inbox")
    _enable_channel(db, "inbox")
    db.commit()
    s = dispatch(db, user=u, target_overrides=None,
                 subject="标题", content="正文", channels=["inbox"])
    assert s.sent == 1 and s.queued == 0 and s.failed == 0
    n = db.get(Notification, s.notification_ids[0])
    assert n.status == NotificationStatus.SENT
    assert n.content == "正文"
    assert n.sent_at is not None


def test_dispatch_email_is_queued_pending(client, db):
    u = make_user(db, username="ob_email", email="x@y.com")
    _enable_channel(db, "email", {"host": "smtp.x", "port": 465, "user": "u", "password": "p", "from": "f@y"})
    db.commit()
    s = dispatch(db, user=u, target_overrides=None,
                 subject="标题", content="正文", channels=["email"])
    assert s.queued == 1 and s.sent == 0 and s.failed == 0
    n = db.get(Notification, s.notification_ids[0])
    assert n.status == NotificationStatus.PENDING
    assert n.next_attempt_at is not None


def test_dispatch_missing_recipient_is_terminal_failed(client, db):
    u = make_user(db, username="ob_no_email", email=None)
    _enable_channel(db, "email", {})
    db.commit()
    s = dispatch(db, user=u, target_overrides=None,
                 subject="x", content="y", channels=["email"])
    assert s.failed == 1
    n = db.get(Notification, s.notification_ids[0])
    assert n.status == NotificationStatus.FAILED
    assert "收件人" in (n.error or "")


def test_deliver_pending_failure_triggers_backoff_then_failed(client, db, monkeypatch):
    """SMTP 一直失败 → 3 次后转 failed，间隔符合 [1,5,30] 分钟。"""
    u = make_user(db, username="ob_retry", email="x@y.com")
    _enable_channel(db, "email", {"host": "smtp.x", "port": 465, "user": "u", "password": "p", "from": "f@y"})
    db.commit()
    s = dispatch(db, user=u, target_overrides=None,
                 subject="x", content="y", channels=["email"])
    nid = s.notification_ids[0]

    # patch email notifier 永远失败
    from app.notifiers import REGISTRY
    from app.notifiers.base import SendOutcome

    monkeypatch.setitem(REGISTRY, "email",
                        type("N", (), {"send": staticmethod(
                            lambda target, sub, content, cfg: SendOutcome(ok=False, detail="boom")
                        )})())

    # 第 1 次投递 → 失败，retry_count=1，next +1min
    deliver_pending(db)
    db.expire_all()
    n = db.get(Notification, nid)
    assert n.status == NotificationStatus.PENDING
    assert n.retry_count == 1
    delta1 = (n.next_attempt_at - datetime.now(timezone.utc)).total_seconds()
    assert 30 < delta1 < 120  # 约 1 分钟

    # 让 next_attempt_at 到期再投
    n.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    deliver_pending(db)
    db.expire_all()
    n = db.get(Notification, nid)
    assert n.retry_count == 2
    delta2 = (n.next_attempt_at - datetime.now(timezone.utc)).total_seconds()
    assert 4 * 60 < delta2 < 6 * 60  # 约 5 分钟

    # 第 3 次投递 → retry_count 达到 MAX_RETRIES（=3），转 failed
    n.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    deliver_pending(db)
    db.expire_all()
    n = db.get(Notification, nid)
    assert n.retry_count == MAX_RETRIES
    assert n.status == NotificationStatus.FAILED


def test_resend_endpoint_resets_to_pending(client, db):
    u = make_user(db, role="counselor", username="ob_resend", password="GoodPass1")
    _enable_channel(db, "email", {"host": "smtp.x"})
    n = Notification(
        user_id=u.id, channel="email", target="x@y.com", subject="x", content="y",
        status=NotificationStatus.FAILED, retry_count=3, error="boom",
    )
    db.add(n)
    db.commit()

    r = client.post(
        "/api/v1/auth/login",
        data={"username": "ob_resend", "password": "GoodPass1"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    resp = client.post(f"/api/v1/notifications/{n.id}/resend", headers=headers)
    assert resp.status_code == 200, resp.text

    db.expire_all()
    n2 = db.get(Notification, n.id)
    assert n2.status == NotificationStatus.PENDING
    assert n2.retry_count == 0
    assert n2.error is None
