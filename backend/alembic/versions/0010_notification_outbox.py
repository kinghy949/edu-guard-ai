"""notifications outbox columns

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("notifications", sa.Column("subject", sa.String(255), nullable=True))
    op.add_column("notifications", sa.Column("content", sa.Text, nullable=True))
    op.add_column("notifications", sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"))
    op.add_column("notifications", sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True))
    # read_at 供 T4.2 消息中心使用，提前一起加
    op.add_column("notifications", sa.Column("read_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_notifications_status_next", "notifications", ["status", "next_attempt_at"])


def downgrade() -> None:
    op.drop_index("ix_notifications_status_next", table_name="notifications")
    op.drop_column("notifications", "read_at")
    op.drop_column("notifications", "next_attempt_at")
    op.drop_column("notifications", "retry_count")
    op.drop_column("notifications", "content")
    op.drop_column("notifications", "subject")
