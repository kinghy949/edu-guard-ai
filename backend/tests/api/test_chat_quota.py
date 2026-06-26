from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models.chat import ChatMessage, ChatSession
from tests.conftest import auth_header, make_user


def _session(db, user) -> ChatSession:
    s = ChatSession(user_id=user.id, title="quota")
    db.add(s)
    db.flush()
    return s


def _message(db, session, role: str, content: str, *, created_at=None) -> ChatMessage:
    m = ChatMessage(session_id=session.id, role=role, content=content)
    if created_at is not None:
        m.created_at = created_at
    db.add(m)
    db.flush()
    return m


def test_quota_counts_today_user_messages_across_sessions_not_assistant(client, db, monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "CHAT_DAILY_MESSAGE_LIMIT", 2)
    user = make_user(db, role="student", username="quota_user")
    s1 = _session(db, user)
    s2 = _session(db, user)
    _message(db, s1, "user", "今天 1")
    _message(db, s1, "assistant", "不计数")
    _message(db, s2, "user", "昨天", created_at=datetime.now(timezone.utc) - timedelta(days=1))
    db.commit()

    r = client.get("/api/v1/chat/quota", headers=auth_header(user))

    assert r.status_code == 200
    assert r.json() == {"limit": 2, "used": 1, "remaining": 1}


def test_send_message_over_quota_returns_429_before_llm(client, db, monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "CHAT_DAILY_MESSAGE_LIMIT", 2)
    user = make_user(db, role="student", username="quota_block")
    s = _session(db, user)
    _message(db, s, "user", "今天 1")
    _message(db, s, "user", "今天 2")
    db.commit()

    r = client.post(
        f"/api/v1/chat/sessions/{s.id}/messages",
        json={"content": "第三条"},
        headers=auth_header(user),
    )

    assert r.status_code == 429
    assert "今日 AI 对话次数已用完" in r.json()["detail"]


def test_stream_message_over_quota_returns_429(client, db, monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "CHAT_DAILY_MESSAGE_LIMIT", 1)
    user = make_user(db, role="student", username="quota_stream")
    s = _session(db, user)
    _message(db, s, "user", "今天 1")
    db.commit()

    r = client.post(
        f"/api/v1/chat/sessions/{s.id}/messages/stream",
        json={"content": "第二条"},
        headers=auth_header(user),
    )

    assert r.status_code == 429


def test_zero_limit_means_unlimited(client, db, monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "CHAT_DAILY_MESSAGE_LIMIT", 0)
    user = make_user(db, role="student", username="quota_unlimited")
    s = _session(db, user)
    _message(db, s, "user", "今天 1")
    db.commit()

    r = client.get("/api/v1/chat/quota", headers=auth_header(user))

    assert r.status_code == 200
    assert r.json()["limit"] == 0
    assert r.json()["remaining"] is None
