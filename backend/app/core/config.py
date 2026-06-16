import json

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "EduGuard-AI"
    APP_ENV: str = "dev"
    SECRET_KEY: str = "change-me"
    # 敏感字段对称加密密钥（Fernet 44 字节 base64 urlsafe）；
    # 留空时由 SECRET_KEY 派生（仅供 dev 使用），prod 必须显式设置
    ENCRYPTION_KEY: str = ""
    # 允许的前端来源，逗号或 JSON 数组形式；默认仅放行本地开发地址
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]
    # JWT 过期时间（分钟），默认 24 小时
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    # 登录失败 N 次后锁定账户 LOCK_MINUTES 分钟
    LOGIN_MAX_FAILED: int = 5
    LOGIN_LOCK_MINUTES: int = 15
    # 单 IP 每分钟最多 LOGIN_IP_RATE_LIMIT 次登录请求；0 表示关闭
    LOGIN_IP_RATE_LIMIT: int = 10

    DATABASE_URL: str = "postgresql+psycopg://eduguard:eduguard@localhost:5432/eduguard"

    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4o-mini"

    SMTP_ENABLED: bool = False
    WECOM_ENABLED: bool = False
    DINGTALK_ENABLED: bool = False
    SMS_ENABLED: bool = False

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_cors_origins(cls, v):
        if v is None or v == "":
            return ["http://localhost:5173"]
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            s = v.strip()
            if s.startswith("["):
                return json.loads(s)
            return [item.strip() for item in s.split(",") if item.strip()]
        return v


settings = Settings()


def ensure_production_safe(s: Settings | None = None) -> None:
    """生产环境下校验关键密钥已被合理设置，缺失则拒绝启动。"""
    s = s or settings
    if s.APP_ENV != "prod":
        return
    weak = {"change-me", "change-me-in-prod", ""}
    if s.SECRET_KEY in weak or len(s.SECRET_KEY) < 32:
        raise RuntimeError(
            "生产环境必须设置强 SECRET_KEY（长度≥32，且不能使用默认值）。"
            "可用 `openssl rand -hex 32` 生成。"
        )
    if not s.ENCRYPTION_KEY:
        raise RuntimeError(
            "生产环境必须显式设置 ENCRYPTION_KEY（Fernet 44 字节 base64 urlsafe）。"
            "可用 `python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"` 生成。"
        )
