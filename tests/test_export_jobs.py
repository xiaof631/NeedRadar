import json
from pathlib import Path

import pytest

import app.services.export_jobs as export_jobs
from app.db.storage import db
from app.models import CandidateNeedStatus, ExportJobStatus, RawEntryStatus
from app.services import candidate_needs, raw_entries, rss_sources


@pytest.fixture(autouse=True)
def _reset_db() -> None:
    db.reset()
    yield
    db.reset()


@pytest.fixture()
def _override_export_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(export_jobs.settings, "export_output_dir", str(tmp_path))
    return tmp_path


def _seed_need() -> None:
    source = rss_sources.create_source(
        {"name": "Seed", "url": "https://example.com/rss", "frequency": 3600}
    )
    entry = raw_entries.create_entry(
        {
            "source_id": source.id,
            "guid": "seed-guid",
            "title": "Seed entry",
            "status": RawEntryStatus.PROMOTED,
        }
    )
    candidate_needs.create_need(
        {
            "raw_entry_id": entry.id,
            "summary": "Demo need",
            "status": CandidateNeedStatus.APPROVED,
        }
    )


def test_run_candidate_export_job_generates_file(
    _override_export_dir: Path,
) -> None:
    _seed_need()

    job = export_jobs.create_candidate_export_job(format="json")
    completed = export_jobs.run_candidate_export_job(job.id)

    assert completed.status == ExportJobStatus.COMPLETED
    assert completed.file_path is not None
    payload = json.loads(Path(completed.file_path).read_text(encoding="utf-8"))
    assert isinstance(payload, list)
    assert payload and payload[0]["summary"] == "Demo need"


def test_run_candidate_export_job_csv_format(_override_export_dir: Path) -> None:
    _seed_need()

    job = export_jobs.create_candidate_export_job(format="csv")
    completed = export_jobs.run_candidate_export_job(job.id)

    assert completed.status == ExportJobStatus.COMPLETED
    assert completed.file_path is not None
    content = Path(completed.file_path).read_text(encoding="utf-8")
    lines = [line for line in content.splitlines() if line]
    assert len(lines) >= 2
    assert "summary" in lines[0]


def test_run_candidate_export_job_handles_missing_job() -> None:
    with pytest.raises(export_jobs.ExportJobNotFoundError):
        export_jobs.run_candidate_export_job(999)


def test_get_export_job_not_found() -> None:
    with pytest.raises(export_jobs.ExportJobNotFoundError):
        export_jobs.get_export_job(999)


def test_list_candidate_export_jobs_with_status_filter(_override_export_dir: Path) -> None:
    _seed_need()

    job = export_jobs.create_candidate_export_job(format="json")
    export_jobs.run_candidate_export_job(job.id)

    all_jobs = export_jobs.list_candidate_export_jobs(limit=50)
    assert len(all_jobs) == 1

    pending_only = export_jobs.list_candidate_export_jobs(status=ExportJobStatus.PENDING, limit=50)
    assert len(pending_only) == 0

    completed_only = export_jobs.list_candidate_export_jobs(status=ExportJobStatus.COMPLETED, limit=50)
    assert len(completed_only) == 1


def test_create_candidate_export_job_with_filters() -> None:
    _seed_need()

    job = export_jobs.create_candidate_export_job(
        format="json",
        statuses=[CandidateNeedStatus.APPROVED],
        search="Metrics",
        limit=5,
    )
    assert job.format == "json"
    assert job.status == ExportJobStatus.PENDING
    assert job.record_count is None
