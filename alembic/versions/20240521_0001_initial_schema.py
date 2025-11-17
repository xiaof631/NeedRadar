from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20240521_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:  # pragma: no cover - 迁移脚本
    op.create_table(
        "rss_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False, unique=True),
        sa.Column("category", sa.String(length=100)),
        sa.Column("frequency", sa.Integer(), nullable=False, server_default="3600"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("last_fetched_at", sa.DateTime(timezone=True)),
        sa.Column("etag", sa.String(length=200)),
        sa.Column("last_modified", sa.String(length=200)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "fetch_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("rss_sources.id", ondelete="CASCADE")),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="success"),
        sa.Column("http_status", sa.Integer()),
        sa.Column("error_message", sa.Text()),
    )

    op.create_table(
        "raw_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("rss_sources.id", ondelete="CASCADE")),
        sa.Column("guid", sa.String(length=500), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("content_hash", sa.String(length=128), unique=True),
        sa.Column("summary", sa.Text()),
        sa.Column("content", sa.Text()),
        sa.Column("link", sa.String(length=500)),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("author", sa.String(length=200)),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_raw_entries_source_guid",
        "raw_entries",
        ["source_id", "guid"],
        unique=True,
    )

    op.create_table(
        "filter_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("keywords", sa.JSON(), nullable=False),
        sa.Column("patterns", sa.JSON(), nullable=False),
        sa.Column("min_score", sa.Float()),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "candidate_needs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "raw_entry_id",
            sa.Integer(),
            sa.ForeignKey("raw_entries.id", ondelete="CASCADE"),
        ),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.Column("problem_statement", sa.Text()),
        sa.Column("target_users", sa.Text()),
        sa.Column("value_proposition", sa.Text()),
        sa.Column("competition", sa.Text()),
        sa.Column("notes", sa.Text()),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending_review"),
        sa.Column("confidence", sa.Float()),
        sa.Column("rule_score", sa.Float()),
        sa.Column("synced_at", sa.DateTime(timezone=True)),
        sa.Column("sync_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "candidate_need_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("need_id", sa.Integer(), sa.ForeignKey("candidate_needs.id", ondelete="CASCADE")),
        sa.Column("from_status", sa.String(length=32)),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:  # pragma: no cover - 迁移脚本
    op.drop_table("candidate_need_logs")
    op.drop_table("candidate_needs")
    op.drop_table("filter_rules")
    op.drop_index("ix_raw_entries_source_guid", table_name="raw_entries")
    op.drop_table("raw_entries")
    op.drop_table("fetch_logs")
    op.drop_table("rss_sources")
