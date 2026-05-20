from app.schemas._base import ORMBase, TimestampRead


def _mask_key(k: str) -> str:
    if not k:
        return ""
    if len(k) <= 8:
        return "*" * len(k)
    return f"{k[:4]}…{k[-4:]}"


class LLMConfigRead(TimestampRead):
    base_url: str
    api_key: str  # 返回时已脱敏
    model: str
    temperature: float
    enabled: bool
    note: str | None
    updated_by: int | None


class LLMConfigUpdate(ORMBase):
    base_url: str | None = None
    api_key: str | None = None  # 留空表示不修改
    model: str | None = None
    temperature: float | None = None
    enabled: bool | None = None
    note: str | None = None


class LLMConfigTestRequest(ORMBase):
    prompt: str = "你好，请用一句话介绍你自己。"
