from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, require_admin
from app.core.config import settings
from app.core.password_policy import validate_password
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User, UserRole
from app.schemas.user import PasswordChange, TokenRead, UserCreate, UserRead

router = APIRouter()


def _check_password_or_400(password: str, *, username: str | None = None, student_no: str | None = None) -> None:
    errs = validate_password(password, username=username, student_no=student_no)
    if errs:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "；".join(errs))


@router.post("/register", response_model=UserRead, dependencies=[Depends(require_admin)])
def register(payload: UserCreate, db: DbSession):
    """注册新用户（仅管理员）。学生账户通常通过批量导入创建。"""
    exists = db.scalar(select(User).where(User.username == payload.username))
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "用户名已存在")
    if payload.role not in {r.value for r in UserRole}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "角色无效")
    _check_password_or_400(payload.password, username=payload.username)
    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=payload.role,
        email=payload.email,
        phone=payload.phone,
        display_name=payload.display_name,
        password_updated_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


_INVALID_CREDENTIAL = "用户名或密码错误"


@router.post("/login", response_model=TokenRead)
def login(db: DbSession, form: OAuth2PasswordRequestForm = Depends()):
    """登录：账户锁定优先返回 423，凭据错统一返回 401（不泄露账户存在性）。"""
    now = datetime.now(timezone.utc)
    user = db.scalar(select(User).where(User.username == form.username))

    if user and user.locked_until and user.locked_until > now:
        remaining = max(int((user.locked_until - now).total_seconds() // 60) + 1, 1)
        raise HTTPException(
            status.HTTP_423_LOCKED,
            f"账户已锁定，请 {remaining} 分钟后再试",
        )

    if not user or not verify_password(form.password, user.password_hash):
        if user is not None:
            user.failed_login_count = (user.failed_login_count or 0) + 1
            if user.failed_login_count >= settings.LOGIN_MAX_FAILED:
                user.locked_until = now + timedelta(minutes=settings.LOGIN_LOCK_MINUTES)
                user.failed_login_count = 0
            db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, _INVALID_CREDENTIAL)

    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "账户已停用")

    # 成功登录：清零失败计数与锁定
    user.failed_login_count = 0
    user.locked_until = None
    db.commit()
    token = create_access_token(user.id, extra={"role": user.role})
    return TokenRead(access_token=token, must_change_password=user.must_change_password)


@router.post("/change-password", response_model=UserRead)
def change_password(payload: PasswordChange, db: DbSession, user: CurrentUser):
    if not verify_password(payload.old_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "原密码错误")
    if payload.old_password == payload.new_password:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "新密码不能与原密码相同")
    _check_password_or_400(payload.new_password, username=user.username)
    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    user.password_updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return user


@router.get("/me", response_model=UserRead)
def me(user: CurrentUser):
    return user
