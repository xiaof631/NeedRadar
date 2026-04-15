from __future__ import annotations

import os


os.environ.setdefault(
    "NEEDRADAR_DATABASE_URL",
    "sqlite+aiosqlite:///./data/test-multisource.db",
)
os.environ.setdefault(
    "NEEDRADAR_ALEMBIC_DATABASE_URL",
    "sqlite:///./data/test-multisource.db",
)
