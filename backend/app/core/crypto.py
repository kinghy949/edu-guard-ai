"""敏感字段对称加密。

- 密文形如 ``enc:v1:<base64-fernet>``，便于将来引入 v2 时区分
- 无前缀视为明文（存量数据），直接返回，保证向后兼容
- 密钥优先取 settings.ENCRYPTION_KEY；为空时由 SECRET_KEY 通过 PBKDF2
  派生（开发便利），prod 模式由 ensure_production_safe 检查显式配置
"""
from __future__ import annotations

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

_PREFIX = "enc:v1:"
_SALT = b"eduguard.fernet.v1"


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    key_src = (getattr(settings, "ENCRYPTION_KEY", "") or "").strip()
    if key_src:
        # 允许直接给 Fernet key（44 字节 base64 urlsafe），否则按字节做派生
        try:
            return Fernet(key_src.encode() if isinstance(key_src, str) else key_src)
        except (ValueError, TypeError):
            seed = key_src.encode("utf-8")
    else:
        seed = (settings.SECRET_KEY or "change-me").encode("utf-8")
    derived = hashlib.pbkdf2_hmac("sha256", seed, _SALT, 100_000, dklen=32)
    return Fernet(base64.urlsafe_b64encode(derived))


def encrypt_str(plain: str | None) -> str | None:
    if plain is None or plain == "":
        return plain
    if plain.startswith(_PREFIX):
        return plain  # 已经是密文则不再二次加密
    token = _fernet().encrypt(plain.encode("utf-8")).decode("ascii")
    return _PREFIX + token


def decrypt_str(value: str | None) -> str | None:
    """无前缀视为明文原样返回，保证存量数据可继续读取。"""
    if value is None or value == "":
        return value
    if not value.startswith(_PREFIX):
        return value
    token = value[len(_PREFIX):]
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken:
        # 密钥变更或数据损坏：返回空，避免崩溃
        return None


def mask(value: str | None, *, keep: int = 4) -> str:
    """脱敏显示：保留末 keep 位，其余用星号；过短直接全星。"""
    if not value:
        return ""
    if value.startswith(_PREFIX):
        value = decrypt_str(value) or ""
    if not value:
        return ""
    if len(value) <= keep * 2:
        return "*" * len(value)
    return f"{value[:keep]}…{value[-keep:]}"


def looks_masked(value: str | None) -> bool:
    """前端回传 mask 形式（含 * 或 …）时应跳过覆盖。"""
    if not value:
        return False
    return "*" in value or "…" in value
