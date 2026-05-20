"""LLM 运行时配置加载：DB 优先，回退 settings。"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.llm_client import LLMRuntime, resolve_runtime
from app.models.llm_config import LLMConfig


def load_runtime(db: Session) -> LLMRuntime:
    cfg = db.scalar(
        select(LLMConfig).where(LLMConfig.enabled.is_(True)).order_by(LLMConfig.id.desc())
    )
    if cfg:
        return resolve_runtime(
            base_url=cfg.base_url,
            api_key=cfg.api_key,
            model=cfg.model,
            temperature=cfg.temperature,
        )
    return resolve_runtime()
