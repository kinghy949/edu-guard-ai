from __future__ import annotations

from app.services.notification_secrets import (
    decrypt_config_for_send,
    encrypt_config_for_write,
    mask_config_for_read,
)


def test_email_password_is_encrypted_on_write():
    out = encrypt_config_for_write("email", {"host": "smtp.x.com", "password": "p@ss"})
    assert out["password"].startswith("enc:v1:")
    assert out["host"] == "smtp.x.com"


def test_masked_value_keeps_existing_ciphertext():
    existing = encrypt_config_for_write("email", {"password": "real"})
    incoming = {"password": "re****l"}  # 含 * 视为掩码
    merged = encrypt_config_for_write("email", incoming, existing=existing)
    assert merged["password"] == existing["password"]


def test_mask_for_read_hides_secret_keys():
    stored = encrypt_config_for_write("email", {"password": "real-password"})
    masked = mask_config_for_read("email", stored)
    assert "real-password" not in str(masked)
    assert "…" in masked["password"] or "*" in masked["password"]


def test_decrypt_for_send_restores_plain():
    stored = encrypt_config_for_write(
        "dingtalk", {"webhook": "https://oapi.dingtalk.com/robot/send?access_token=abcd", "secret": "SEC123"}
    )
    out = decrypt_config_for_send("dingtalk", stored)
    assert out["webhook"].startswith("https://oapi.dingtalk.com")
    assert out["secret"] == "SEC123"


def test_unknown_channel_passes_through():
    assert encrypt_config_for_write("custom", {"k": "v"}) == {"k": "v"}
    assert decrypt_config_for_send("custom", {"k": "v"}) == {"k": "v"}


def test_explicit_empty_value_clears_secret():
    out = encrypt_config_for_write("email", {"password": ""}, existing={"password": "enc:v1:xxx"})
    # 显式空 → 不保留旧值（管理员主动解绑）
    assert out["password"] == ""
