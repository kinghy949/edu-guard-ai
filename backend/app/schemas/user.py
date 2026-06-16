from pydantic import EmailStr, Field

from app.schemas._base import ORMBase, TimestampRead


class UserCreate(ORMBase):
    username: str = Field(min_length=3, max_length=64)
    # 复杂度由 password_policy.validate_password 在 service 层强制校验
    password: str = Field(min_length=8, max_length=128)
    role: str = "student"
    email: EmailStr | None = None
    phone: str | None = None
    display_name: str | None = None


class PasswordChange(ORMBase):
    old_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class UserUpdate(ORMBase):
    email: EmailStr | None = None
    phone: str | None = None
    display_name: str | None = None
    is_active: bool | None = None
    role: str | None = None


class UserRead(TimestampRead):
    username: str
    role: str
    email: str | None
    phone: str | None
    display_name: str | None
    is_active: bool
    must_change_password: bool = False


class UserLogin(ORMBase):
    username: str
    password: str


class TokenRead(ORMBase):
    access_token: str
    token_type: str = "bearer"
    # 前端据此在登录后强制跳转修改密码页
    must_change_password: bool = False
