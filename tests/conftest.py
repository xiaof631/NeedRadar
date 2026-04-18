from __future__ import annotations

import os
import tempfile
from pathlib import Path

from app.core import config as config_module
from app.db import session as db_session

TEST_DB_DIR = Path(tempfile.mkdtemp(prefix="needradar-test-db-"))
TEST_DB_PATH = TEST_DB_DIR / "test-multisource.db"
TEST_DATABASE_URL = f"sqlite+aiosqlite:///{TEST_DB_PATH}"
TEST_ALEMBIC_DATABASE_URL = f"sqlite:///{TEST_DB_PATH}"

os.environ["NEEDRADAR_DATABASE_URL"] = TEST_DATABASE_URL
os.environ["NEEDRADAR_ALEMBIC_DATABASE_URL"] = TEST_ALEMBIC_DATABASE_URL
config_module.get_settings.cache_clear()
config_module.settings = config_module.get_settings(
    database_url=TEST_DATABASE_URL,
    alembic_database_url=TEST_ALEMBIC_DATABASE_URL,
)


def _get_test_settings():
    return config_module.settings


db_session.get_settings = _get_test_settings
db_session._sync_engine = None
db_session._session_factory = None
db_session._async_engine = None
db_session._async_session_factory = None
