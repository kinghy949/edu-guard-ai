from __future__ import annotations

from sqlalchemy import select

from app.models.llm_config import LLMConfig
from app.models.notification import NotificationConfig
from tests.conftest import make_user


def _admin_headers(client, db):
    make_user(db, role="admin", username="enc_admin", password="AdminPass1")
    db.commit()
    r = client.post(
        "/api/v1/auth/login",
        data={"username": "enc_admin", "password": "AdminPass1"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_llm_api_key_is_encrypted_at_rest(client, db):
    headers = _admin_headers(client, db)
    payload = {
        "base_url": "https://api.example.com/v1",
        "api_key": "sk-real-secret-xyz123456789",
        "model": "gpt-4o-mini",
    }
    resp = client.put("/api/v1/admin/llm-config", json=payload, headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["api_key"] != payload["api_key"]
    assert "…" in body["api_key"] or "*" in body["api_key"]

    row = db.scalar(select(LLMConfig).order_by(LLMConfig.id.desc()))
    assert row.api_key.startswith("enc:v1:")
    assert "sk-real-secret" not in row.api_key


def test_llm_masked_api_key_keeps_existing_secret(client, db):
    headers = _admin_headers(client, db)
    client.put(
        "/api/v1/admin/llm-config",
        json={"base_url": "https://a.test/v1", "api_key": "sk-original-001", "model": "m"},
        headers=headers,
    )
    original = db.scalar(select(LLMConfig).order_by(LLMConfig.id.desc())).api_key
    # 回传含 ... 的掩码值应被识别为"不修改"
    r2 = client.put(
        "/api/v1/admin/llm-config",
        json={"api_key": "sk-o…l-001", "model": "m2"},
        headers=headers,
    )
    assert r2.status_code == 200
    db.expire_all()
    after = db.scalar(select(LLMConfig).order_by(LLMConfig.id.desc()))
    assert after.api_key == original
    assert after.model == "m2"


def test_notification_email_password_encrypted_and_masked(client, db):
    headers = _admin_headers(client, db)
    resp = client.put(
        "/api/v1/notifications/configs/email",
        json={
            "enabled": True,
            "config": {"host": "smtp.example.com", "user": "noreply", "password": "very-secret-pwd"},
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["config"]["host"] == "smtp.example.com"
    assert body["config"]["password"] != "very-secret-pwd"

    row = db.scalar(select(NotificationConfig).where(NotificationConfig.channel == "email"))
    assert row.config["password"].startswith("enc:v1:")

    # GET all 同样掩码
    listed = client.get("/api/v1/notifications/configs/all", headers=headers).json()
    email_cfg = next(c for c in listed if c["channel"] == "email")
    assert "very-secret-pwd" not in str(email_cfg)
