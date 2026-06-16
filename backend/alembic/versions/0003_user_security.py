"""user security: must_change_password / password_updated_at / login lock

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "must_change_password",
            sa.Boolean,
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "users",
        sa.Column("password_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "failed_login_count",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "users",
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_login_count")
    op.drop_column("users", "password_updated_at")
    op.drop_column("users", "must_change_password")
