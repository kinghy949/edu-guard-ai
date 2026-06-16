from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.ai import LLMError, chat, resolve_runtime
from app.api.deps import CurrentUser, DbSession, require_admin
from app.core.crypto import decrypt_str, encrypt_str, looks_masked, mask
from app.models.llm_config import LLMConfig
from app.schemas.llm_config import (
    LLMConfigRead, LLMConfigTestRequest, LLMConfigUpdate,
)

router = APIRouter(dependencies=[Depends(require_admin)])


def _to_read(cfg: LLMConfig) -> dict:
    return {
        "id": cfg.id,
        "created_at": cfg.created_at,
        "updated_at": cfg.updated_at,
        "base_url": cfg.base_url,
        # 始终返回脱敏值；mask 会自动识别密文前缀
        "api_key": mask(cfg.api_key),
        "model": cfg.model,
        "temperature": cfg.temperature,
        "enabled": cfg.enabled,
        "note": cfg.note,
        "updated_by": cfg.updated_by,
    }


def _active(db) -> LLMConfig | None:
    return db.scalar(select(LLMConfig).order_by(LLMConfig.id.desc()))


@router.get("", response_model=LLMConfigRead | None, summary="读取当前 LLM 配置（api_key 脱敏）")
def get_config(db: DbSession):
    cfg = _active(db)
    return _to_read(cfg) if cfg else None


@router.put("", response_model=LLMConfigRead, summary="更新 LLM 配置")
def update_config(payload: LLMConfigUpdate, db: DbSession, current: CurrentUser):
    cfg = _active(db)
    if not cfg:
        if not (payload.base_url and payload.api_key and payload.model):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "首次创建需提供 base_url / api_key / model")
        cfg = LLMConfig(
            base_url=payload.base_url,
            api_key=encrypt_str(payload.api_key),
            model=payload.model,
            temperature=payload.temperature if payload.temperature is not None else 0.3,
            enabled=payload.enabled if payload.enabled is not None else True,
            note=payload.note,
            updated_by=current.id,
        )
        db.add(cfg)
    else:
        data = payload.model_dump(exclude_unset=True)
        if "api_key" in data:
            new_key = (data["api_key"] or "").strip()
            # 空 / 仅空格 / 收到掩码值（含 * 或 …）视为不修改
            if not new_key or looks_masked(new_key):
                data.pop("api_key")
            else:
                data["api_key"] = encrypt_str(new_key)
        for k, v in data.items():
            setattr(cfg, k, v)
        cfg.updated_by = current.id
    db.commit()
    db.refresh(cfg)
    return _to_read(cfg)


@router.post("/test", summary="使用当前/草稿配置发起一次简单调用")
def test_config(payload: LLMConfigTestRequest, db: DbSession):
    cfg = _active(db)
    if not cfg:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "尚未保存配置")
    try:
        rt = resolve_runtime(
            base_url=cfg.base_url, api_key=decrypt_str(cfg.api_key),
            model=cfg.model, temperature=cfg.temperature,
        )
        reply = chat([{"role": "user", "content": payload.prompt}], runtime=rt)
    except LLMError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e)) from e
    return {"ok": True, "reply": reply}
