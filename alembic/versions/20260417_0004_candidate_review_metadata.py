"""add candidate type and review readiness"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision = "20260417_0004"
down_revision = "20260321_0003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:  # pragma: no cover - 迁移脚本
    op.add_column(
        "candidate_needs",
        sa.Column("candidate_type", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "candidate_needs",
        sa.Column("review_readiness", sa.Float(), nullable=True),
    )


def downgrade() -> None:  # pragma: no cover - 迁移脚本
    op.drop_column("candidate_needs", "review_readiness")
    op.drop_column("candidate_needs", "candidate_type")
