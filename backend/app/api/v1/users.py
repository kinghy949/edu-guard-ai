from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, require_admin
from app.api.v1._helpers import apply_updates, get_or_404
from app.core.security import hash_password
from app.models.user import User
from app.schemas.user import UserRead, UserUpdate

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("", response_model=list[UserRead])
def list_users(db: DbSession, skip: int = 0, limit: int = 100):
    return db.scalars(select(User).offset(skip).limit(limit)).all()


@router.get("/{user_id}", response_model=UserRead)
def get_user(user_id: int, db: DbSession):
    return get_or_404(db, User, user_id, "用户")


@router.patch("/{user_id}", response_model=UserRead)
def update_user(user_id: int, payload: UserUpdate, db: DbSession):
    user = get_or_404(db, User, user_id, "用户")
    apply_updates(user, payload.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(user)
    return user


@router.post("/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(user_id: int, new_password: str, db: DbSession):
    if len(new_password) < 6:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "密码至少 6 位")
    user = get_or_404(db, User, user_id, "用户")
    user.password_hash = hash_password(new_password)
    db.commit()


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, db: DbSession, current: CurrentUser):
    if user_id == current.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "不能删除自己")
    user = get_or_404(db, User, user_id, "用户")
    db.delete(user)
    db.commit()
