from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.main import app
from app.models import SourceType
from app.services import marketplace_leads, raw_entries, rss_sources
from fastapi.testclient import TestClient


def _event_value(event: object, key: str) -> object:
    if isinstance(event, dict):
        return event.get(key)
    return getattr(event, key)


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
    assert payload["source_breakdown"][0]["source_name"] == "Freelancer Web Development Jobs"
    assert payload["source_breakdown"][0]["high_purity"] == 1


def test_marketplace_leads_returns_todo_queue(client: TestClient) -> None:
    source = rss_sources.create_source(
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
            "source_id": source.id,
            "guid": "todo-new",
            "title": "Frontend Developer (React / Next.js)",
            "summary": "Frontend Developer (React / Next.js) | $1200 | 2 days",
            "content": "Build a frontend app.",
            "published_at": datetime(2026, 4, 16, 9, 0, tzinfo=UTC),
            "link": "https://example.com/todo-new",
            "tags": ["marketplace"],
            "metadata": {
                "platform": "PeoplePerHour",
                "budget": "$1200",
                "timeline": "2 days",
            },
        }
    )
    raw_entries.create_entry(
        {
            "source_id": source.id,
            "guid": "todo-watching",
            "title": "CRM 后台开发",
            "summary": "CRM 后台开发 | 5千~1万 | 15天",
            "content": "Need a backend system.",
            "published_at": datetime(2026, 4, 10, 9, 0, tzinfo=UTC),
            "link": "https://example.com/todo-watching",
            "tags": ["marketplace"],
            "metadata": {
                "platform": "PeoplePerHour",
                "lead_status": "watching",
                "lead_events": [
                    {
                        "event_type": "status_changed",
                        "created_at": "2026-04-12T09:00:00+00:00",
                        "status_from": "new",
                        "status_to": "watching",
                    }
                ],
            },
        }
    )
    raw_entries.create_entry(
        {
            "source_id": source.id,
            "guid": "todo-contacted",
            "title": "后台及数据库开发",
            "summary": "后台及数据库开发 | 5千~1万 | 20",
            "content": "Database and backend work.",
            "published_at": datetime(2026, 4, 8, 9, 0, tzinfo=UTC),
            "link": "https://example.com/todo-contacted",
            "tags": ["marketplace"],
            "metadata": {
                "platform": "PeoplePerHour",
                "lead_status": "contacted",
                "lead_events": [
                    {
                        "event_type": "status_changed",
                        "created_at": "2026-04-09T09:00:00+00:00",
                        "status_from": "new",
                        "status_to": "contacted",
                    }
                ],
            },
        }
    )

    response = client.get("/api/v1/marketplace-leads/")
    assert response.status_code == 200
    payload = response.json()

    assert payload["todo_breakdown"]["total"] == 3
    assert payload["todo_breakdown"]["high"] >= 1
    assert payload["todo_breakdown"]["new_high_priority"] == 1
    assert payload["todo_breakdown"]["watching_stale"] == 1
    assert payload["todo_breakdown"]["contacted_stale"] == 1
    assert {item["reminder_type"] for item in payload["todo_queue"]} == {
        "new_high_priority",
        "watching_stale",
        "contacted_stale",
    }


def test_marketplace_leads_returns_source_recommendations(client: TestClient) -> None:
    good_source = rss_sources.create_source(
        {
            "name": "PeoplePerHour Technology Projects",
            "url": "https://www.peopleperhour.com/freelance-jobs/technology-programming",
            "frequency": 3600,
            "source_type": SourceType.FREELANCE_MARKETPLACE,
            "config": {"adapter": "peopleperhour_technology"},
        }
    )
    noisy_source = rss_sources.create_source(
        {
            "name": "Remotive Software Contracts",
            "url": "https://remotive.com/remote-jobs/software-dev",
            "frequency": 3600,
            "source_type": SourceType.FREELANCE_MARKETPLACE,
            "config": {"adapter": "remotive_contracts"},
        }
    )
    for index, title in enumerate(
        [
            "Frontend Developer (React / Next.js)",
            "Full-Stack Web Developer",
            "HubSpot CMS (HubL) Developer – Custom Quote Template",
        ],
        start=1,
    ):
        raw_entries.create_entry(
            {
                "source_id": good_source.id,
                "guid": f"good-{index}",
                "title": title,
                "summary": f"{title} | $1200 | 2 days",
                "content": "Build a software product.",
                "link": f"https://example.com/good-{index}",
                "tags": ["marketplace"],
                "metadata": {
                    "platform": "PeoplePerHour",
                    "budget": "$1200",
                    "timeline": "2 days",
                },
            }
        )
    for index, title in enumerate(
        [
            "Senior Backend Engineer",
            "Platform Engineer",
        ],
        start=1,
    ):
        raw_entries.create_entry(
            {
                "source_id": noisy_source.id,
                "guid": f"noisy-{index}",
                "title": title,
                "summary": f"{title} | Full-time | Remote",
                "content": "Employment type: full-time",
                "link": f"https://example.com/noisy-{index}",
                "tags": ["marketplace"],
                "metadata": {
                    "platform": "Remotive",
                    "engagement": "full-time",
                },
            }
        )

    response = client.get("/api/v1/marketplace-leads/")
    assert response.status_code == 200
    payload = response.json()

    recommendations = {item["source_name"]: item for item in payload["source_recommendations"]}
    assert recommendations["PeoplePerHour Technology Projects"]["action"] == "expand_similar"
    assert recommendations["Remotive Software Contracts"]["action"] == "pause_candidate"


def test_marketplace_leads_returns_conversion_breakdowns(client: TestClient) -> None:
    pph = rss_sources.create_source(
        {
            "name": "PeoplePerHour Technology Projects",
            "url": "https://www.peopleperhour.com/freelance-jobs/technology-programming",
            "frequency": 3600,
            "source_type": SourceType.FREELANCE_MARKETPLACE,
            "config": {"adapter": "peopleperhour_technology"},
        }
    )
    remotive = rss_sources.create_source(
        {
            "name": "Remotive Software Contracts",
            "url": "https://remotive.com/remote-jobs/software-dev",
            "frequency": 3600,
            "source_type": SourceType.FREELANCE_MARKETPLACE,
            "config": {"adapter": "remotive_contracts"},
        }
    )
    won = raw_entries.create_entry(
        {
            "source_id": pph.id,
            "guid": "conv-won",
            "title": "Frontend Developer (React / Next.js)",
            "summary": "Frontend Developer (React / Next.js) | $1200 | 2 days",
            "content": "Build a frontend app.",
            "link": "https://example.com/conv-won",
            "tags": ["marketplace"],
            "metadata": {
                "platform": "PeoplePerHour",
                "budget": "$1200",
                "timeline": "2 days",
                "lead_outcome": "won",
            },
        }
    )
    raw_entries.create_entry(
        {
            "source_id": pph.id,
            "guid": "conv-lost",
            "title": "Full-Stack Web Developer",
            "summary": "Full-Stack Web Developer | $2K | 7 days",
            "content": "Build a full-stack web application.",
            "link": "https://example.com/conv-lost",
            "tags": ["marketplace"],
            "metadata": {
                "platform": "PeoplePerHour",
                "budget": "$2K",
                "timeline": "7 days",
                "lead_outcome": "lost",
            },
        }
    )
    raw_entries.create_entry(
        {
            "source_id": remotive.id,
            "guid": "conv-full-time",
            "title": "Senior Backend Engineer",
            "summary": "Senior Backend Engineer | Remote",
            "content": "Employment type: full-time",
            "link": "https://example.com/conv-full-time",
            "tags": ["marketplace"],
            "metadata": {
                "platform": "Remotive",
                "engagement": "full-time",
                "lead_outcome": "not_fit",
            },
        }
    )
    marketplace_leads.update_lead_status(won.id, marketplace_leads.MarketplaceLeadStatus.CONTACTED)

    response = client.get("/api/v1/marketplace-leads/")
    assert response.status_code == 200
    payload = response.json()

    source_metrics = {item["label"]: item for item in payload["source_conversion_breakdown"]}
    assert source_metrics["PeoplePerHour Technology Projects"]["won"] == 1
    assert source_metrics["PeoplePerHour Technology Projects"]["lost"] == 1
    assert source_metrics["PeoplePerHour Technology Projects"]["resolved"] == 2
    assert source_metrics["PeoplePerHour Technology Projects"]["contacted"] == 1
    assert source_metrics["Remotive Software Contracts"]["not_fit"] == 1

    segment_metrics = {item["key"]: item for item in payload["segment_conversion_breakdown"]}
    assert segment_metrics["tier:high_purity"]["resolved"] == 3
    assert segment_metrics["kind:project"]["won"] == 1
    assert segment_metrics["kind:full_time_job"]["not_fit"] == 1


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

    total, items, tier_breakdown, kind_breakdown, _, source_breakdown = marketplace_leads.list_leads(limit=3)

    assert total == 3
    source_ids = [item.source_id for item in items]
    assert source_ids == [sxsoft.id, zbj.id, zbj.id]
    assert tier_breakdown["high_purity"] == 3
    assert tier_breakdown["expanded"] == 0
    assert kind_breakdown["project"] == 3
    assert source_breakdown[0].source_name in {"猪八戒需求大厅精选任务", "软件项目交易网最新外包项目"}


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

    total, items, tier_breakdown, _, _, _ = marketplace_leads.list_leads(
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

    total, items, _, _, status_breakdown, _ = marketplace_leads.list_leads()

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


def test_update_marketplace_lead_outcome(client: TestClient) -> None:
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
            "guid": "lead-outcome",
            "title": "Full-Stack Web Developer",
            "summary": "Full-Stack Web Developer | $2K | 7 days",
            "content": "Build a full-stack web application.",
            "link": "https://example.com/full-stack-outcome",
            "tags": ["marketplace"],
            "metadata": {
                "platform": "PeoplePerHour",
                "budget": "$2K",
                "timeline": "7 days",
                "skills": ["Python", "Django"],
            },
        }
    )

    response = client.put(f"/api/v1/marketplace-leads/{lead.id}/outcome", json={"outcome": "won"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["lead_outcome"] == "won"
    assert any(
        _event_value(event, "event_type") == "outcome_updated"
        and _event_value(event, "outcome_to") == "won"
        for event in payload["lead_events"]
    )


def test_get_marketplace_lead_detail_and_update_notes(client: TestClient) -> None:
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
            "guid": "lead-detail",
            "title": "Full-Stack Web Developer",
            "summary": "Full-Stack Web Developer | $2K | 7 days",
            "content": "Build a full-stack web application with admin tooling.",
            "link": "https://example.com/full-stack-detail",
            "tags": ["marketplace"],
            "metadata": {
                "platform": "PeoplePerHour",
                "budget": "$2K",
                "timeline": "7 days",
                "skills": ["Python", "Django"],
                "lead_notes": "Need follow-up on delivery scope",
            },
        }
    )

    detail_response = client.get(f"/api/v1/marketplace-leads/{lead.id}")

    assert detail_response.status_code == 200
    assert detail_response.json()["notes"] == "Need follow-up on delivery scope"

    update_response = client.put(
        f"/api/v1/marketplace-leads/{lead.id}/notes",
        json={"notes": "Reached out by email on Friday"},
    )

    assert update_response.status_code == 200
    assert update_response.json()["notes"] == "Reached out by email on Friday"

    refetch_response = client.get(f"/api/v1/marketplace-leads/{lead.id}")
    assert refetch_response.status_code == 200
    payload = refetch_response.json()
    assert payload["notes"] == "Reached out by email on Friday"
    assert payload["last_action_at"]
    assert any(_event_value(event, "event_type") == "captured" for event in payload["lead_events"])
    assert any(
        _event_value(event, "event_type") == "notes_updated"
        and _event_value(event, "note") == "Reached out by email on Friday"
        for event in payload["lead_events"]
    )


def test_marketplace_lead_history_tracks_status_and_notes_updates(client: TestClient) -> None:
    source = rss_sources.create_source(
        {
            "name": "Jobicy Contract Developer Roles",
            "url": "https://jobicy.com/?feed=job_feed&job_categories=dev",
            "frequency": 3600,
            "source_type": SourceType.FREELANCE_MARKETPLACE,
            "config": {"adapter": "jobicy_api"},
        }
    )
    lead = raw_entries.create_entry(
        {
            "source_id": source.id,
            "guid": "lead-history",
            "title": "Senior Python Developer",
            "summary": "Senior Python Developer | Remote | Contract",
            "content": "Looking for a contract Python developer for migration work.",
            "link": "https://example.com/senior-python-developer",
            "tags": ["marketplace"],
            "metadata": {
                "platform": "Jobicy",
                "skills": ["Python"],
            },
        }
    )

    status_response = client.put(
        f"/api/v1/marketplace-leads/{lead.id}/status",
        json={"status": "watching"},
    )
    assert status_response.status_code == 200

    notes_response = client.put(
        f"/api/v1/marketplace-leads/{lead.id}/notes",
        json={"notes": "Review outreach plan before contacting"},
    )
    assert notes_response.status_code == 200

    detail_response = client.get(f"/api/v1/marketplace-leads/{lead.id}")
    assert detail_response.status_code == 200
    payload = detail_response.json()

    assert payload["last_action_at"]
    assert len(payload["lead_events"]) >= 3
    assert any(_event_value(event, "event_type") == "captured" for event in payload["lead_events"])
    assert any(
        _event_value(event, "event_type") == "status_changed"
        and _event_value(event, "status_from") == "new"
        and _event_value(event, "status_to") == "watching"
        for event in payload["lead_events"]
    )
    assert any(
        _event_value(event, "event_type") == "notes_updated"
        and _event_value(event, "note") == "Review outreach plan before contacting"
        for event in payload["lead_events"]
    )


def test_marketplace_lead_list_supports_outcome_filtering(client: TestClient) -> None:
    source = rss_sources.create_source(
        {
            "name": "PeoplePerHour Technology Projects",
            "url": "https://www.peopleperhour.com/freelance-jobs/technology-programming",
            "frequency": 3600,
            "source_type": SourceType.FREELANCE_MARKETPLACE,
            "config": {"adapter": "peopleperhour_technology"},
        }
    )
    won_lead = raw_entries.create_entry(
        {
            "source_id": source.id,
            "guid": "lead-won",
            "title": "Frontend Developer (React / Next.js)",
            "summary": "Frontend Developer (React / Next.js) | $1200 | 2 days",
            "content": "Build a frontend app.",
            "link": "https://example.com/lead-won",
            "tags": ["marketplace"],
            "metadata": {
                "platform": "PeoplePerHour",
                "lead_outcome": "won",
            },
        }
    )
    raw_entries.create_entry(
        {
            "source_id": source.id,
            "guid": "lead-open",
            "title": "CRM 后台开发",
            "summary": "CRM 后台开发 | 5千~1万 | 15天",
            "content": "Need a backend system.",
            "link": "https://example.com/lead-open",
            "tags": ["marketplace"],
            "metadata": {
                "platform": "PeoplePerHour",
            },
        }
    )

    response = client.get("/api/v1/marketplace-leads/", params={"lead_outcome": "won"})
    assert response.status_code == 200
    payload = response.json()

    assert payload["total"] == 1
    assert payload["items"][0]["id"] == won_lead.id
    assert payload["outcome_breakdown"]["won"] == 1
    assert payload["outcome_breakdown"]["unresolved"] == 1


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

    total, items, tier_breakdown, _, _, _ = marketplace_leads.list_leads(
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

    total, items, tier_breakdown, _, _, _ = marketplace_leads.list_leads(
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

    total, items, tier_breakdown, _, _, _ = marketplace_leads.list_leads(
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

    total, items, tier_breakdown, _, _, _ = marketplace_leads.list_leads(
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

    total, items, tier_breakdown, _, _, _ = marketplace_leads.list_leads(
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

    total, items, tier_breakdown, _, _, _ = marketplace_leads.list_leads(
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

    total, items, _, kind_breakdown, _, _ = marketplace_leads.list_leads(
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

    total, items, _, kind_breakdown, _, _ = marketplace_leads.list_leads(reviewable_only=True)

    assert total == 1
    assert items[0].lead_kind == marketplace_leads.MarketplaceLeadKind.PROJECT
    assert kind_breakdown["project"] == 1
    assert kind_breakdown["full_time_job"] == 1


def test_marketplace_leads_merge_same_company_similar_titles() -> None:
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
            "guid": "remotive-react-role",
            "title": "Senior Full-stack React Developer",
            "summary": "Senior Full-stack React Developer | Remote",
            "content": "Contract role for React delivery.",
            "link": "https://remotive.com/remote-jobs/software-development/full-stack-react",
            "author": "Lemon.io",
            "tags": ["marketplace", "remotive"],
            "metadata": {
                "platform": "Remotive",
                "category": "Software Development",
                "engagement": "contract",
                "location": "Remote",
                "skills": ["react", "python", "next.js"],
            },
        }
    )
    raw_entries.create_entry(
        {
            "source_id": job_board.id,
            "guid": "job-board-react-role",
            "title": "Full Stack React Developer",
            "summary": "Full Stack React Developer | Remote",
            "content": "React contract role with product delivery ownership.",
            "link": "https://example.com/jobs/full-stack-react",
            "author": "Lemon.io",
            "tags": ["marketplace", "remote"],
            "metadata": {
                "platform": "Example Jobs",
                "category": "Software Development",
                "engagement": "contract",
                "location": "Remote",
                "skills": ["react", "python", "next.js"],
            },
        }
    )

    total, items, _, _, _, _ = marketplace_leads.list_leads()

    assert total == 1
    assert items[0].duplicate_count == 2
    assert len(items[0].duplicate_sources) == 2


def test_marketplace_leads_merge_same_link_without_query_string() -> None:
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
    for guid, source_id, link in (
        ("same-link-a", remotive.id, "https://example.com/jobs/123?utm_source=remotive"),
        ("same-link-b", job_board.id, "https://example.com/jobs/123?ref=job-board"),
    ):
        raw_entries.create_entry(
            {
                "source_id": source_id,
                "guid": guid,
                "title": "Senior Backend Engineer",
                "summary": "Senior Backend Engineer | Remote",
                "content": "Contract backend work.",
                "link": link,
                "tags": ["marketplace", "remote"],
                "metadata": {
                    "platform": "Example Jobs",
                    "category": "Software Development",
                    "engagement": "contract",
                    "location": "Remote",
                    "skills": ["python", "api"],
                },
            }
        )

    total, items, _, _, _, _ = marketplace_leads.list_leads()

    assert total == 1
    assert items[0].duplicate_count == 2


def test_marketplace_leads_do_not_merge_distinct_roles_same_company() -> None:
    remotive = rss_sources.create_source(
        {
            "name": "Remotive Software Contracts",
            "url": "https://remotive.com/api/remote-jobs?category=software-dev&limit=40",
            "frequency": 21600,
            "source_type": SourceType.FREELANCE_MARKETPLACE,
            "config": {"adapter": "remotive_api"},
        }
    )
    for guid, title, skills in (
        ("same-company-react", "Senior Full-stack React Developer", ["react", "python", "next.js"]),
        ("same-company-golang", "Senior Golang Developer", ["golang", "grpc", "postgres"]),
    ):
        raw_entries.create_entry(
            {
                "source_id": remotive.id,
                "guid": guid,
                "title": title,
                "summary": f"{title} | Remote",
                "content": "Contract software role.",
                "link": f"https://remotive.com/jobs/{guid}",
                "author": "Lemon.io",
                "tags": ["marketplace", "remotive"],
                "metadata": {
                    "platform": "Remotive",
                    "category": "Software Development",
                    "engagement": "contract",
                    "location": "Remote",
                    "skills": skills,
                },
            }
        )

    total, items, _, _, _, _ = marketplace_leads.list_leads()


def test_marketplace_leads_source_breakdown_tracks_quality() -> None:
    pph = rss_sources.create_source(
        {
            "name": "PeoplePerHour Technology Projects",
            "url": "https://www.peopleperhour.com/freelance-jobs/technology-programming",
            "frequency": 3600,
            "source_type": SourceType.FREELANCE_MARKETPLACE,
            "config": {"adapter": "peopleperhour_technology"},
        }
    )
    jobicy = rss_sources.create_source(
        {
            "name": "Jobicy Contract Developer Roles",
            "url": "https://jobicy.com/api/v2/remote-jobs?count=50&tag=python%20developer",
            "frequency": 21600,
            "source_type": SourceType.FREELANCE_MARKETPLACE,
            "config": {"adapter": "jobicy_api"},
        }
    )
    raw_entries.create_entry(
        {
            "source_id": pph.id,
            "guid": "pph-dashboard-role",
            "title": "Frontend Developer (React / Next.js)",
            "summary": "Frontend Developer (React / Next.js) | $41 | a day ago",
            "content": "Build polished, responsive UIs and collaborate with backend teams.",
            "link": "https://www.peopleperhour.com/projects/frontend-dashboard",
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
    contacted = raw_entries.create_entry(
        {
            "source_id": jobicy.id,
            "guid": "jobicy-dashboard-role",
            "title": "Senior Python Developer – Code Migration Specialist",
            "summary": "Senior Python Developer – Code Migration Specialist | Philippines",
            "content": "Freelance project-based collaboration for a senior Python developer.",
            "link": "https://jobicy.com/jobs/3001-dashboard",
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
    marketplace_leads.update_lead_status(contacted.id, marketplace_leads.MarketplaceLeadStatus.CONTACTED)

    total, _, _, _, _, source_breakdown = marketplace_leads.list_leads()

    assert total == 2
    assert len(source_breakdown) == 2
    by_name = {item.source_name: item for item in source_breakdown}
    assert by_name["PeoplePerHour Technology Projects"].high_purity == 1
    assert by_name["PeoplePerHour Technology Projects"].reviewable == 1
    assert by_name["Jobicy Contract Developer Roles"].contacted == 1
    assert by_name["Jobicy Contract Developer Roles"].reviewable == 1


def test_marketplace_leads_prioritize_reviewable_new_high_purity_items() -> None:
    pph = rss_sources.create_source(
        {
            "name": "PeoplePerHour Technology Projects",
            "url": "https://www.peopleperhour.com/freelance-jobs/technology-programming",
            "frequency": 3600,
            "source_type": SourceType.FREELANCE_MARKETPLACE,
            "config": {"adapter": "peopleperhour_technology"},
        }
    )
    jobs = rss_sources.create_source(
        {
            "name": "Generic Remote Jobs",
            "url": "https://example.com/jobs",
            "frequency": 21600,
            "source_type": SourceType.FREELANCE_MARKETPLACE,
            "config": {"adapter": "generic_remote"},
        }
    )
    top_lead = raw_entries.create_entry(
        {
            "source_id": pph.id,
            "guid": "priority-top",
            "title": "Frontend Developer (React / Next.js)",
            "summary": "Frontend Developer (React / Next.js) | $41 | a day ago",
            "content": "Build polished, responsive UIs and collaborate with backend teams.",
            "link": "https://www.peopleperhour.com/projects/priority-top",
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
    low_lead = raw_entries.create_entry(
        {
            "source_id": jobs.id,
            "guid": "priority-low",
            "title": "Senior Backend Engineer",
            "summary": "Senior Backend Engineer | Remote",
            "content": "Employment type: full-time. Build backend APIs and services.",
            "link": "https://example.com/jobs/priority-low",
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
    marketplace_leads.update_lead_status(low_lead.id, marketplace_leads.MarketplaceLeadStatus.CONTACTED)

    total, items, _, _, _, _ = marketplace_leads.list_leads()

    assert total == 2
    assert items[0].id == top_lead.id
    assert items[0].priority_score > items[1].priority_score
    assert "高纯度线索" in items[0].priority_reason
    assert "全职招聘降权" in items[1].priority_reason
