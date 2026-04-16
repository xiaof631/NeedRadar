from __future__ import annotations

import os

from app.core import config as config_module


os.environ["NEEDRADAR_DATABASE_URL"] = "sqlite+aiosqlite:///./data/test-multisource.db"
os.environ["NEEDRADAR_ALEMBIC_DATABASE_URL"] = "sqlite:///./data/test-multisource.db"
config_module.get_settings.cache_clear()
config_module.settings = config_module.get_settings()
