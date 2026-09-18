"""add keyword seeds table"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision = "20260918_0006"
down_revision = "20260417_0005"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:  # pragma: no cover - 迁移脚本
    op.create_table(
        "keyword_seeds",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("phrase", sa.String(length=200), nullable=False),
        sa.Column("phrase_key", sa.String(length=200), nullable=False),
        sa.Column("pattern_kind", sa.String(length=32), nullable=False, server_default="convert_to"),
        sa.Column("occurrence_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="new"),
        sa.Column("search_volume", sa.Integer()),
        sa.Column("keyword_difficulty", sa.Integer()),
        sa.Column("cpc", sa.Float()),
        sa.Column("competition", sa.String(length=32)),
        sa.Column("validated_at", sa.DateTime(timezone=True)),
        sa.Column("validation_error", sa.Text()),
        sa.Column("opportunity_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("evidence", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_keyword_seeds_phrase_key", "keyword_seeds", ["phrase_key"], unique=True)


def downgrade() -> None:  # pragma: no cover - 迁移脚本
    op.drop_index("ix_keyword_seeds_phrase_key", table_name="keyword_seeds")
    op.drop_table("keyword_seeds")
