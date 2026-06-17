"""student_progress_snapshots

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "student_progress_snapshots",
        sa.Column("student_id", sa.Integer,
                  sa.ForeignKey("students.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("total_required", sa.Numeric(6, 1), nullable=False, server_default="0"),
        sa.Column("total_earned", sa.Numeric(6, 1), nullable=False, server_default="0"),
        sa.Column("total_in_progress", sa.Numeric(6, 1), nullable=False, server_default="0"),
        sa.Column("total_gap", sa.Numeric(6, 1), nullable=False, server_default="0"),
        sa.Column("completion_ratio", sa.Float, nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("computed_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("student_progress_snapshots")
