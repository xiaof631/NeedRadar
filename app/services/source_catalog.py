"""预置数据源目录。"""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.models import RssSource, SourceStatus, SourceType
from app.services import rss_sources

CatalogEntry = dict[str, Any]

_GITHUB_PUBLIC_EXPANDED: tuple[CatalogEntry, ...] = (
    {
        "name": "Supabase Issues",
        "url": "https://api.github.com/repos/supabase/supabase/issues",
        "category": "developer-tools",
        "frequency": 3600,
        "source_type": SourceType.GITHUB_ISSUES,
        "config": {"item_limit": 30, "state": "open", "sort": "updated", "direction": "desc"},
    },
    {
        "name": "Supabase Realtime Issues",
        "url": "https://api.github.com/repos/supabase/realtime/issues",
        "category": "developer-tools",
        "frequency": 3600,
        "source_type": SourceType.GITHUB_ISSUES,
        "config": {"item_limit": 25, "state": "open", "sort": "updated", "direction": "desc"},
    },
    {
        "name": "Next.js Issues",
        "url": "https://api.github.com/repos/vercel/next.js/issues",
        "category": "developer-tools",
        "frequency": 3600,
        "source_type": SourceType.GITHUB_ISSUES,
        "config": {"item_limit": 30, "state": "open", "sort": "updated", "direction": "desc"},
    },
    {
        "name": "Vercel AI SDK Issues",
        "url": "https://api.github.com/repos/vercel/ai/issues",
        "category": "ai-tools",
        "frequency": 3600,
        "source_type": SourceType.GITHUB_ISSUES,
        "config": {"item_limit": 30, "state": "open", "sort": "updated", "direction": "desc"},
    },
    {
        "name": "Turborepo Issues",
        "url": "https://api.github.com/repos/vercel/turborepo/issues",
        "category": "developer-tools",
        "frequency": 5400,
        "source_type": SourceType.GITHUB_ISSUES,
        "config": {"item_limit": 25, "state": "open", "sort": "updated", "direction": "desc"},
    },
    {
        "name": "OpenAI Python Issues",
        "url": "https://api.github.com/repos/openai/openai-python/issues",
        "category": "ai-tools",
        "frequency": 3600,
        "source_type": SourceType.GITHUB_ISSUES,
        "config": {"item_limit": 30, "state": "open", "sort": "updated", "direction": "desc"},
    },
    {
        "name": "LangChain Issues",
        "url": "https://api.github.com/repos/langchain-ai/langchain/issues",
        "category": "ai-tools",
        "frequency": 3600,
        "source_type": SourceType.GITHUB_ISSUES,
        "config": {"item_limit": 30, "state": "open", "sort": "updated", "direction": "desc"},
    },
    {
        "name": "LangGraph Issues",
        "url": "https://api.github.com/repos/langchain-ai/langgraph/issues",
        "category": "ai-tools",
        "frequency": 3600,
        "source_type": SourceType.GITHUB_ISSUES,
        "config": {"item_limit": 25, "state": "open", "sort": "updated", "direction": "desc"},
    },
    {
        "name": "n8n Issues",
        "url": "https://api.github.com/repos/n8n-io/n8n/issues",
        "category": "workflow-automation",
        "frequency": 3600,
        "source_type": SourceType.GITHUB_ISSUES,
        "config": {"item_limit": 30, "state": "open", "sort": "updated", "direction": "desc"},
    },
    {
        "name": "Activepieces Issues",
        "url": "https://api.github.com/repos/activepieces/activepieces/issues",
        "category": "workflow-automation",
        "frequency": 3600,
        "source_type": SourceType.GITHUB_ISSUES,
        "config": {"item_limit": 25, "state": "open", "sort": "updated", "direction": "desc"},
    },
    {
        "name": "Cal.com Issues",
        "url": "https://api.github.com/repos/calcom/cal.com/issues",
        "category": "scheduling",
        "frequency": 5400,
        "source_type": SourceType.GITHUB_ISSUES,
        "config": {"item_limit": 25, "state": "open", "sort": "updated", "direction": "desc"},
    },
)

_CATALOGS: dict[str, tuple[CatalogEntry, ...]] = {
    "github-public-expanded": _GITHUB_PUBLIC_EXPANDED,
}

_CATALOG_DESCRIPTIONS: dict[str, str] = {
    "github-public-expanded": "长期扩源用的 GitHub public repo issue 源目录，覆盖 AI、开发工具、自动化与排期场景。",
}


class SourceCatalogNotFoundError(Exception):
    """目录不存在。"""


def list_catalogs() -> dict[str, str]:
    """列出可用目录。"""

    return dict(_CATALOG_DESCRIPTIONS)


def get_catalog(profile: str) -> tuple[CatalogEntry, ...]:
    """读取指定目录。"""

    catalog = _CATALOGS.get(profile)
    if catalog is None:
        raise SourceCatalogNotFoundError(profile)
    return tuple(_clone_entry(item) for item in catalog)


def seed_catalog(
    profile: str,
    *,
    status: SourceStatus | None = None,
) -> tuple[list[RssSource], list[str]]:
    """导入指定目录，返回新增源与跳过的 URL。"""

    created: list[RssSource] = []
    skipped: list[str] = []
    default_status = status or _default_status_for_profile(profile)
    for item in get_catalog(profile):
        payload = _clone_entry(item)
        if default_status is not None:
            payload["status"] = default_status
        try:
            created.append(rss_sources.create_source(payload))
        except rss_sources.RssSourceAlreadyExistsError:
            skipped.append(str(payload["url"]))
    return created, skipped


def _clone_entry(item: CatalogEntry) -> CatalogEntry:
    payload = dict(item)
    payload["config"] = dict(item.get("config", {}))
    return payload


def _default_status_for_profile(profile: str) -> SourceStatus | None:
    if not profile.startswith("github-"):
        return None
    settings = get_settings()
    if settings.github_access_token:
        return SourceStatus.ACTIVE
    return SourceStatus.PAUSED
