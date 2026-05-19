from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, require_admin
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User, UserRole
from app.schemas.user import TokenRead, UserCreate, UserRead

router = APIRouter()


@router.post("/register", response_model=UserRead, dependencies=[Depends(require_admin)])
def register(payload: UserCreate, db: DbSession):
    """注册新用户（仅管理员）。学生账户通常通过批量导入创建。"""
    exists = db.scalar(select(User).where(User.username == payload.username))
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "用户名已存在")
    if payload.role not in {r.value for r in UserRole}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "角色无效")
    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=payload.role,
        email=payload.email,
        phone=payload.phone,
        display_name=payload.display_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenRead)
def login(db: DbSession, form: OAuth2PasswordRequestForm = Depends()):
    user = db.scalar(select(User).where(User.username == form.username))
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "账户已停用")
    token = create_access_token(user.id, extra={"role": user.role})
    return TokenRead(access_token=token)


@router.get("/me", response_model=UserRead)
def me(user: CurrentUser):
    return user
