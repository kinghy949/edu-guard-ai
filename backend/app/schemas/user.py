from pydantic import EmailStr, Field

from app.schemas._base import ORMBase, TimestampRead


class UserCreate(ORMBase):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    role: str = "student"
    email: EmailStr | None = None
    phone: str | None = None
    display_name: str | None = None


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


class UserLogin(ORMBase):
    username: str
    password: str


class TokenRead(ORMBase):
    access_token: str
    token_type: str = "bearer"
