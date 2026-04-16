from __future__ import annotations

import os

import pytest

from app.core import config as config_module
from app.models import SourceStatus, SourceType
from app.services import rss_sources, source_catalog


@pytest.fixture(autouse=True)
def _reset_db() -> None:
    os.environ.pop("NEEDRADAR_GITHUB_ACCESS_TOKEN", None)
    config_module.get_settings.cache_clear()
    rss_sources.reset_storage()
    yield
    rss_sources.reset_storage()
    config_module.get_settings.cache_clear()


def test_seed_github_public_expanded_catalog_creates_sources() -> None:
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


def test_seed_catalog_activates_when_token_configured() -> None:
    os.environ["NEEDRADAR_GITHUB_ACCESS_TOKEN"] = "token"
    config_module.get_settings.cache_clear()

    created, skipped = source_catalog.seed_catalog("github-public-expanded")

    assert skipped == []
    assert created
    assert all(source.status == SourceStatus.ACTIVE for source in created)


def test_unknown_catalog_raises() -> None:
    with pytest.raises(source_catalog.SourceCatalogNotFoundError):
        source_catalog.get_catalog("unknown-profile")
