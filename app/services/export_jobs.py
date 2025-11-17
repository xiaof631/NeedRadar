"""候选需求导出任务调度。"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence, Tuple

from app.core import metrics
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.storage import db
from app.models import CandidateNeedStatus, ExportJob, ExportJobStatus, SyncChannel
from app.schemas import CandidateNeedRead
from app.services import candidate_needs, sync_audit

logger = get_logger(__name__)
settings = get_settings()


class ExportJobNotFoundError(Exception):
    """导出任务不存在。"""


_CANDIDATE_JOB_TYPE = "candidate_needs"


def create_candidate_export_job(
    *,
    format: str,
    statuses: Iterable[CandidateNeedStatus] | None = None,
    search: str | None = None,
    raw_entry_id: int | None = None,
    synced: bool | None = None,
    limit: int | None = None,
) -> ExportJob:
    """创建候选需求导出任务记录。"""

    filters: dict[str, Any] = {
        "statuses": [status.value for status in statuses] if statuses else None,
        "search": search,
        "raw_entry_id": raw_entry_id,
        "synced": synced,
        "limit": limit,
    }
    return db.create_export_job(
        {
            "job_type": _CANDIDATE_JOB_TYPE,
            "format": format,
            "status": ExportJobStatus.PENDING,
            "filters": filters,
        }
    )


def get_export_job(job_id: int) -> ExportJob:
    """获取导出任务详情。"""

    job = db.get_export_job(job_id)
    if job is None:
        raise ExportJobNotFoundError
    return job


def list_candidate_export_jobs(
    *, status: ExportJobStatus | None = None, limit: int | None = None
) -> list[ExportJob]:
    """列出候选需求导出任务。"""

    return db.list_export_jobs(
        job_type=_CANDIDATE_JOB_TYPE,
        status=status,
        limit=limit,
    )


def run_candidate_export_job(job_id: int) -> ExportJob:
    """执行导出任务并将结果写入文件。"""

    job = get_export_job(job_id)
    if job.job_type != _CANDIDATE_JOB_TYPE:
        raise ValueError("Unsupported export job type")
    if job.status in {ExportJobStatus.COMPLETED, ExportJobStatus.FAILED}:
        return job

    def _mark_running(model: ExportJob) -> None:
        model.status = ExportJobStatus.RUNNING
        model.started_at = datetime.now(UTC)
        model.attempt_count += 1

    job = db.update_export_job(job_id, _mark_running)
    try:
        rendered, models = _render_candidates(job)
    except Exception as exc:  # pragma: no cover - 兜底
        logger.exception("export-job.render.failed", job_id=job_id)
        job = db.update_export_job(
            job_id,
            lambda model: _mark_failed(model, str(exc)),
        )
        metrics.record_export_job_result(ExportJobStatus.FAILED.value)
        return job

    output_path = _write_export_file(job, rendered)
    job = db.update_export_job(
        job_id,
        lambda model: _mark_completed(model, output_path, len(models)),
    )
    _log_export_success(job, models)
    metrics.record_export_job_result(ExportJobStatus.COMPLETED.value)
    return job


def _render_candidates(job: ExportJob) -> Tuple[dict[str, Any], list[CandidateNeedRead]]:
    filters = job.filters or {}
    statuses = filters.get("statuses")
    parsed_statuses = None
    if statuses:
        parsed_statuses = [CandidateNeedStatus(value) for value in statuses]
    needs = candidate_needs.export_needs(
        statuses=parsed_statuses,
        search=filters.get("search"),
        raw_entry_id=filters.get("raw_entry_id"),
        synced=filters.get("synced"),
        limit=filters.get("limit"),
    )
    models = [CandidateNeedRead.model_validate(item) for item in needs]
    if job.format == "json":
        content: list[dict[str, Any]] = []
        for model in models:
            payload = model.model_dump()
            payload["created_at"] = model.created_at.isoformat()
            payload["updated_at"] = model.updated_at.isoformat()
            payload["synced_at"] = (
                model.synced_at.isoformat() if model.synced_at else None
            )
            content.append(payload)
        return {"format": "json", "content": content}, models
    buffer = [
        [
            "id",
            "raw_entry_id",
            "summary",
            "problem_statement",
            "target_users",
            "value_proposition",
            "competition",
            "confidence",
            "rule_score",
            "status",
            "notes",
            "created_at",
            "updated_at",
        ]
    ]
    for model in models:
        buffer.append(
            [
                model.id,
                model.raw_entry_id,
                model.summary,
                model.problem_statement or "",
                model.target_users or "",
                model.value_proposition or "",
                model.competition or "",
                model.confidence if model.confidence is not None else "",
                model.rule_score if model.rule_score is not None else "",
                model.status.value,
                model.notes or "",
                model.created_at.isoformat(),
                model.updated_at.isoformat(),
            ]
        )
    return {"format": "csv", "content": buffer}, models


def _write_export_file(job: ExportJob, rendered: dict[str, Any]) -> str:
    base_dir = Path(settings.export_output_dir)
    base_dir.mkdir(parents=True, exist_ok=True)
    suffix = "json" if rendered["format"] == "json" else "csv"
    filename = f"candidate_needs_{job.id}.{suffix}"
    path = base_dir / filename
    if rendered["format"] == "json":
        import json

        path.write_text(
            json.dumps(rendered["content"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    else:
        import csv

        with path.open("w", encoding="utf-8", newline="") as fp:
            writer = csv.writer(fp)
            for row in rendered["content"]:
                writer.writerow(row)
    return str(path)


def _log_export_success(job: ExportJob, models: Sequence[CandidateNeedRead]) -> None:
    """为导出任务记录审计日志。"""

    if not models:
        return
    metadata = {
        "job_id": job.id,
        "format": job.format,
        "file_path": job.file_path,
    }
    for model in models:
        sync_audit.log_sync_attempt(
            model.id,
            channel=SyncChannel.EXPORT,
            status="success",
            attempt=job.attempt_count,
            metadata=metadata,
        )


def _mark_failed(model: ExportJob, message: str) -> None:
    model.status = ExportJobStatus.FAILED
    model.error_message = message
    model.finished_at = datetime.now(UTC)


def _mark_completed(model: ExportJob, file_path: str, count: int) -> None:
    model.status = ExportJobStatus.COMPLETED
    model.file_path = file_path
    model.record_count = count
    model.finished_at = datetime.now(UTC)
