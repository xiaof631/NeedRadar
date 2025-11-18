from __future__ import annotations

import pathlib

import pytest

from app.db.storage import db
from app.models import CandidateNeedStatus, RawEntryStatus, SourceStatus, SyncChannel
from app.services import candidate_needs, raw_entries, rss_sources
from jobs import task_queue


@pytest.fixture(autouse=True)
def _reset_db() -> None:
    db.reset()
    yield
    db.reset()


def test_enqueue_fetch_sources_only_targets_active(monkeypatch: pytest.MonkeyPatch) -> None:
    active = rss_sources.create_source(
        {"name": "Active", "url": "https://example.com/a", "frequency": 3600}
    )
    rss_sources.create_source(
        {
            "name": "Paused",
            "url": "https://example.com/b",
            "frequency": 3600,
            "status": SourceStatus.PAUSED,
        }
    )

    queued: list[int] = []

    def _fake_fetch_delay(source_id: int) -> None:
        queued.append(source_id)

    monkeypatch.setattr(task_queue.fetch_rss_source_task, "delay", _fake_fetch_delay)

    queued_count = task_queue.enqueue_fetch_sources()

    assert queued_count == 1
    assert queued == [active.id]


def test_enqueue_promotions_filters_pending_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    pending = raw_entries.create_entry(
        {
            "source_id": 1,
            "guid": "guid-1",
            "title": "Alpha",
            "status": RawEntryStatus.PENDING,
        }
    )
    raw_entries.create_entry(
        {
            "source_id": 1,
            "guid": "guid-2",
            "title": "Beta",
            "status": RawEntryStatus.IGNORED,
        }
    )

    queued: list[tuple[int, float | None]] = []

    def _fake_delay(entry_id: int, min_score: float | None) -> None:
        queued.append((entry_id, min_score))

    monkeypatch.setattr(task_queue.promote_entry_task, "delay", _fake_delay)

    queued_count = task_queue.enqueue_promotions(batch_size=5, min_score=0.8)

    assert queued_count == 1
    assert queued == [(pending.id, 0.8)]


def _seed_need(status: CandidateNeedStatus) -> int:
    source = rss_sources.create_source(
        {
            "name": f"Source-{status.value}",
            "url": f"https://example.com/rss-{status.value}",
            "frequency": 3600,
        }
    )
    entry = raw_entries.create_entry(
        {
            "source_id": source.id,
            "guid": f"{status.value}-guid",
            "title": f"Need entry {status.value}",
            "status": RawEntryStatus.PROMOTED,
        }
    )
    need = candidate_needs.create_need(
        {
            "raw_entry_id": entry.id,
            "summary": f"Need-{status.value}",
            "status": status,
        }
    )
    return need.id


def test_enqueue_sync_tasks_skips_without_webhook(monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_need(CandidateNeedStatus.APPROVED)

    called: list[int] = []

    def _fake_sync_delay(*_: object) -> None:
        called.append(1)

    monkeypatch.setattr(task_queue.sync_candidate_need_task, "delay", _fake_sync_delay)

    queued_count = task_queue.enqueue_sync_tasks(
        webhook_url=None,
        statuses=(CandidateNeedStatus.APPROVED,),
        batch_size=10,
    )

    assert queued_count == 0
    assert called == []


def test_enqueue_sync_tasks_respects_status_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    approved_id = _seed_need(CandidateNeedStatus.APPROVED)
    _seed_need(CandidateNeedStatus.PENDING_REVIEW)

    queued: list[tuple[int, str]] = []

    def _fake_sync_delay(need_id: int, webhook_url: str) -> None:
        queued.append((need_id, webhook_url))

    monkeypatch.setattr(task_queue.sync_candidate_need_task, "delay", _fake_sync_delay)

    queued_count = task_queue.enqueue_sync_tasks(
        webhook_url="https://webhook.example.com",
        statuses=(CandidateNeedStatus.APPROVED,),
        batch_size=10,
    )

    assert queued_count == 1
    assert queued == [(approved_id, "https://webhook.example.com")]


def test_enqueue_sync_tasks_dispatches_mq(monkeypatch: pytest.MonkeyPatch) -> None:
    need_id = _seed_need(CandidateNeedStatus.APPROVED)

    monkeypatch.setattr(task_queue.settings, "downstream_mq_enabled", True)

    webhook_calls: list[int] = []
    mq_calls: list[int] = []

    def _fake_sync_delay(target_need_id: int, webhook_url: str) -> None:
        webhook_calls.append(target_need_id)

    def _fake_mq_delay(target_need_id: int) -> None:
        mq_calls.append(target_need_id)

    monkeypatch.setattr(task_queue.sync_candidate_need_task, "delay", _fake_sync_delay)
    monkeypatch.setattr(task_queue.publish_candidate_need_mq_task, "delay", _fake_mq_delay)

    queued = task_queue.enqueue_sync_tasks(
        webhook_url="https://hook.example.com",
        statuses=(CandidateNeedStatus.APPROVED,),
        batch_size=5,
    )

    assert queued == 1
    assert webhook_calls == [need_id]
    assert mq_calls == [need_id]


def test_enqueue_sync_tasks_dispatches_file_drop(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    need_id = _seed_need(CandidateNeedStatus.APPROVED)

    monkeypatch.setattr(task_queue.settings, "downstream_filesystem_enabled", True)
    monkeypatch.setattr(task_queue.settings, "downstream_filesystem_dir", str(tmp_path))
    monkeypatch.setattr(task_queue.settings, "downstream_filesystem_format", "json")

    file_calls: list[int] = []

    def _fake_file_delay(target_need_id: int) -> None:
        file_calls.append(target_need_id)

    monkeypatch.setattr(
        task_queue.write_candidate_need_file_drop_task,
        "delay",
        _fake_file_delay,
    )

    queued = task_queue.enqueue_sync_tasks(
        webhook_url=None,
        statuses=(CandidateNeedStatus.APPROVED,),
        batch_size=5,
    )

    assert queued == 1
    assert file_calls == [need_id]


def test_enqueue_sync_tasks_respects_channel_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    need_id = _seed_need(CandidateNeedStatus.APPROVED)

    monkeypatch.setattr(task_queue.settings, "downstream_mq_enabled", True)
    monkeypatch.setattr(task_queue.settings, "downstream_filesystem_enabled", True)
    monkeypatch.setattr(task_queue.settings, "downstream_webhook_url", "https://hook")

    webhook_calls: list[int] = []
    mq_calls: list[int] = []
    file_calls: list[int] = []

    monkeypatch.setattr(task_queue.sync_candidate_need_task, "delay", lambda *args: webhook_calls.append(args[0]))
    monkeypatch.setattr(task_queue.publish_candidate_need_mq_task, "delay", lambda need_id: mq_calls.append(need_id))
    monkeypatch.setattr(
        task_queue.write_candidate_need_file_drop_task,
        "delay",
        lambda need_id: file_calls.append(need_id),
    )

    queued = task_queue.enqueue_sync_tasks(
        webhook_url="https://hook",
        statuses=(CandidateNeedStatus.APPROVED,),
        batch_size=5,
        channels=(SyncChannel.MQ,),
    )

    assert queued == 1
    assert webhook_calls == []
    assert mq_calls == [need_id]
    assert file_calls == []
