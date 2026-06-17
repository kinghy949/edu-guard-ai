from __future__ import annotations

from tests.conftest import auth_header, make_user


def test_upsert_sms_config_missing_keys_returns_400(client, db):
    admin = make_user(db, role="admin", username="nv_admin", password="GoodPass1")
    db.commit()
    headers = auth_header(admin)
    # provider=aliyun 但缺 sign_name / template_code
    r = client.put(
        "/api/v1/notifications/configs/sms",
        json={"enabled": True, "config": {"provider": "aliyun", "access_key_id": "x", "access_key_secret": "y"}},
        headers=headers,
    )
    assert r.status_code == 400
    assert "sign_name" in r.json()["detail"] or "template_code" in r.json()["detail"]


def test_upsert_sms_mock_passes(client, db):
    admin = make_user(db, role="admin", username="nv_admin_ok", password="GoodPass1")
    db.commit()
    headers = auth_header(admin)
    r = client.put(
        "/api/v1/notifications/configs/sms",
        json={"enabled": True, "config": {"provider": "mock"}},
        headers=headers,
    )
    assert r.status_code == 200
