"""创建初始管理员账户。

用法:
    python -m scripts.create_admin <username> <password> [email]
"""
import sys

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.user import User, UserRole


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    username, password = sys.argv[1], sys.argv[2]
    email = sys.argv[3] if len(sys.argv) >= 4 else None

    with SessionLocal() as db:
        if db.scalar(select(User).where(User.username == username)):
            print(f"用户已存在: {username}")
            return 1
        user = User(
            username=username,
            password_hash=hash_password(password),
            role=UserRole.ADMIN,
            email=email,
            display_name="管理员",
        )
        db.add(user)
        db.commit()
        print(f"✅ 管理员已创建: id={user.id} username={user.username}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
