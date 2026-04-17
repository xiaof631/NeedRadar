from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.main import app
from app.models import SourceType
from app.services import marketplace_leads, raw_entries, rss_sources
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _reset_db() -> None:
    rss_sources.reset_storage()
    yield
    rss_sources.reset_storage()


@pytest.fixture()
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def test_list_marketplace_leads_returns_structured_fields(client: TestClient) -> None:
    source = rss_sources.create_source(
        {
            "name": "Freelancer Web Development Jobs",
            "url": "https://www.freelancer.com/jobs/web-development/",
            "frequency": 3600,
            "source_type": SourceType.FREELANCE_MARKETPLACE,
            "config": {"adapter": "freelancer_jobs"},
        }
    )
    raw_entries.create_entry(
        {
            "source_id": source.id,
            "guid": "lead-1",
            "title": "Build a responsive booking portal",
            "summary": "Build a responsive booking portal | $500 Avg Bid | 6 days left",
            "content": "Need a modern booking system with admin dashboard.",
            "link": "https://www.freelancer.com/projects/example",
            "published_at": datetime(2026, 4, 17, 9, 0, tzinfo=UTC),
            "tags": ["marketplace", "freelancer", "web-development"],
            "metadata": {
                "platform": "Freelancer",
                "category": "web-development",
                "budget": "$500 Avg Bid",
                "timeline": "6 days left",
                "engagement": "fixed-price",
                "skills": ["Web Development", "Laravel"],
            },
        }
    )

    response = client.get("/api/v1/marketplace-leads/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    item = payload["items"][0]
    assert item["platform"] == "Freelancer"
    assert item["source_name"] == "Freelancer Web Development Jobs"
    assert item["budget"] == "$500 Avg Bid"
    assert item["timeline"] == "6 days left"
    assert item["skills"] == ["Web Development", "Laravel"]
    assert item["lead_tier"] == "high_purity"


def test_list_marketplace_leads_diversifies_sources() -> None:
    sxsoft = rss_sources.create_source(
        {
            "name": "软件项目交易网最新外包项目",
            "url": "https://www.sxsoft.com/",
            "frequency": 3600,
            "source_type": SourceType.FREELANCE_MARKETPLACE,
            "config": {"adapter": "sxsoft_latest"},
        }
    )
    zbj = rss_sources.create_source(
        {
            "name": "猪八戒需求大厅精选任务",
            "url": "https://task.zbj.com/index/",
            "frequency": 3600,
            "source_type": SourceType.FREELANCE_MARKETPLACE,
            "config": {"adapter": "zbj_hall_scroll"},
        }
    )
    raw_entries.create_entry(
        {
            "source_id": zbj.id,
            "guid": "zbj-1",
            "title": "小程序商城开发",
            "summary": "小程序商城开发 | ￥5000 | 10天完成",
            "content": "12个服务商参与",
            "link": "https://task.zbj.com/1/",
            "tags": ["marketplace", "zbj"],
            "metadata": {"platform": "猪八戒", "budget": "￥5000", "timeline": "10天完成", "skills": []},
        }
    )
    raw_entries.create_entry(
        {
            "source_id": zbj.id,
            "guid": "zbj-2",
            "title": "ERP 系统开发",
            "summary": "ERP 系统开发 | ￥10000 | 20天完成",
            "content": "8个服务商参与",
            "link": "https://task.zbj.com/2/",
            "tags": ["marketplace", "zbj"],
            "metadata": {"platform": "猪八戒", "budget": "￥10000", "timeline": "20天完成", "skills": []},
        }
    )
    raw_entries.create_entry(
        {
            "source_id": sxsoft.id,
            "guid": "sx-1",
            "title": "CRM 后台开发",
            "summary": "CRM 后台开发 | 5千~1万 | 15天",
            "content": None,
            "link": "https://www.sxsoft.com/project/1",
            "tags": ["marketplace", "sxsoft"],
            "metadata": {"platform": "软件项目交易网", "budget": "5千~1万", "timeline": "15天", "skills": []},
        }
    )

    total, items, tier_breakdown = marketplace_leads.list_leads(limit=3)

    assert total == 3
    source_ids = [item.source_id for item in items]
    assert source_ids == [sxsoft.id, zbj.id, zbj.id]
    assert tier_breakdown["high_purity"] == 3
    assert tier_breakdown["expanded"] == 0


def test_list_marketplace_leads_supports_tier_filtering() -> None:
    sxsoft = rss_sources.create_source(
        {
            "name": "软件项目交易网最新外包项目",
            "url": "https://www.sxsoft.com/",
            "frequency": 3600,
            "source_type": SourceType.FREELANCE_MARKETPLACE,
            "config": {"adapter": "sxsoft_latest"},
        }
    )
    raw_entries.create_entry(
        {
            "source_id": sxsoft.id,
            "guid": "sx-high",
            "title": "后台及数据库开发",
            "summary": "后台及数据库开发 | 5千~1万 | 20",
            "content": None,
            "link": "https://www.sxsoft.com/project/high",
            "tags": ["marketplace", "sxsoft"],
            "metadata": {"platform": "软件项目交易网", "budget": "5千~1万", "timeline": "20", "skills": []},
        }
    )
    raw_entries.create_entry(
        {
            "source_id": sxsoft.id,
            "guid": "sx-expanded",
            "title": "基于RK3568的openEuler Embedded版本编译java/mysql/qt",
            "summary": "基于RK3568的openEuler Embedded版本编译java/mysql/qt | 待商议 | 20",
            "content": None,
            "link": "https://www.sxsoft.com/project/expanded",
            "tags": ["marketplace", "sxsoft"],
            "metadata": {"platform": "软件项目交易网", "budget": "待商议", "timeline": "20", "skills": ["嵌入式与智能硬件"]},
        }
    )

    total, items, tier_breakdown = marketplace_leads.list_leads(
        tier=marketplace_leads.MarketplaceLeadTier.EXPANDED
    )

    assert total == 1
    assert items[0].title == "基于RK3568的openEuler Embedded版本编译java/mysql/qt"
    assert items[0].lead_tier == marketplace_leads.MarketplaceLeadTier.EXPANDED
    assert tier_breakdown["high_purity"] == 1
    assert tier_breakdown["expanded"] == 1


def test_peopleperhour_frontend_project_is_high_purity() -> None:
    pph = rss_sources.create_source(
        {
            "name": "PeoplePerHour Technology Projects",
            "url": "https://www.peopleperhour.com/freelance-jobs/technology-programming",
            "frequency": 3600,
            "source_type": SourceType.FREELANCE_MARKETPLACE,
            "config": {"adapter": "peopleperhour_technology"},
        }
    )
    raw_entries.create_entry(
        {
            "source_id": pph.id,
            "guid": "pph-frontend",
            "title": "Frontend Developer (React / Next.js)",
            "summary": "Frontend Developer (React / Next.js) | $41 | a day ago",
            "content": "Build polished, responsive UIs and collaborate with backend teams.",
            "link": "https://www.peopleperhour.com/projects/frontend",
            "tags": ["marketplace", "peopleperhour", "remote"],
            "metadata": {
                "platform": "PeoplePerHour",
                "budget": "$41",
                "timeline": "a day ago",
                "location": "Remote",
                "skills": [],
            },
        }
    )

    total, items, tier_breakdown = marketplace_leads.list_leads(
        tier=marketplace_leads.MarketplaceLeadTier.HIGH_PURITY
    )

    assert total == 1
    assert items[0].lead_tier == marketplace_leads.MarketplaceLeadTier.HIGH_PURITY
    assert tier_breakdown["high_purity"] == 1
    assert tier_breakdown["expanded"] == 0
