from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "EduGuard-AI"
    APP_ENV: str = "dev"
    SECRET_KEY: str = "change-me"

    DATABASE_URL: str = "postgresql+psycopg://eduguard:eduguard@localhost:5432/eduguard"

    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4o-mini"

    SMTP_ENABLED: bool = False
    WECOM_ENABLED: bool = False
    DINGTALK_ENABLED: bool = False
    SMS_ENABLED: bool = False


settings = Settings()
