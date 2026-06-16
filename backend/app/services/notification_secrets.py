"""通知渠道配置的敏感字段加解密策略。

将"哪些 key 是敏感字段"集中在此，避免每个 notifier 各写一份。
"""
from __future__ import annotations

from typing import Any

from app.core.crypto import decrypt_str, encrypt_str, looks_masked, mask

SENSITIVE_KEYS: dict[str, list[str]] = {
    "email": ["password"],
    "sms": ["access_key_secret"],
    "wecom": ["webhook"],  # webhook URL 包含 key 参数，按敏感字段处理
    "dingtalk": ["webhook", "secret"],
    "inbox": [],
}


def _keys(channel: str) -> list[str]:
    return SENSITIVE_KEYS.get(channel, [])


def encrypt_config_for_write(
    channel: str,
    incoming: dict[str, Any] | None,
    *,
    existing: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """前端写入时调用：
    - 对敏感键加密
    - 收到掩码值则保留 existing 中的原值（不覆盖）
    """
    if incoming is None:
        return None
    out = dict(incoming)
    for k in _keys(channel):
        if k not in out:
            continue
        new_val = out.get(k)
        if new_val is None or new_val == "":
            # 显式置空 → 真的清空（管理员主动解绑）
            continue
        if isinstance(new_val, str) and looks_masked(new_val):
            # 掩码回写：保留旧密文
            if existing and k in existing:
                out[k] = existing.get(k)
            else:
                out.pop(k)
            continue
        out[k] = encrypt_str(new_val) if isinstance(new_val, str) else new_val
    return out


def decrypt_config_for_send(channel: str, stored: dict[str, Any] | None) -> dict[str, Any]:
    """读出供 notifier 实际发送使用：敏感键还原为明文。"""
    if not stored:
        return {}
    out = dict(stored)
    for k in _keys(channel):
        v = out.get(k)
        if isinstance(v, str) and v:
            out[k] = decrypt_str(v)
    return out


def mask_config_for_read(channel: str, stored: dict[str, Any] | None) -> dict[str, Any] | None:
    """返回给前端展示：敏感键统一脱敏。"""
    if stored is None:
        return None
    out = dict(stored)
    for k in _keys(channel):
        v = out.get(k)
        if isinstance(v, str) and v:
            out[k] = mask(v)
    return out
