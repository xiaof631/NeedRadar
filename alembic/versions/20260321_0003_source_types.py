"""add source type and config to rss sources"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "20260321_0003"
down_revision = "20240530_0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:  # pragma: no cover - 迁移脚本
    op.add_column(
        "rss_sources",
        sa.Column("source_type", sa.String(length=32), nullable=False, server_default="rss"),
    )
    op.add_column(
        "rss_sources",
        sa.Column("config", sa.JSON(), nullable=False, server_default="{}"),
    )


def downgrade() -> None:  # pragma: no cover - 迁移脚本
    op.drop_column("rss_sources", "config")
    op.drop_column("rss_sources", "source_type")
