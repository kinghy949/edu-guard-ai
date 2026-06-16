"""warnings status/assignee + warning_actions table

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "warnings",
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
    )
    op.add_column(
        "warnings",
        sa.Column(
            "assignee_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_warnings_status_level", "warnings", ["status", "level"])
    # 存量数据迁移：已有 resolved_at 的视为已解决
    op.execute("UPDATE warnings SET status = 'resolved' WHERE resolved_at IS NOT NULL")

    op.create_table(
        "warning_actions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "warning_id", sa.Integer,
            sa.ForeignKey("warnings.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "user_id", sa.Integer,
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_warning_actions_warning", "warning_actions", ["warning_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_warning_actions_warning", table_name="warning_actions")
    op.drop_table("warning_actions")
    op.drop_index("ix_warnings_status_level", table_name="warnings")
    op.drop_column("warnings", "assignee_id")
    op.drop_column("warnings", "status")
