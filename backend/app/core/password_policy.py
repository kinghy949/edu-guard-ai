"""密码策略：长度、字符种类、避免与身份关联。"""
from __future__ import annotations

MIN_LENGTH = 8
MAX_LENGTH = 128


def validate_password(password: str, *, username: str | None = None, student_no: str | None = None) -> list[str]:
    """返回错误信息列表；为空则视为合规。"""
    errors: list[str] = []
    if password is None:
        return ["密码不能为空"]
    if len(password) < MIN_LENGTH:
        errors.append(f"密码长度至少 {MIN_LENGTH} 位")
    if len(password) > MAX_LENGTH:
        errors.append(f"密码长度不得超过 {MAX_LENGTH} 位")
    has_alpha = any(c.isalpha() for c in password)
    has_digit = any(c.isdigit() for c in password)
    if not (has_alpha and has_digit):
        errors.append("密码必须同时包含字母和数字")
    lowered = password.lower()
    if username and lowered == username.lower():
        errors.append("密码不能与用户名相同")
    if student_no and lowered == student_no.lower():
        errors.append("密码不能与学号相同")
    return errors


def ensure_password_valid(password: str, *, username: str | None = None, student_no: str | None = None) -> None:
    """校验失败抛 ValueError，消息为分号拼接的错误清单。"""
    errs = validate_password(password, username=username, student_no=student_no)
    if errs:
        raise ValueError("；".join(errs))
