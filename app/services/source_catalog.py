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

_MARKETPLACE_PUBLIC_BASELINE: tuple[CatalogEntry, ...] = (
    {
        "name": "软件项目交易网最新外包项目",
        "url": "https://www.sxsoft.com/",
        "category": "freelance-marketplace",
        "frequency": 3600,
        "source_type": SourceType.FREELANCE_MARKETPLACE,
        "config": {
            "adapter": "sxsoft_latest",
            "item_limit": 12,
            "topic": "software-development",
            "include_keywords": "开发,搭建,定制,实现,对接,小程序,网站,系统,平台,插件,程序,前端,后端,后台,数据库,进销存,erp,crm,saas,web,软件,app,android,ios,管理软件,qt,java,mysql",
            "exclude_keywords": "logo,海报,文案,命名,广告,创意设计,包装设计,活动,征集,大赛,推广,运营,设计,ui,优化,协议,脚本,代付",
        },
    },
    {
        "name": "Freelancer Web Development Jobs",
        "url": "https://www.freelancer.com/jobs/web-development/",
        "category": "freelance-marketplace",
        "frequency": 5400,
        "source_type": SourceType.FREELANCE_MARKETPLACE,
        "status": SourceStatus.PAUSED,
        "config": {
            "adapter": "freelancer_jobs",
            "item_limit": 12,
            "topic": "web-development",
        },
    },
    {
        "name": "PeoplePerHour Technology Projects",
        "url": "https://www.peopleperhour.com/freelance-jobs/technology-programming",
        "category": "freelance-marketplace",
        "frequency": 5400,
        "source_type": SourceType.FREELANCE_MARKETPLACE,
        "config": {
            "adapter": "peopleperhour_technology",
            "item_limit": 15,
            "topic": "software-contracting",
            "include_keywords": "developer,development,software,website,web,frontend,backend,full-stack,full stack,react,next.js,python,django,api,cms,erp,crm,database,automation,android,ios,wordpress,app",
            "exclude_keywords": "logo,branding,illustration,copywriting,video,marketing,social media,seo only,design only,help with my,penetration testing,art catalog,catalogit,airtable,excel,spreadsheet",
        },
    },
    {
        "name": "We Work Remotely Programming Contracts",
        "url": "https://weworkremotely.com/categories/remote-programming-jobs.rss",
        "category": "freelance-marketplace",
        "frequency": 7200,
        "source_type": SourceType.FREELANCE_MARKETPLACE,
        "config": {
            "adapter": "wwr_programming_rss",
            "item_limit": 15,
            "topic": "software-contracting",
            "include_keywords": "contract,contract-based,freelance,project-based,/hr,hourly",
            "exclude_keywords": "intern,marketing,sales,designer,design,talent community,talent pool",
        },
    },
    {
        "name": "Remotive Software Contracts",
        "url": "https://remotive.com/api/remote-jobs?category=software-dev&limit=40",
        "category": "freelance-marketplace",
        "frequency": 21600,
        "source_type": SourceType.FREELANCE_MARKETPLACE,
        "config": {
            "adapter": "remotive_api",
            "item_limit": 15,
            "topic": "software-contracting",
            "job_types": "contract,freelance",
            "include_keywords": "contract,freelance,consultant,developer,engineer,full stack,full-stack,frontend,backend,react,next.js,python,django,api,saas,wordpress,mobile,android,ios",
            "exclude_keywords": "intern,designer,design,sales,marketing,talent pool,talent community,recruiter,human resources",
        },
    },
    {
        "name": "Jobicy Contract Developer Roles",
        "url": "https://jobicy.com/api/v2/remote-jobs?count=50&tag=python%20developer",
        "category": "freelance-marketplace",
        "frequency": 21600,
        "source_type": SourceType.FREELANCE_MARKETPLACE,
        "config": {
            "adapter": "jobicy_api",
            "item_limit": 12,
            "topic": "software-contracting",
            "exclude_keywords": "data scientist,data science,analyst,physics,chemistry,civil engineer,mathematics",
        },
    },
    {
        "name": "Contra Featured Remote Jobs",
        "url": "https://contra.com/featured-jobs/freelance-creative-jobs",
        "category": "freelance-marketplace",
        "frequency": 7200,
        "source_type": SourceType.FREELANCE_MARKETPLACE,
        "status": SourceStatus.PAUSED,
        "config": {
            "adapter": "contra_featured_jobs",
            "item_limit": 10,
            "topic": "creative-and-web",
        },
    },
    {
        "name": "猪八戒需求大厅精选任务",
        "url": "https://task.zbj.com/index/",
        "category": "freelance-marketplace",
        "frequency": 7200,
        "source_type": SourceType.FREELANCE_MARKETPLACE,
        "config": {
            "adapter": "zbj_hall_scroll",
            "item_limit": 15,
            "topic": "software-development",
            "include_keywords": "开发,搭建,定制,实现,对接,小程序,网站,系统,平台,插件,程序,前端,后端,数据库,进销存,erp,crm,saas,web,软件,app,android,ios,管理软件",
            "exclude_keywords": "logo,海报,文案,命名,台标,梳子,造句,展区设计,外观设计,广告,节目方案,创意设计,包装设计,活动,征集,大赛,推广,运营,设计,ui,优化",
        },
    },
)

_CATALOGS: dict[str, tuple[CatalogEntry, ...]] = {
    "github-public-expanded": _GITHUB_PUBLIC_EXPANDED,
    "marketplace-public-baseline": _MARKETPLACE_PUBLIC_BASELINE,
}

_CATALOG_DESCRIPTIONS: dict[str, str] = {
    "github-public-expanded": "长期扩源用的 GitHub public repo issue 源目录，覆盖 AI、开发工具、自动化与排期场景。",
    "marketplace-public-baseline": "公开外包/自由职业项目线索目录，优先接入可公开浏览的真实项目列表。",
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
