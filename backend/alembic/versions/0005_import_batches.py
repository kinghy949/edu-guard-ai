"""import batches + per-row change snapshots

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "import_batches",
        sa.Column("id", sa.Integer, primary_key=True),
        # students / courses / programs / grades
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("filename", sa.String(255), nullable=True),
        # completed / failed / rolled_back / dry_run
        sa.Column("status", sa.String(16), nullable=False, server_default="completed"),
        sa.Column("dry_run", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("total_rows", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("updated_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("errors", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("mapping", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("operator_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_import_batches_kind_created", "import_batches", ["kind", "created_at"])

    op.create_table(
        "import_batch_rows",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("batch_id", sa.Integer, sa.ForeignKey("import_batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("row_no", sa.Integer, nullable=True),
        # create / update
        sa.Column("op", sa.String(8), nullable=False),
        sa.Column("table_name", sa.String(32), nullable=False),
        sa.Column("record_pk", sa.Integer, nullable=True),
        sa.Column("before", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_index("ix_import_batch_rows_batch", "import_batch_rows", ["batch_id"])


def downgrade() -> None:
    op.drop_index("ix_import_batch_rows_batch", table_name="import_batch_rows")
    op.drop_table("import_batch_rows")
    op.drop_index("ix_import_batches_kind_created", table_name="import_batches")
    op.drop_table("import_batches")
