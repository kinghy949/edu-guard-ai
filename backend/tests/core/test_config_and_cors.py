from __future__ import annotations

import pytest

from app.core.config import Settings, ensure_production_safe


def test_cors_origins_parses_comma_separated_string():
    s = Settings(CORS_ORIGINS="https://a.example.cn, https://b.example.cn")
    assert s.CORS_ORIGINS == ["https://a.example.cn", "https://b.example.cn"]


def test_cors_origins_parses_json_array_string():
    s = Settings(CORS_ORIGINS='["https://a.example.cn","https://b.example.cn"]')
    assert s.CORS_ORIGINS == ["https://a.example.cn", "https://b.example.cn"]


def test_cors_origins_keeps_list_input():
    s = Settings(CORS_ORIGINS=["https://x.example.cn"])
    assert s.CORS_ORIGINS == ["https://x.example.cn"]


def test_ensure_production_safe_dev_allows_default_key():
    s = Settings(APP_ENV="dev", SECRET_KEY="change-me")
    ensure_production_safe(s)  # should not raise


def test_ensure_production_safe_prod_rejects_default_key():
    s = Settings(APP_ENV="prod", SECRET_KEY="change-me")
    with pytest.raises(RuntimeError):
        ensure_production_safe(s)


def test_ensure_production_safe_prod_rejects_short_key():
    s = Settings(APP_ENV="prod", SECRET_KEY="short-key")
    with pytest.raises(RuntimeError):
        ensure_production_safe(s)


def test_ensure_production_safe_prod_accepts_strong_key():
    s = Settings(
        APP_ENV="prod",
        SECRET_KEY="a" * 32,
        ENCRYPTION_KEY="x" * 32,  # T1.6 起，prod 还需显式 ENCRYPTION_KEY
    )
    ensure_production_safe(s)


def test_ensure_production_safe_prod_requires_encryption_key():
    import pytest as _pytest
    s = Settings(APP_ENV="prod", SECRET_KEY="a" * 32, ENCRYPTION_KEY="")
    with _pytest.raises(RuntimeError):
        ensure_production_safe(s)


def test_cors_headers_not_wildcard(client):
    # client fixture 已构造 TestClient(app)，CORS 中间件按 settings.CORS_ORIGINS 限定来源
    resp = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    # 非白名单来源不应被回写 ACAO
    assert resp.headers.get("access-control-allow-origin") != "*"
    assert resp.headers.get("access-control-allow-origin") != "https://evil.example.com"
