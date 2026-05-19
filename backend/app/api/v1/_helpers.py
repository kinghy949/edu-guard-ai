from typing import TypeVar

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import Base

T = TypeVar("T", bound=Base)


def get_or_404(db: Session, model: type[T], obj_id: int, name: str = "对象") -> T:
    obj = db.get(model, obj_id)
    if not obj:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{name}不存在")
    return obj


def apply_updates(obj: Base, payload_dict: dict) -> None:
    for k, v in payload_dict.items():
        if v is not None:
            setattr(obj, k, v)
