from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.main import app
from app.models import CandidateNeedStatus, RawEntryStatus, SourceStatus, SourceType, SyncChannel
import app.services.export_jobs as export_jobs

from app.services import candidate_clusters, candidate_needs, raw_entries, rss_sources, sync_audit
from app.services.export_jobs import ExportJobStatus
from fastapi.testclient import TestClient
from jobs import task_queue


@pytest.fixture(autouse=True)
def _reset_db() -> None:
    rss_sources.reset_storage()
    yield
    rss_sources.reset_storage()


@pytest.fixture()
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def export_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(export_jobs.settings, "export_output_dir", str(tmp_path))
    monkeypatch.setattr(task_queue.settings, "celery_task_always_eager", True)
    return tmp_path


def _seed_candidate_needs() -> tuple[int, list[int]]:
    source = rss_sources.create_source(
        {
            "name": "Tech",
            "url": "https://example.com/tech.xml",
            "frequency": 3600,
            "status": SourceStatus.ACTIVE,
        }
    )
    entry = raw_entries.create_entry(
        {
            "source_id": source.id,
            "guid": "entry-1",
            "title": "AI Ideas",
            "summary": "AI powered analytics",
            "published_at": datetime.now(UTC),
            "status": RawEntryStatus.PROMOTED,
        }
    )
    other_entry = raw_entries.create_entry(
        {
            "source_id": source.id,
            "guid": "entry-2",
            "title": "Product Ops",
            "summary": "Collaboration tooling",
            "published_at": datetime.now(UTC),
            "status": RawEntryStatus.FILTERED,
        }
    )
    needs = [
        candidate_needs.create_need(
            {
                "raw_entry_id": entry.id,
                "summary": "Analytics assistant",
                "problem_statement": "Hard to monitor usage trends",
                "target_users": "Product managers",
                "value_proposition": "自动化分析关键信号",
                "competition": "Spreadsheet",
                "confidence": 0.7,
                "rule_score": 0.82,
                "status": CandidateNeedStatus.PENDING_REVIEW,
                "notes": "High priority",
            }
        ),
        candidate_needs.create_need(
            {
                "raw_entry_id": other_entry.id,
                "summary": "Collaboration hub",
                "problem_statement": "Remote teams lack context",
                "target_users": "Startup teams",
                "value_proposition": "共享知识库",
                "competition": "Docs",
                "confidence": 0.5,
                "rule_score": 0.45,
                "status": CandidateNeedStatus.APPROVED,
            }
        ),
    ]
    return entry.id, [need.id for need in needs]


def test_create_and_list_candidate_needs(client: TestClient) -> None:
    entry_id, _ = _seed_candidate_needs()

    response = client.post(
        "/api/v1/candidate-needs",
        json={
            "raw_entry_id": entry_id,
            "summary": "Automation insights",
            "problem_statement": "Teams lack automation metrics",
            "status": CandidateNeedStatus.IN_DISCOVERY.value,
        },
    )
    assert response.status_code == 201
    created = response.json()
    assert created["status"] == CandidateNeedStatus.IN_DISCOVERY.value
    assert created["raw_entry_id"] == entry_id
    assert created["rule_score"] is None

    invalid = client.post(
        "/api/v1/candidate-needs",
        json={
            "raw_entry_id": 999,
            "summary": "Invalid",
        },
    )
    assert invalid.status_code == 400

    list_response = client.get(
        "/api/v1/candidate-needs",
        params={"statuses": [CandidateNeedStatus.APPROVED.value]},
    )
    assert list_response.status_code == 200
    body = list_response.json()
    assert body["total"] == 1
    assert body["items"][0]["status"] == CandidateNeedStatus.APPROVED.value
    assert body["items"][0]["rule_score"] == pytest.approx(0.45)

    search_response = client.get(
        "/api/v1/candidate-needs",
        params={"search": "assistant"},
    )
    assert search_response.status_code == 200
    search_body = search_response.json()
    assert search_body["total"] >= 1
    assert any("assistant" in item["summary"].lower() for item in search_body["items"])

    source_filter_response = client.get(
        "/api/v1/candidate-needs",
        params={"source_type": SourceType.RSS.value},
    )
    assert source_filter_response.status_code == 200
    source_filter_body = source_filter_response.json()
    assert source_filter_body["total"] == 3
    assert all(item["source_type"] == SourceType.RSS.value for item in source_filter_body["items"])
    assert all(item["source_name"] == "Tech" for item in source_filter_body["items"])


def test_update_candidate_need_and_status(client: TestClient) -> None:
    _, need_ids = _seed_candidate_needs()

    update_response = client.put(
        f"/api/v1/candidate-needs/{need_ids[0]}",
        json={
            "summary": "Analytics co-pilot",
            "status": CandidateNeedStatus.APPROVED.value,
            "notes": "Ready for review",
        },
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["summary"] == "Analytics co-pilot"
    assert updated["status"] == CandidateNeedStatus.APPROVED.value
    assert updated["notes"] == "Ready for review"

    status_response = client.put(
        f"/api/v1/candidate-needs/{need_ids[1]}/status",
        json={"status": CandidateNeedStatus.REJECTED.value},
    )
    assert status_response.status_code == 200
    status_body = status_response.json()
    assert status_body["status"] == CandidateNeedStatus.REJECTED.value

    missing = client.put(
        "/api/v1/candidate-needs/999/status",
        json={"status": CandidateNeedStatus.APPROVED.value},
    )
    assert missing.status_code == 404


def test_export_candidate_needs(client: TestClient) -> None:
    _seed_candidate_needs()

    json_export = client.get(
        "/api/v1/candidate-needs/export",
        params={"format": "json", "limit": 2},
    )
    assert json_export.status_code == 200
    data = json_export.json()
    assert data["format"] == "json"
    assert len(data["items"]) == 2
    assert data["items"][0]["rule_score"] is not None

    csv_export = client.get(
        "/api/v1/candidate-needs/export",
        params={"format": "csv", "limit": 2},
    )
    assert csv_export.status_code == 200
    csv_body = csv_export.json()
    assert csv_body["format"] == "csv"
    lines = [line for line in csv_body["content"].splitlines() if line]
    assert len(lines) >= 2
    assert "rule_score" in lines[0]


def test_sync_channel_stats(client: TestClient) -> None:
    _, need_ids = _seed_candidate_needs()
    sync_audit.log_sync_attempt(
        need_ids[0],
        channel=SyncChannel.WEBHOOK,
        status="success",
        attempt=1,
    )
    sync_audit.log_sync_attempt(
        need_ids[0],
        channel=SyncChannel.MQ,
        status="failed",
        attempt=2,
        message="mq-down",
    )
    sync_audit.log_sync_attempt(
        need_ids[1],
        channel=SyncChannel.FILE_DROP,
        status="failed",
        attempt=1,
        message="disk-full",
    )

    response = client.get(
        "/api/v1/candidate-needs/sync-stats",
        params={"limit": 10},
    )
    assert response.status_code == 200
    stats = {item["channel"]: item for item in response.json()}
    assert stats["webhook"]["success"] == 1
    assert stats["webhook"]["total_attempts"] == 1
    assert stats["mq"]["failed"] == 1
    assert stats["mq"]["last_error"] == "mq-down"
    assert stats["file_drop"]["failed"] == 1
    assert stats["file_drop"]["pending"] == 0
    assert stats["export"]["total_attempts"] == 0


def test_filter_candidate_needs_by_synced_status(client: TestClient) -> None:
    _, need_ids = _seed_candidate_needs()
    candidate_needs.mark_need_synced(need_ids[0])

    synced_response = client.get("/api/v1/candidate-needs", params={"synced": True})
    assert synced_response.status_code == 200
    synced_body = synced_response.json()
    assert synced_body["total"] == 1
    assert all(item["synced_at"] is not None for item in synced_body["items"])


def test_sync_logs_endpoint(client: TestClient) -> None:
    _, need_ids = _seed_candidate_needs()
    sync_audit.log_sync_attempt(
        need_ids[0],
        channel=SyncChannel.WEBHOOK,
        status="success",
        attempt=1,
        metadata={"status_code": 200},
    )

    response = client.get(f"/api/v1/candidate-needs/{need_ids[0]}/sync-logs")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["channel"] == SyncChannel.WEBHOOK.value
    assert body[0]["metadata"]["status_code"] == 200


def test_recent_sync_logs_listing(client: TestClient) -> None:
    _, need_ids = _seed_candidate_needs()
    sync_audit.log_sync_attempt(
        need_ids[0],
        channel=SyncChannel.WEBHOOK,
        status="failed",
        attempt=2,
        message="timeout",
    )
    sync_audit.log_sync_attempt(
        need_ids[1],
        channel=SyncChannel.MQ,
        status="success",
        attempt=1,
    )

    listing = client.get("/api/v1/candidate-needs/sync-logs", params={"limit": 5})
    assert listing.status_code == 200
    payload = listing.json()
    assert payload["total"] == 2
    assert {item["channel"] for item in payload["items"]} == {
        SyncChannel.WEBHOOK.value,
        SyncChannel.MQ.value,
    }

    filtered = client.get(
        "/api/v1/candidate-needs/sync-logs",
        params={"channel": SyncChannel.WEBHOOK.value},
    )
    assert filtered.status_code == 200
    filtered_body = filtered.json()
    assert filtered_body["total"] == 1
    assert filtered_body["items"][0]["need_id"] == need_ids[0]


def test_export_task_lifecycle(client: TestClient, export_dir: Path) -> None:
    _seed_candidate_needs()

    create = client.post(
        "/api/v1/candidate-needs/export-tasks",
        json={"format": "json", "limit": 2},
    )
    assert create.status_code == 202
    job_body = create.json()
    job_id = job_body["id"]
    assert job_body["status"] == ExportJobStatus.PENDING.value

    completed = export_jobs.run_candidate_export_job(job_id)
    assert completed.status == ExportJobStatus.COMPLETED

    status_resp = client.get(f"/api/v1/candidate-needs/export-tasks/{job_id}")
    assert status_resp.status_code == 200
    status_body = status_resp.json()
    assert status_body["status"] == ExportJobStatus.COMPLETED.value
    assert Path(status_body["file_path"]).exists()

    unsynced_response = client.get("/api/v1/candidate-needs", params={"synced": False})
    assert unsynced_response.status_code == 200
    unsynced_body = unsynced_response.json()
    assert unsynced_body["total"] == 2
    assert all(item["synced_at"] is None for item in unsynced_body["items"])


def test_export_job_creates_audit_logs(client: TestClient, export_dir: Path) -> None:
    _, need_ids = _seed_candidate_needs()
    response = client.post(
        "/api/v1/candidate-needs/export-tasks",
        json={"format": "csv", "limit": len(need_ids)},
    )
    assert response.status_code == 202
    job_id = response.json()["id"]

    export_jobs.run_candidate_export_job(job_id)

    logs = sync_audit.list_logs(channel=SyncChannel.EXPORT)
    assert len(logs) == len(need_ids)
    assert all(log.channel == SyncChannel.EXPORT for log in logs)
    assert all(log.metadata.get("job_id") == job_id for log in logs)


def test_list_export_tasks_endpoint(
    client: TestClient, export_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_candidate_needs()

    first = client.post(
        "/api/v1/candidate-needs/export-tasks",
        json={"format": "csv", "limit": 5},
    )
    assert first.status_code == 202
    completed_id = first.json()["id"]
    export_jobs.run_candidate_export_job(completed_id)

    original_enqueue = task_queue.enqueue_export_job

    def _noop(job_id: int) -> None:  # pragma: no cover - 测试替身
        return None

    monkeypatch.setattr(task_queue, "enqueue_export_job", _noop)
    second = client.post(
        "/api/v1/candidate-needs/export-tasks",
        json={"format": "json", "limit": 1},
    )
    assert second.status_code == 202
    monkeypatch.setattr(task_queue, "enqueue_export_job", original_enqueue)

    listing = client.get(
        "/api/v1/candidate-needs/export-tasks",
        params={"limit": 10},
    )
    assert listing.status_code == 200
    body = listing.json()
    assert body["total"] == 2
    statuses = {item["status"] for item in body["items"]}
    assert ExportJobStatus.COMPLETED.value in statuses
    assert ExportJobStatus.PENDING.value in statuses

    filtered = client.get(
        "/api/v1/candidate-needs/export-tasks",
        params={"status": ExportJobStatus.COMPLETED.value},
    )
    assert filtered.status_code == 200
    filtered_body = filtered.json()
    assert filtered_body["total"] == 1
    assert filtered_body["items"][0]["status"] == ExportJobStatus.COMPLETED.value


def test_candidate_need_status_logs_api(client: TestClient) -> None:
    _, need_ids = _seed_candidate_needs()

    update_response = client.put(
        f"/api/v1/candidate-needs/{need_ids[0]}/status",
        json={"status": CandidateNeedStatus.APPROVED.value},
    )
    assert update_response.status_code == 200

    logs_response = client.get(
        f"/api/v1/candidate-needs/{need_ids[0]}/status-logs"
    )
    assert logs_response.status_code == 200
    logs = logs_response.json()
    assert len(logs) >= 2
    assert logs[0]["to_status"] == CandidateNeedStatus.PENDING_REVIEW.value
    assert logs[-1]["to_status"] == CandidateNeedStatus.APPROVED.value

    missing = client.get("/api/v1/candidate-needs/999/status-logs")
    assert missing.status_code == 404

    export_response = client.get(
        "/api/v1/candidate-needs/export",
        params={"format": "json", "synced": False},
    )
    assert export_response.status_code == 200
    export_body = export_response.json()
    assert export_body["format"] == "json"
    assert export_body["items"]
    assert all(item["synced_at"] is None for item in export_body["items"])


def test_candidate_need_status_transition_validation(client: TestClient) -> None:
    _, need_ids = _seed_candidate_needs()
    target_id = need_ids[0]

    invalid = client.put(
        f"/api/v1/candidate-needs/{target_id}/status",
        json={"status": CandidateNeedStatus.COMPLETED.value},
    )
    assert invalid.status_code == 400
    assert "无法流转" in invalid.json()["detail"]

    approve = client.put(
        f"/api/v1/candidate-needs/{target_id}/status",
        json={"status": CandidateNeedStatus.APPROVED.value},
    )
    assert approve.status_code == 200

    discovery = client.put(
        f"/api/v1/candidate-needs/{target_id}/status",
        json={"status": CandidateNeedStatus.IN_DISCOVERY.value},
    )
    assert discovery.status_code == 200

    completed = client.put(
        f"/api/v1/candidate-needs/{target_id}/status",
        json={"status": CandidateNeedStatus.COMPLETED.value},
    )
    assert completed.status_code == 200

    reopen = client.put(
        f"/api/v1/candidate-needs/{target_id}/status",
        json={"status": CandidateNeedStatus.PENDING_REVIEW.value},
    )
    assert reopen.status_code == 400


def _seed_cluster_candidates() -> None:
    rss_source = rss_sources.create_source(
        {
            "name": "RSS Feed",
            "url": "https://example.com/issues.xml",
            "frequency": 3600,
            "source_type": SourceType.RSS,
        }
    )
    github_source = rss_sources.create_source(
        {
            "name": "GitHub Repo Issues",
            "url": "https://api.github.com/repos/acme/needradar/issues",
            "frequency": 1800,
            "source_type": SourceType.GITHUB_ISSUES,
        }
    )
    hn_source = rss_sources.create_source(
        {
            "name": "Ask HN",
            "url": "https://hacker-news.firebaseio.com/v0/askstories.json",
            "frequency": 900,
            "source_type": SourceType.HACKER_NEWS,
        }
    )

    first_entry = raw_entries.create_entry(
        {
            "source_id": rss_source.id,
            "guid": "rss-issue-triage",
            "title": "Manual issue triage for engineering teams",
            "summary": "Teams still triage inbound issues manually",
            "status": RawEntryStatus.PROMOTED,
        }
    )
    second_entry = raw_entries.create_entry(
        {
            "source_id": github_source.id,
            "guid": "gh-issue-triage",
            "title": "Need faster GitHub issue triage",
            "summary": "Engineering teams process issue queues manually",
            "status": RawEntryStatus.PROMOTED,
        }
    )
    third_entry = raw_entries.create_entry(
        {
            "source_id": hn_source.id,
            "guid": "hn-podcast-clips",
            "title": "Podcast clip generator",
            "summary": "Create short video clips from long podcasts",
            "status": RawEntryStatus.PROMOTED,
        }
    )

    candidate_needs.create_need(
        {
            "raw_entry_id": first_entry.id,
            "summary": "Issue triage assistant for engineering teams",
            "problem_statement": "Engineering teams manually triage inbound issues every day",
            "confidence": 0.82,
            "rule_score": 0.76,
            "status": CandidateNeedStatus.APPROVED,
        }
    )
    candidate_needs.create_need(
        {
            "raw_entry_id": second_entry.id,
            "summary": "Engineering issue triage copilot",
            "problem_statement": "Teams process GitHub issues manually and lose context",
            "confidence": 0.78,
            "rule_score": 0.73,
            "status": CandidateNeedStatus.PENDING_REVIEW,
        }
    )
    candidate_needs.create_need(
        {
            "raw_entry_id": third_entry.id,
            "summary": "Podcast clip maker",
            "problem_statement": "Creators need highlight clips from long-form audio",
            "confidence": 0.61,
            "rule_score": 0.58,
            "status": CandidateNeedStatus.PENDING_REVIEW,
        }
    )


def _seed_signal_cluster_candidates() -> None:
    reddit_source = rss_sources.create_source(
        {
            "name": "Reddit Comments",
            "url": "https://www.reddit.com/r/sideproject/comments",
            "frequency": 900,
            "source_type": SourceType.REDDIT,
        }
    )
    github_source = rss_sources.create_source(
        {
            "name": "GitHub Repo Issues",
            "url": "https://api.github.com/repos/acme/needradar/issues",
            "frequency": 1800,
            "source_type": SourceType.GITHUB_ISSUES,
        }
    )

    reddit_entry = raw_entries.create_entry(
        {
            "source_id": reddit_source.id,
            "guid": "reddit-comment-1",
            "title": "Comment on Manual customer support workflows",
            "summary": "still manually copying customer emails into notion",
            "content": (
                "This is so annoying and tedious. Looking for a better tool to "
                "replace our manual customer support workflow."
            ),
            "tags": [
                "reddit",
                "reddit_comment",
                "complaint_signal",
                "alternative_request",
            ],
            "status": RawEntryStatus.PROMOTED,
        }
    )
    github_entry = raw_entries.create_entry(
        {
            "source_id": github_source.id,
            "guid": "gh-support-automation",
            "title": "Support queue automation for small teams",
            "summary": "Small teams still triage support requests manually",
            "status": RawEntryStatus.PROMOTED,
        }
    )

    candidate_needs.create_need(
        {
            "raw_entry_id": reddit_entry.id,
            "summary": "Automation for manual customer support triage",
            "problem_statement": "Small teams still copy support requests by hand every day",
            "confidence": 0.88,
            "rule_score": 0.92,
            "status": CandidateNeedStatus.PENDING_REVIEW,
        }
    )
    candidate_needs.create_need(
        {
            "raw_entry_id": github_entry.id,
            "summary": "Customer support triage copilot",
            "problem_statement": "Support teams manually route and summarize incoming requests",
            "confidence": 0.74,
            "rule_score": 0.69,
            "status": CandidateNeedStatus.APPROVED,
        }
    )


def test_candidate_clusters_service() -> None:
    _seed_cluster_candidates()

    clusters = candidate_clusters.summarize_clusters(limit=20, min_cluster_size=2)

    assert len(clusters) == 1
    cluster = clusters[0]
    assert cluster.signal_count == 2
    assert cluster.cross_source is True
    assert cluster.source_count == 2
    assert "RSS Feed" in cluster.source_names
    assert "GitHub Repo Issues" in cluster.source_names
    assert SourceType.RSS.value in cluster.source_types
    assert SourceType.GITHUB_ISSUES.value in cluster.source_types


def test_candidate_clusters_api(client: TestClient) -> None:
    _seed_cluster_candidates()

    response = client.get(
        "/api/v1/candidate-needs/clusters",
        params={"limit": 20, "min_cluster_size": 2},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["total"] == 1
    cluster = body["items"][0]
    assert cluster["signal_count"] == 2
    assert cluster["cross_source"] is True
    assert cluster["source_count"] == 2
    assert SourceType.GITHUB_ISSUES.value in cluster["source_types"]


def test_candidate_clusters_prioritize_complaint_and_alternative_signals() -> None:
    _seed_signal_cluster_candidates()

    clusters = candidate_clusters.summarize_clusters(limit=20, min_cluster_size=2)

    assert len(clusters) == 1
    cluster = clusters[0]
    assert cluster.complaint_signal_count == 1
    assert cluster.alternative_request_count == 1
    assert cluster.reddit_comment_count == 1
    assert cluster.priority_score > 0.5


def test_candidate_clusters_api_exposes_signal_counts(client: TestClient) -> None:
    _seed_signal_cluster_candidates()

    response = client.get(
        "/api/v1/candidate-needs/clusters",
        params={"limit": 20, "min_cluster_size": 2},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["total"] == 1
    cluster = body["items"][0]
    assert cluster["complaint_signal_count"] == 1
    assert cluster["alternative_request_count"] == 1
    assert cluster["reddit_comment_count"] == 1
    assert cluster["priority_score"] > 0.5


def test_candidate_clusters_skip_generic_false_positive_overlap() -> None:
    source_a = rss_sources.create_source(
        {
            "name": "Ask HN",
            "url": "https://news.ycombinator.com/ask",
            "frequency": 900,
            "source_type": SourceType.HACKER_NEWS,
        }
    )
    source_b = rss_sources.create_source(
        {
            "name": "ERP Blog",
            "url": "https://example.com/erp.xml",
            "frequency": 3600,
            "source_type": SourceType.RSS,
        }
    )
    entry_a = raw_entries.create_entry(
        {
            "source_id": source_a.id,
            "guid": "ask-hn-saas",
            "title": "Ask HN: Can anyone suggest me a SaaS product idea?",
            "summary": "Looking for a good SaaS idea to build.",
            "status": RawEntryStatus.PROMOTED,
        }
    )
    entry_b = raw_entries.create_entry(
        {
            "source_id": source_b.id,
            "guid": "erp-offline",
            "title": "Offline ERP resilience for global businesses",
            "summary": "Cloud ERP systems need continuity when connectivity is unavailable.",
            "status": RawEntryStatus.PROMOTED,
        }
    )
    candidate_needs.create_need(
        {
            "raw_entry_id": entry_a.id,
            "summary": "Ask HN: Can anyone suggest me a SaaS product idea?",
            "status": CandidateNeedStatus.PENDING_REVIEW,
            "rule_score": 0.53,
        }
    )
    candidate_needs.create_need(
        {
            "raw_entry_id": entry_b.id,
            "summary": "Offline ERP resilience for global businesses",
            "status": CandidateNeedStatus.PENDING_REVIEW,
            "rule_score": 0.35,
        }
    )

    clusters = candidate_clusters.summarize_clusters(limit=20, min_cluster_size=2)

    assert clusters == []


def test_candidate_clusters_skip_cross_source_github_bug_false_positive_overlap() -> None:
    rss_source = rss_sources.create_source(
        {
            "name": "DEV SaaS Feed",
            "url": "https://dev.to/feed/saas",
            "frequency": 1800,
            "source_type": SourceType.RSS,
        }
    )
    github_source = rss_sources.create_source(
        {
            "name": "Supabase Issues",
            "url": "https://api.github.com/repos/supabase/supabase/issues",
            "frequency": 1800,
            "source_type": SourceType.GITHUB_ISSUES,
        }
    )
    rss_entry = raw_entries.create_entry(
        {
            "source_id": rss_source.id,
            "guid": "switching-calendly",
            "title": "Switching from Calendly to a lighter scheduling stack",
            "summary": "Ops teams want a simpler alternative with fewer integration headaches.",
            "status": RawEntryStatus.PROMOTED,
        }
    )
    github_entry = raw_entries.create_entry(
        {
            "source_id": github_source.id,
            "guid": "ssl-cert-invalid",
            "title": "ERR_CERT_AUTHORITY_INVALID — SSL certificate invalid on project",
            "summary": "Self-hosted project remains stuck behind an invalid certificate error.",
            "status": RawEntryStatus.PROMOTED,
        }
    )
    candidate_needs.create_need(
        {
            "raw_entry_id": rss_entry.id,
            "summary": "Calendly alternative for lean ops teams",
            "problem_statement": "Teams want a simpler scheduling stack without extra integration overhead.",
            "status": CandidateNeedStatus.PENDING_REVIEW,
            "rule_score": 0.61,
        }
    )
    candidate_needs.create_need(
        {
            "raw_entry_id": github_entry.id,
            "summary": "SSL certificate invalid on self-hosted project",
            "problem_statement": "Self-hosted projects get stuck behind invalid certificate failures.",
            "status": CandidateNeedStatus.PENDING_REVIEW,
            "rule_score": 0.73,
        }
    )

    clusters = candidate_clusters.summarize_clusters(limit=20, min_cluster_size=2)

    assert clusters == []


def test_candidate_clusters_can_filter_by_source_type(client: TestClient) -> None:
    _seed_cluster_candidates()

    response = client.get(
        "/api/v1/candidate-needs/clusters",
        params={
            "limit": 20,
            "min_cluster_size": 2,
            "source_type": SourceType.GITHUB_ISSUES.value,
        },
    )
    assert response.status_code == 200
    body = response.json()

    assert body["total"] == 0
