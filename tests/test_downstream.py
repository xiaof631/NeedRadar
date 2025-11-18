import pytest

from app.db.storage import db
from app.models import CandidateNeedStatus, RawEntryStatus, SyncChannel
from app.services import candidate_needs, downstream, raw_entries, rss_sources, sync_audit


@pytest.fixture(autouse=True)
def _reset_db() -> None:
    db.reset()
    yield
    db.reset()


def _seed_need() -> int:
    source = rss_sources.create_source(
        {"name": "FileDrop", "url": "https://example.com/rss", "frequency": 3600}
    )
    entry = raw_entries.create_entry(
        {
            "source_id": source.id,
            "guid": "seed-guid",
            "title": "Need",
            "status": RawEntryStatus.PROMOTED,
        }
    )
    need = candidate_needs.create_need(
        {
            "raw_entry_id": entry.id,
            "summary": "Need summary",
            "status": CandidateNeedStatus.APPROVED,
        }
    )
    return need.id


def test_write_need_to_file_drop_success(tmp_path_factory: pytest.TempPathFactory) -> None:
    need_id = _seed_need()
    need = candidate_needs.get_need(need_id)

    result = downstream.write_need_to_file_drop(
        need,
        directory=str(tmp_path_factory.mktemp("file-drop")),
        file_format="json",
        attempt=2,
    )

    assert result.success is True
    assert result.channel == SyncChannel.FILE_DROP
    assert result.metadata is not None
    file_path = result.metadata["file_path"]

    refreshed = candidate_needs.get_need(need_id)
    assert refreshed.synced_at is not None
    logs = sync_audit.list_logs(channel=SyncChannel.FILE_DROP, limit=1)
    assert logs[0].status == "success"
    assert logs[0].metadata["file_path"] == file_path


def test_write_need_to_file_drop_handles_error(tmp_path_factory: pytest.TempPathFactory) -> None:
    need_id = _seed_need()
    need = candidate_needs.get_need(need_id)
    locked_path = tmp_path_factory.mktemp("locked")
    # 创建一个与目录重名的文件以触发写入错误
    target = locked_path / "occupied"
    target.write_text("blocked")

    result = downstream.write_need_to_file_drop(
        need,
        directory=str(target),
        file_format="json",
    )

    assert result.success is False
    logs = sync_audit.list_logs(channel=SyncChannel.FILE_DROP, limit=1)
    assert logs[0].status == "failed"
    assert "blocked" in logs[0].message or logs[0].message is not None
