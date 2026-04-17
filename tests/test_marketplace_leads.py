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
    assert item["normalized_budget"] == "$500 Avg Bid"
    assert item["timeline"] == "6 days left"
    assert item["normalized_timeline"] == "6 days"
    assert item["skills"] == ["Web Development", "Laravel"]
    assert item["lead_kind"] == "project"
    assert item["lead_tier"] == "high_purity"
    assert item["lead_status"] == "new"
    assert item["duplicate_count"] == 1
    assert payload["kind_breakdown"]["project"] == 1
    assert payload["status_breakdown"]["new"] == 1


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

    total, items, tier_breakdown, kind_breakdown, _ = marketplace_leads.list_leads(limit=3)

    assert total == 3
    source_ids = [item.source_id for item in items]
    assert source_ids == [sxsoft.id, zbj.id, zbj.id]
    assert tier_breakdown["high_purity"] == 3
    assert tier_breakdown["expanded"] == 0
    assert kind_breakdown["project"] == 3


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

    total, items, tier_breakdown, _, _ = marketplace_leads.list_leads(
        tier=marketplace_leads.MarketplaceLeadTier.EXPANDED
    )

    assert total == 1
    assert items[0].title == "基于RK3568的openEuler Embedded版本编译java/mysql/qt"
    assert items[0].lead_tier == marketplace_leads.MarketplaceLeadTier.EXPANDED
    assert tier_breakdown["high_purity"] == 1
    assert tier_breakdown["expanded"] == 1


def test_list_marketplace_leads_merges_duplicates_across_sources() -> None:
    pph = rss_sources.create_source(
        {
            "name": "PeoplePerHour Technology Projects",
            "url": "https://www.peopleperhour.com/freelance-jobs/technology-programming",
            "frequency": 3600,
            "source_type": SourceType.FREELANCE_MARKETPLACE,
            "config": {"adapter": "peopleperhour_technology"},
        }
    )
    freelancer = rss_sources.create_source(
        {
            "name": "Freelancer Web Development Jobs",
            "url": "https://www.freelancer.com/jobs/web-development/",
            "frequency": 3600,
            "source_type": SourceType.FREELANCE_MARKETPLACE,
            "config": {"adapter": "freelancer_jobs"},
        }
    )
    for source in (pph, freelancer):
        raw_entries.create_entry(
            {
                "source_id": source.id,
                "guid": f"lead-{source.id}",
                "title": "Frontend Developer React Next.js",
                "summary": "Frontend Developer React Next.js | $1200 | 7 days",
                "content": "Build React and Next.js frontend for a SaaS dashboard.",
                "link": f"https://example.com/{source.id}",
                "tags": ["marketplace"],
                "metadata": {
                    "platform": source.name,
                    "budget": "$1200",
                    "timeline": "7 days",
                    "skills": ["React", "Next.js"],
                },
            }
        )

    total, items, _, _, status_breakdown = marketplace_leads.list_leads()

    assert total == 1
    assert items[0].duplicate_count == 2
    assert len(items[0].duplicate_sources) == 2
    assert status_breakdown["new"] == 1


def test_update_marketplace_lead_status(client: TestClient) -> None:
    source = rss_sources.create_source(
        {
            "name": "PeoplePerHour Technology Projects",
            "url": "https://www.peopleperhour.com/freelance-jobs/technology-programming",
            "frequency": 3600,
            "source_type": SourceType.FREELANCE_MARKETPLACE,
            "config": {"adapter": "peopleperhour_technology"},
        }
    )
    lead = raw_entries.create_entry(
        {
            "source_id": source.id,
            "guid": "lead-status",
            "title": "Full-Stack Web Developer",
            "summary": "Full-Stack Web Developer | $2K | 7 days",
            "content": "Build a full-stack web application.",
            "link": "https://example.com/full-stack",
            "tags": ["marketplace"],
            "metadata": {
                "platform": "PeoplePerHour",
                "budget": "$2K",
                "timeline": "7 days",
                "skills": ["Python", "Django"],
            },
        }
    )

    response = client.put(f"/api/v1/marketplace-leads/{lead.id}/status", json={"status": "watching"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["lead_status"] == "watching"

    list_response = client.get("/api/v1/marketplace-leads/", params={"lead_status": "watching"})
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1


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

    total, items, tier_breakdown, _, _ = marketplace_leads.list_leads(
        tier=marketplace_leads.MarketplaceLeadTier.HIGH_PURITY
    )

    assert total == 1
    assert items[0].lead_tier == marketplace_leads.MarketplaceLeadTier.HIGH_PURITY
    assert tier_breakdown["high_purity"] == 1
    assert tier_breakdown["expanded"] == 0


def test_peopleperhour_full_stack_project_is_high_purity() -> None:
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
            "guid": "pph-full-stack",
            "title": "Full Stack Developer for Online Casino Platform",
            "summary": "Full Stack Developer for Online Casino Platform | $6.8K | a day ago",
            "content": "Build responsive front-end interfaces, backend APIs, and database schemas.",
            "link": "https://www.peopleperhour.com/projects/full-stack",
            "tags": ["marketplace", "peopleperhour", "remote"],
            "metadata": {
                "platform": "PeoplePerHour",
                "budget": "$6.8K",
                "timeline": "a day ago",
                "location": "Remote",
                "skills": [],
            },
        }
    )

    total, items, tier_breakdown, _, _ = marketplace_leads.list_leads(
        tier=marketplace_leads.MarketplaceLeadTier.HIGH_PURITY
    )

    assert total == 1
    assert items[0].lead_tier == marketplace_leads.MarketplaceLeadTier.HIGH_PURITY
    assert tier_breakdown["high_purity"] == 1
    assert tier_breakdown["expanded"] == 0


def test_peopleperhour_hubspot_cms_project_is_high_purity() -> None:
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
            "guid": "pph-hubspot",
            "title": "HubSpot CMS (HubL) Developer – Custom Quote Template",
            "summary": "HubSpot CMS (HubL) Developer – Custom Quote Template | $41 | 16 hours ago",
            "content": "Need a custom data-driven quote template inside HubSpot CMS.",
            "link": "https://www.peopleperhour.com/projects/hubspot",
            "tags": ["marketplace", "peopleperhour", "remote"],
            "metadata": {
                "platform": "PeoplePerHour",
                "budget": "$41",
                "timeline": "16 hours ago",
                "location": "Remote",
                "skills": [],
            },
        }
    )

    total, items, tier_breakdown, _, _ = marketplace_leads.list_leads(
        tier=marketplace_leads.MarketplaceLeadTier.HIGH_PURITY
    )

    assert total == 1
    assert items[0].lead_tier == marketplace_leads.MarketplaceLeadTier.HIGH_PURITY
    assert tier_breakdown["high_purity"] == 1
    assert tier_breakdown["expanded"] == 0


def test_remotive_full_stack_react_contract_is_high_purity() -> None:
    remotive = rss_sources.create_source(
        {
            "name": "Remotive Software Contracts",
            "url": "https://remotive.com/api/remote-jobs?category=software-dev&limit=40",
            "frequency": 21600,
            "source_type": SourceType.FREELANCE_MARKETPLACE,
            "config": {"adapter": "remotive_api"},
        }
    )
    raw_entries.create_entry(
        {
            "source_id": remotive.id,
            "guid": "remotive-full-stack-react",
            "title": "Senior Full-stack React Developer",
            "summary": "Senior Full-stack React Developer | Americas, Europe, Asia, Oceania",
            "content": "Contract software development role covering React, Python, Node.js, and Next.js delivery.",
            "link": "https://remotive.com/remote-jobs/software-development/senior-full-stack-react-developer-2088711",
            "tags": ["marketplace", "remotive", "remote", "Software Development"],
            "metadata": {
                "platform": "Remotive",
                "category": "Software Development",
                "timeline": "Americas, Europe, Asia, Oceania",
                "engagement": "contract",
                "location": "Americas, Europe, Asia, Oceania",
                "skills": ["react", "python", "node.js", "next.js"],
            },
        }
    )

    total, items, tier_breakdown, _, _ = marketplace_leads.list_leads(
        tier=marketplace_leads.MarketplaceLeadTier.HIGH_PURITY
    )

    assert total == 1
    assert items[0].source_name == "Remotive Software Contracts"
    assert items[0].lead_tier == marketplace_leads.MarketplaceLeadTier.HIGH_PURITY
    assert tier_breakdown["high_purity"] == 1
    assert tier_breakdown["expanded"] == 0


def test_jobicy_python_developer_contract_is_high_purity() -> None:
    jobicy = rss_sources.create_source(
        {
            "name": "Jobicy Contract Developer Roles",
            "url": "https://jobicy.com/api/v2/remote-jobs?count=100&tag=developer",
            "frequency": 21600,
            "source_type": SourceType.FREELANCE_MARKETPLACE,
            "config": {"adapter": "jobicy_api"},
        }
    )
    raw_entries.create_entry(
        {
            "source_id": jobicy.id,
            "guid": "jobicy-python-developer",
            "title": "Senior Python Developer – Code Migration Specialist",
            "summary": "Senior Python Developer – Code Migration Specialist | Philippines",
            "content": "Freelance project-based collaboration for a senior Python developer. 20-30 hours per week.",
            "link": "https://jobicy.com/jobs/3001-senior-python-developer-code-migration-specialist",
            "tags": ["marketplace", "jobicy", "remote", "project-based"],
            "metadata": {
                "platform": "Jobicy",
                "category": "Software Engineering",
                "timeline": "Philippines",
                "engagement": "hourly-contract",
                "location": "Philippines",
                "skills": ["python", "docker", "Software Engineering"],
            },
        }
    )

    total, items, tier_breakdown, _, _ = marketplace_leads.list_leads(
        tier=marketplace_leads.MarketplaceLeadTier.HIGH_PURITY
    )

    assert total == 1
    assert items[0].source_name == "Jobicy Contract Developer Roles"
    assert items[0].lead_tier == marketplace_leads.MarketplaceLeadTier.HIGH_PURITY
    assert tier_breakdown["high_purity"] == 1
    assert tier_breakdown["expanded"] == 0


def test_peopleperhour_kiosk_project_stays_expanded() -> None:
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
            "guid": "pph-kiosk",
            "title": "Android Device Owner/Kiosk Mode Specialist — OEM Provisioning",
            "summary": "Android Device Owner/Kiosk Mode Specialist — OEM Provisioning | $488 | 10 hours ago",
            "content": "Need kiosk mode, OEM provisioning, and OTA setup for dedicated tablets.",
            "link": "https://www.peopleperhour.com/projects/kiosk",
            "tags": ["marketplace", "peopleperhour", "remote"],
            "metadata": {
                "platform": "PeoplePerHour",
                "budget": "$488",
                "timeline": "10 hours ago",
                "location": "Remote",
                "skills": [],
            },
        }
    )

    total, items, tier_breakdown, _, _ = marketplace_leads.list_leads(
        tier=marketplace_leads.MarketplaceLeadTier.EXPANDED
    )

    assert total == 1
    assert items[0].lead_tier == marketplace_leads.MarketplaceLeadTier.EXPANDED
    assert tier_breakdown["high_purity"] == 0
    assert tier_breakdown["expanded"] == 1


def test_list_marketplace_leads_supports_lead_kind_filtering() -> None:
    remotive = rss_sources.create_source(
        {
            "name": "Remotive Software Contracts",
            "url": "https://remotive.com/api/remote-jobs?category=software-dev&limit=40",
            "frequency": 21600,
            "source_type": SourceType.FREELANCE_MARKETPLACE,
            "config": {"adapter": "remotive_api"},
        }
    )
    job_board = rss_sources.create_source(
        {
            "name": "Generic Remote Jobs",
            "url": "https://example.com/jobs",
            "frequency": 21600,
            "source_type": SourceType.FREELANCE_MARKETPLACE,
            "config": {"adapter": "generic_remote"},
        }
    )
    raw_entries.create_entry(
        {
            "source_id": remotive.id,
            "guid": "remotive-contract-role",
            "title": "Senior Full-stack React Developer",
            "summary": "Senior Full-stack React Developer | Americas",
            "content": "Contract software development role covering React and Python delivery.",
            "link": "https://remotive.com/remote-jobs/1",
            "tags": ["marketplace", "remotive", "remote"],
            "metadata": {
                "platform": "Remotive",
                "category": "Software Development",
                "engagement": "contract",
                "location": "Americas",
                "skills": ["react", "python"],
            },
        }
    )
    raw_entries.create_entry(
        {
            "source_id": job_board.id,
            "guid": "full-time-role",
            "title": "Senior Backend Engineer",
            "summary": "Senior Backend Engineer | Remote",
            "content": "Employment type: full-time. Build backend APIs and services.",
            "link": "https://example.com/full-time-role",
            "tags": ["marketplace", "remote"],
            "metadata": {
                "platform": "Example Jobs",
                "category": "Software Development",
                "engagement": "full-time",
                "location": "Remote",
                "skills": ["python", "api"],
            },
        }
    )

    total, items, _, kind_breakdown, _ = marketplace_leads.list_leads(
        lead_kind=marketplace_leads.MarketplaceLeadKind.CONTRACT_ROLE
    )

    assert total == 1
    assert items[0].lead_kind == marketplace_leads.MarketplaceLeadKind.CONTRACT_ROLE
    assert kind_breakdown["contract_role"] == 1
    assert kind_breakdown["full_time_job"] == 1


def test_list_marketplace_leads_supports_reviewable_only() -> None:
    freelancer = rss_sources.create_source(
        {
            "name": "Freelancer Web Development Jobs",
            "url": "https://www.freelancer.com/jobs/web-development/",
            "frequency": 3600,
            "source_type": SourceType.FREELANCE_MARKETPLACE,
            "config": {"adapter": "freelancer_jobs"},
        }
    )
    job_board = rss_sources.create_source(
        {
            "name": "Generic Remote Jobs",
            "url": "https://example.com/jobs",
            "frequency": 21600,
            "source_type": SourceType.FREELANCE_MARKETPLACE,
            "config": {"adapter": "generic_remote"},
        }
    )
    raw_entries.create_entry(
        {
            "source_id": freelancer.id,
            "guid": "project-lead",
            "title": "Build a responsive booking portal",
            "summary": "Build a responsive booking portal | $500 Avg Bid | 6 days left",
            "content": "Need a modern booking system with admin dashboard.",
            "link": "https://www.freelancer.com/projects/example",
            "tags": ["marketplace", "freelancer"],
            "metadata": {
                "platform": "Freelancer",
                "budget": "$500 Avg Bid",
                "timeline": "6 days left",
                "engagement": "fixed-price",
                "skills": ["Web Development"],
            },
        }
    )
    raw_entries.create_entry(
        {
            "source_id": job_board.id,
            "guid": "full-time-role-2",
            "title": "Full-time Staff Software Engineer",
            "summary": "Full-time Staff Software Engineer | Remote",
            "content": "Employment type: full-time. Platform engineering role.",
            "link": "https://example.com/full-time-role-2",
            "tags": ["marketplace", "remote"],
            "metadata": {
                "platform": "Example Jobs",
                "category": "Software Development",
                "engagement": "full-time",
                "location": "Remote",
                "skills": ["go", "platform"],
            },
        }
    )

    total, items, _, kind_breakdown, _ = marketplace_leads.list_leads(reviewable_only=True)

    assert total == 1
    assert items[0].lead_kind == marketplace_leads.MarketplaceLeadKind.PROJECT
    assert kind_breakdown["project"] == 1
    assert kind_breakdown["full_time_job"] == 1
