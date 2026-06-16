from __future__ import annotations

from app.core.crypto import decrypt_str, encrypt_str, looks_masked, mask


def test_encrypt_then_decrypt_roundtrip():
    cipher = encrypt_str("super-secret-key")
    assert cipher.startswith("enc:v1:")
    assert decrypt_str(cipher) == "super-secret-key"


def test_decrypt_plain_value_is_passthrough():
    # 存量明文数据无前缀，应原样返回，保证向后兼容
    assert decrypt_str("legacy-plain-key") == "legacy-plain-key"


def test_encrypt_idempotent_on_ciphertext():
    cipher = encrypt_str("abc123")
    # 已是密文则不再二次加密
    again = encrypt_str(cipher)
    assert again == cipher


def test_encrypt_handles_empty_and_none():
    assert encrypt_str(None) is None
    assert encrypt_str("") == ""
    assert decrypt_str(None) is None
    assert decrypt_str("") == ""


def test_mask_decrypts_ciphertext_before_masking():
    cipher = encrypt_str("sk-1234567890abcdef")
    masked = mask(cipher)
    assert masked.startswith("sk-1") and masked.endswith("cdef")
    assert "…" in masked


def test_mask_short_value_full_stars():
    assert mask("abc") == "***"


def test_looks_masked_detects_stars_and_ellipsis():
    assert looks_masked("sk-1…cdef") is True
    assert looks_masked("****") is True
    assert looks_masked("sk-realsecret") is False
    assert looks_masked("") is False
