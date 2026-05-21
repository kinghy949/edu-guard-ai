"""首次部署引导：

容器启动时执行（compose command 中 `alembic upgrade head` 之后调用）。
- 始终幂等：表已建好且数据已就绪时是 no-op
- 步骤 1：若无任何用户，创建默认管理员
  - 用户名/密码/邮箱可由环境变量覆盖：
      BOOTSTRAP_ADMIN_USERNAME（默认 admin）
      BOOTSTRAP_ADMIN_PASSWORD（默认 admin123；首次部署务必通过 .env 覆盖）
      BOOTSTRAP_ADMIN_EMAIL（可选）
- 步骤 2：若 SEED_DEMO=true 且数据库内无任何培养方案，导入演示数据
  （直接调用 scripts.seed_demo 的 main()）

通过环境变量控制，避免生产部署污染。
"""
from __future__ import annotations

import os

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.program import Program
from app.models.user import User, UserRole


def _truthy(v: str | None) -> bool:
    return (v or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def ensure_admin() -> None:
    username = os.getenv("BOOTSTRAP_ADMIN_USERNAME", "admin").strip()
    password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "admin123")
    email = os.getenv("BOOTSTRAP_ADMIN_EMAIL") or None

    with SessionLocal() as db:
        if db.scalar(select(User).limit(1)) is not None:
            return
        db.add(User(
            username=username,
            password_hash=hash_password(password),
            role=UserRole.ADMIN,
            display_name="管理员",
            email=email,
        ))
        db.commit()
        print(f"[bootstrap] 创建默认管理员: {username}")


def maybe_seed_demo() -> None:
    if not _truthy(os.getenv("SEED_DEMO")):
        print("[bootstrap] SEED_DEMO 未启用，跳过演示数据")
        return
    with SessionLocal() as db:
        if db.scalar(select(Program).limit(1)) is not None:
            print("[bootstrap] 已存在培养方案，跳过演示数据")
            return
    print("[bootstrap] 开始导入演示数据 ...")
    # 延迟导入，避免无 SEED_DEMO 时也加载大文件
    from scripts.seed_demo import main as seed_main
    seed_main()


def main() -> int:
    ensure_admin()
    maybe_seed_demo()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
