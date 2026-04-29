from __future__ import annotations

import pytest

from app.db.storage import db
from app.models import CandidateNeedStatus, RawEntryStatus, SyncChannel
from app.services import candidate_needs, downstream_metrics, raw_entries, rss_sources, sync_audit
from app.services.downstream_metrics import SyncChannelStats


@pytest.fixture(autouse=True)
def _reset_db() -> None:
    db.reset()
    yield
    db.reset()


def _seed_data() -> list[int]:
    source = rss_sources.create_source(
        {"name": "MetricsSource", "url": "https://example.com/rss", "frequency": 3600}
    )
    entry = raw_entries.create_entry(
        {
            "source_id": source.id,
            "guid": "metrics-guid",
            "title": "Metrics entry",
            "status": RawEntryStatus.PROMOTED,
        }
    )
    need = candidate_needs.create_need(
        {
            "raw_entry_id": entry.id,
            "summary": "Metrics need",
            "status": CandidateNeedStatus.APPROVED,
        }
    )
    return [need.id]


def test_sync_channel_stats_defaults() -> None:
    stats = SyncChannelStats(channel=SyncChannel.WEBHOOK)
    assert stats.channel == SyncChannel.WEBHOOK
    assert stats.total_attempts == 0
    assert stats.success == 0
    assert stats.failed == 0
    assert stats.last_attempt_at is None
    assert stats.last_error is None
    assert stats.pending == 0
    assert stats.success_rate == 0.0


def test_sync_channel_stats_pending() -> None:
    stats = SyncChannelStats(channel=SyncChannel.MQ, total_attempts=10, success=6, failed=3)
    assert stats.pending == 1


def test_sync_channel_stats_success_rate() -> None:
    stats = SyncChannelStats(channel=SyncChannel.WEBHOOK, total_attempts=10, success=7, failed=3)
    assert stats.success_rate == 0.7


def test_summarize_recent_sync_logs_empty_when_limit_zero_or_negative() -> None:
    _seed_data()
    sync_audit.log_sync_attempt(
        candidate_needs.list_needs(limit=1)[1][0].id,
        channel=SyncChannel.WEBHOOK,
        status="success",
        attempt=1,
    )
    assert downstream_metrics.summarize_recent_sync_logs(limit=0) == []
    assert downstream_metrics.summarize_recent_sync_logs(limit=-1) == []


def test_summarize_recent_sync_logs_aggregates_correctly() -> None:
    need_ids = _seed_data()
    need_id = need_ids[0]

    sync_audit.log_sync_attempt(need_id, channel=SyncChannel.WEBHOOK, status="success", attempt=1)
    sync_audit.log_sync_attempt(need_id, channel=SyncChannel.MQ, status="failed", attempt=2, message="mq-down")
    sync_audit.log_sync_attempt(need_id, channel=SyncChannel.WEBHOOK, status="failed", attempt=3, message="timeout")

    stats_list = downstream_metrics.summarize_recent_sync_logs(limit=10)
    stats_by_channel = {s.channel: s for s in stats_list}

    assert stats_by_channel[SyncChannel.WEBHOOK].total_attempts == 2
    assert stats_by_channel[SyncChannel.WEBHOOK].success == 1
    assert stats_by_channel[SyncChannel.WEBHOOK].failed == 1
    assert stats_by_channel[SyncChannel.WEBHOOK].last_error == "timeout"
    assert stats_by_channel[SyncChannel.MQ].total_attempts == 1
    assert stats_by_channel[SyncChannel.MQ].failed == 1
    assert stats_by_channel[SyncChannel.MQ].last_error == "mq-down"
    # Channels with no logs should still appear
    assert SyncChannel.FILE_DROP in stats_by_channel
    assert stats_by_channel[SyncChannel.FILE_DROP].total_attempts == 0


def test_summarize_recent_sync_logs_caps_last_error_on_failure_only() -> None:
    need_ids = _seed_data()
    need_id = need_ids[0]

    sync_audit.log_sync_attempt(need_id, channel=SyncChannel.WEBHOOK, status="success", attempt=1)
    sync_audit.log_sync_attempt(need_id, channel=SyncChannel.WEBHOOK, status="failed", attempt=2, message="first-error")
    sync_audit.log_sync_attempt(need_id, channel=SyncChannel.WEBHOOK, status="success", attempt=3)

    stats_list = downstream_metrics.summarize_recent_sync_logs(limit=10)
    webhook_stats = next(s for s in stats_list if s.channel == SyncChannel.WEBHOOK)
    # last_error should still be from the last failure, not cleared by success
    assert webhook_stats.last_error == "first-error"
    assert webhook_stats.total_attempts == 3
    assert webhook_stats.success == 2
    assert webhook_stats.failed == 1
