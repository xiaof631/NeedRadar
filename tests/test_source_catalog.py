from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

from app.core import config as config_module
from app.models import SourceStatus, SourceType
from app.services import rss_sources, source_catalog


@pytest.fixture(autouse=True)
def _reset_db() -> None:
    os.environ["NEEDRADAR_GITHUB_ACCESS_TOKEN"] = ""
    config_module.get_settings.cache_clear()
    config_module.settings = config_module.get_settings(
        database_url=config_module.settings.database_url,
        alembic_database_url=config_module.settings.alembic_database_url,
        github_access_token="",
    )
    rss_sources.reset_storage()
    yield
    rss_sources.reset_storage()
    config_module.get_settings.cache_clear()
    config_module.settings = config_module.get_settings(
        database_url=config_module.settings.database_url,
        alembic_database_url=config_module.settings.alembic_database_url,
        github_access_token="",
    )


def test_seed_github_public_expanded_catalog_creates_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(source_catalog, "get_settings", lambda: SimpleNamespace(github_access_token=None))
    created, skipped = source_catalog.seed_catalog("github-public-expanded")

    assert skipped == []
    assert len(created) >= 10
    assert all(source.source_type == SourceType.GITHUB_ISSUES for source in created)
    assert all(source.status == SourceStatus.PAUSED for source in created)

    total, items = rss_sources.list_sources(source_type=SourceType.GITHUB_ISSUES)
    assert total == len(created)
    names = {item.name for item in items}
    assert "Vercel AI SDK Issues" in names
    assert "n8n Issues" in names
    assert "LangChain Issues" in names


def test_seed_catalog_skips_existing_urls() -> None:
    rss_sources.create_source(
        {
            "name": "Supabase Issues",
            "url": "https://api.github.com/repos/supabase/supabase/issues",
            "category": "developer-tools",
            "frequency": 3600,
            "source_type": SourceType.GITHUB_ISSUES,
            "config": {"item_limit": 30, "state": "open"},
        }
    )

    created, skipped = source_catalog.seed_catalog("github-public-expanded")

    assert "https://api.github.com/repos/supabase/supabase/issues" in skipped
    assert len(created) + len(skipped) == len(source_catalog.get_catalog("github-public-expanded"))


def test_seed_catalog_activates_when_token_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    os.environ["NEEDRADAR_GITHUB_ACCESS_TOKEN"] = "token"
    config_module.get_settings.cache_clear()
    config_module.settings = config_module.get_settings(
        database_url=config_module.settings.database_url,
        alembic_database_url=config_module.settings.alembic_database_url,
        github_access_token="token",
    )
    monkeypatch.setattr(source_catalog, "get_settings", lambda: SimpleNamespace(github_access_token="token"))

    created, skipped = source_catalog.seed_catalog("github-public-expanded")

    assert skipped == []
    assert created
    assert all(source.status == SourceStatus.ACTIVE for source in created)


def test_unknown_catalog_raises() -> None:
    with pytest.raises(source_catalog.SourceCatalogNotFoundError):
        source_catalog.get_catalog("unknown-profile")


def test_seed_marketplace_catalog_pauses_freelancer_source_by_default() -> None:
    created, skipped = source_catalog.seed_catalog("marketplace-public-baseline")

    assert skipped == []
    assert len(created) == 7

    by_name = {source.name: source for source in created}
    assert by_name["Freelancer Web Development Jobs"].status == SourceStatus.PAUSED
    assert by_name["软件项目交易网最新外包项目"].status == SourceStatus.ACTIVE
    assert by_name["PeoplePerHour Technology Projects"].status == SourceStatus.ACTIVE
    assert by_name["We Work Remotely Programming Contracts"].status == SourceStatus.ACTIVE
    assert by_name["Remotive Software Contracts"].status == SourceStatus.ACTIVE
    assert by_name["Contra Featured Remote Jobs"].status == SourceStatus.PAUSED
    assert by_name["猪八戒需求大厅精选任务"].status == SourceStatus.ACTIVE
    assert "软件" in by_name["软件项目交易网最新外包项目"].config["include_keywords"]
    assert "脚本" in by_name["软件项目交易网最新外包项目"].config["exclude_keywords"]
    assert "qt" in by_name["软件项目交易网最新外包项目"].config["include_keywords"]
    assert "penetration testing" in by_name["PeoplePerHour Technology Projects"].config["exclude_keywords"]
    assert "talent community" in by_name["We Work Remotely Programming Contracts"].config["exclude_keywords"]
    assert "contract" in by_name["Remotive Software Contracts"].config["job_types"]
