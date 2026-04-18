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
