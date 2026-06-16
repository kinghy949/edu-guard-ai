from __future__ import annotations

from tests.conftest import make_user


def _login(client, username: str, password: str):
    return client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


def test_login_returns_must_change_password_flag(client, db):
    make_user(db, username="stu_first", password="Init1234", must_change_password=True)
    db.commit()
    resp = _login(client, "stu_first", "Init1234")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["must_change_password"] is True
    assert body["access_token"]


def test_change_password_flow(client, db):
    user = make_user(db, username="stu_chg", password="Init1234", must_change_password=True)
    db.commit()
    login = _login(client, "stu_chg", "Init1234").json()
    headers = {"Authorization": f"Bearer {login['access_token']}"}

    # 原密码错误
    r1 = client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "Wrong1234", "new_password": "NewPass123"},
        headers=headers,
    )
    assert r1.status_code == 400

    # 新密码不符策略（纯数字）
    r2 = client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "Init1234", "new_password": "12345678"},
        headers=headers,
    )
    assert r2.status_code == 400
    assert "字母和数字" in r2.json()["detail"]

    # 新旧相同
    r3 = client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "Init1234", "new_password": "Init1234"},
        headers=headers,
    )
    assert r3.status_code == 400

    # 成功
    r4 = client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "Init1234", "new_password": "NewPass123"},
        headers=headers,
    )
    assert r4.status_code == 200
    assert r4.json()["must_change_password"] is False

    db.refresh(user)
    assert user.must_change_password is False
    assert user.password_updated_at is not None

    # 旧密码失效
    bad = _login(client, "stu_chg", "Init1234")
    assert bad.status_code == 401
    # 新密码可登录
    ok = _login(client, "stu_chg", "NewPass123")
    assert ok.status_code == 200
    assert ok.json()["must_change_password"] is False


def test_register_rejects_weak_password(client, db):
    admin = make_user(db, role="admin", username="admin_reg", password="AdminPass1")
    db.commit()
    login = _login(client, "admin_reg", "AdminPass1").json()
    headers = {"Authorization": f"Bearer {login['access_token']}"}

    # 长度 < 8 直接被 pydantic Field 拦截 → 422
    resp = client.post(
        "/api/v1/auth/register",
        json={"username": "newuser1", "password": "abc"},
        headers=headers,
    )
    assert resp.status_code in (400, 422)

    # 长度满足但策略不过（纯数字）
    resp2 = client.post(
        "/api/v1/auth/register",
        json={"username": "newuser2", "password": "12345678"},
        headers=headers,
    )
    assert resp2.status_code == 400

    # 合规密码成功
    resp3 = client.post(
        "/api/v1/auth/register",
        json={"username": "newuser3", "password": "StrongPass1", "role": "student"},
        headers=headers,
    )
    assert resp3.status_code == 200
