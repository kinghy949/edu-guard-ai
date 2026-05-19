"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("username", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(16), nullable=False, server_default="student"),
        sa.Column("email", sa.String(128)),
        sa.Column("phone", sa.String(32)),
        sa.Column("display_name", sa.String(64)),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "programs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("college", sa.String(64), nullable=False),
        sa.Column("major", sa.String(64), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("total_credits_required", sa.Numeric(6, 2), nullable=False),
        sa.Column("note", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "students",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), unique=True),
        sa.Column("student_no", sa.String(32), nullable=False, unique=True, index=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("gender", sa.String(8)),
        sa.Column("enroll_year", sa.Integer, nullable=False),
        sa.Column("college", sa.String(64), nullable=False),
        sa.Column("major", sa.String(64), nullable=False),
        sa.Column("class_name", sa.String(64)),
        sa.Column("program_id", sa.Integer, sa.ForeignKey("programs.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "credit_buckets",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("program_id", sa.Integer, sa.ForeignKey("programs.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("credits_required", sa.Numeric(6, 2), nullable=False),
        sa.Column("note", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("program_id", "category", name="uq_program_category"),
    )

    op.create_table(
        "courses",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("credits", sa.Numeric(4, 2), nullable=False),
        sa.Column("hours", sa.Integer),
        sa.Column("category_default", sa.String(32)),
        sa.Column("description", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "program_courses",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("program_id", sa.Integer, sa.ForeignKey("programs.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("course_id", sa.Integer, sa.ForeignKey("courses.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("bucket_id", sa.Integer, sa.ForeignKey("credit_buckets.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("is_required", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("semester_suggested", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("program_id", "course_id", name="uq_program_course"),
    )

    op.create_table(
        "grades",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("student_id", sa.Integer, sa.ForeignKey("students.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("course_id", sa.Integer, sa.ForeignKey("courses.id", ondelete="RESTRICT"), index=True, nullable=False),
        sa.Column("semester", sa.String(16), nullable=False),
        sa.Column("credits_earned", sa.Numeric(4, 2), nullable=False, server_default="0"),
        sa.Column("score", sa.Numeric(5, 2)),
        sa.Column("status", sa.String(16), nullable=False, server_default="in_progress"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("student_id", "course_id", "semester", name="uq_student_course_semester"),
    )

    op.create_table(
        "warnings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("student_id", sa.Integer, sa.ForeignKey("students.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("level", sa.String(16), nullable=False),
        sa.Column("semester", sa.String(16), nullable=False),
        sa.Column("summary", sa.String(255), nullable=False),
        sa.Column("detail", postgresql.JSONB),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("resolver_note", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("warning_id", sa.Integer, sa.ForeignKey("warnings.id", ondelete="SET NULL"), index=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), index=True),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("target", sa.String(255), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("error", sa.Text),
        sa.Column("payload", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "notification_configs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("channel", sa.String(16), nullable=False, unique=True),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("config", postgresql.JSONB),
        sa.Column("updated_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("title", sa.String(128)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("session_id", sa.Integer, sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    for t in [
        "chat_messages",
        "chat_sessions",
        "notification_configs",
        "notifications",
        "warnings",
        "grades",
        "program_courses",
        "courses",
        "credit_buckets",
        "students",
        "programs",
        "users",
    ]:
        op.drop_table(t)
