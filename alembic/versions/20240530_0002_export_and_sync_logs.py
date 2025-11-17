"""add export jobs and sync logs"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "20240530_0002"
down_revision = "20240521_0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:  # pragma: no cover - 迁移脚本
    op.create_table(
        "downstream_sync_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("need_id", sa.Integer(), sa.ForeignKey("candidate_needs.id", ondelete="CASCADE")),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("message", sa.Text()),
        sa.Column("details", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_downstream_sync_logs_need_id",
        "downstream_sync_logs",
        ["need_id"],
    )

    op.create_table(
        "export_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_type", sa.String(length=64), nullable=False),
        sa.Column("format", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("filters", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("record_count", sa.Integer()),
        sa.Column("file_path", sa.String(length=500)),
        sa.Column("error_message", sa.Text()),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:  # pragma: no cover - 迁移脚本
    op.drop_table("export_jobs")
    op.drop_index("ix_downstream_sync_logs_need_id", table_name="downstream_sync_logs")
    op.drop_table("downstream_sync_logs")
