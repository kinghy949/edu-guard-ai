from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.conftest import auth_header, make_user


def test_login_success_and_me(client: TestClient, db: Session) -> None:
    user = make_user(db, username="alice", password="Password123", display_name="Alice")
    db.commit()

    response = client.post(
        "/api/v1/auth/login",
        data={"username": "alice", "password": "Password123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 200
    token = response.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["id"] == user.id
    assert me.json()["username"] == "alice"


def test_login_rejects_wrong_password(client: TestClient, db: Session) -> None:
    make_user(db, username="bob", password="Password123")
    db.commit()

    response = client.post(
        "/api/v1/auth/login",
        data={"username": "bob", "password": "wrong-password"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "用户名或密码错误"


def test_login_rejects_inactive_account(client: TestClient, db: Session) -> None:
    user = make_user(db, username="disabled", password="Password123")
    user.is_active = False
    db.commit()

    response = client.post(
        "/api/v1/auth/login",
        data={"username": "disabled", "password": "Password123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "账户已停用"


def test_me_rejects_inactive_token_user(client: TestClient, db: Session) -> None:
    user = make_user(db, username="inactive-token")
    user.is_active = False
    db.commit()

    response = client.get("/api/v1/auth/me", headers=auth_header(user))

    assert response.status_code == 401
