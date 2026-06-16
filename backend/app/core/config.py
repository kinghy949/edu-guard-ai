import json

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "EduGuard-AI"
    APP_ENV: str = "dev"
    SECRET_KEY: str = "change-me"
    # 允许的前端来源，逗号或 JSON 数组形式；默认仅放行本地开发地址
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]
    # JWT 过期时间（分钟），默认 24 小时
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

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
