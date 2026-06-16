from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import settings
from app.core.rate_limit import reset_login_rate_limit
from tests.conftest import make_user


def _login(client, username: str, password: str):
    return client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


@pytest.fixture(autouse=True)
def _reset_rl():
    reset_login_rate_limit()
    yield
    reset_login_rate_limit()


def test_failed_login_locks_after_max(client, db):
    user = make_user(db, username="locktest", password="GoodPass1")
    db.commit()
    for _ in range(settings.LOGIN_MAX_FAILED):
        r = _login(client, "locktest", "WrongPass1")
        assert r.status_code == 401, r.text
    # 第 N+1 次：账户已锁，连正确密码也被拒
    r2 = _login(client, "locktest", "GoodPass1")
    assert r2.status_code == 423
    db.refresh(user)
    assert user.locked_until is not None
    assert user.failed_login_count == 0


def test_lock_releases_after_expiry(client, db):
    user = make_user(db, username="lockexp", password="GoodPass1")
    user.locked_until = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    # 锁已过期 → 正确密码应能登录
    r = _login(client, "lockexp", "GoodPass1")
    assert r.status_code == 200
    db.refresh(user)
    assert user.locked_until is None


def test_success_login_resets_counter(client, db):
    user = make_user(db, username="resetcnt", password="GoodPass1")
    user.failed_login_count = 3
    db.commit()
    r = _login(client, "resetcnt", "GoodPass1")
    assert r.status_code == 200
    db.refresh(user)
    assert user.failed_login_count == 0


def test_invalid_credential_message_does_not_leak_existence(client, db):
    make_user(db, username="exists", password="GoodPass1")
    db.commit()
    r1 = _login(client, "exists", "Bad12345").json()
    r2 = _login(client, "does_not_exist_xyz", "Bad12345").json()
    assert r1["detail"] == r2["detail"]


def test_ip_rate_limit_returns_429(client, db, monkeypatch):
    # 把限流阈值降到 3 便于测试
    monkeypatch.setattr(settings, "LOGIN_IP_RATE_LIMIT", 3)
    reset_login_rate_limit()
    for _ in range(3):
        # 失败也算一次请求
        r = _login(client, "no_such_user_for_rl", "BadPass1234")
        assert r.status_code in (401, 423)
    r2 = _login(client, "no_such_user_for_rl", "BadPass1234")
    assert r2.status_code == 429
