"""warning rules table + default global rule

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "warning_rules",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("scope_college", sa.String(64), nullable=True),
        sa.Column("scope_major", sa.String(64), nullable=True),
        sa.Column("severe_total_gap_ratio", sa.Float, nullable=False, server_default="0.5"),
        sa.Column("warn_total_gap_ratio", sa.Float, nullable=False, server_default="0.25"),
        sa.Column("severe_required_ratio", sa.Float, nullable=False, server_default="0.5"),
        sa.Column("warn_category_ratio", sa.Float, nullable=False, server_default="0.7"),
        sa.Column("required_category_keywords", postgresql.JSONB(astext_type=sa.Text()),
                  nullable=False, server_default=sa.text("""'["必修"]'::jsonb""")),
        sa.Column("stage_total_semesters", sa.Integer, nullable=False, server_default="8"),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("priority", sa.Integer, nullable=False, server_default="0"),
        sa.Column("updated_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    # 插入默认全局规则
    op.execute("""
        INSERT INTO warning_rules (name, severe_total_gap_ratio, warn_total_gap_ratio,
            severe_required_ratio, warn_category_ratio, required_category_keywords,
            stage_total_semesters, enabled, priority)
        VALUES ('全局默认', 0.5, 0.25, 0.5, 0.7, '["必修"]'::jsonb, 8, true, 0)
    """)


def downgrade() -> None:
    op.drop_table("warning_rules")
