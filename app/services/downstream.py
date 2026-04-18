"""与下游系统同步候选需求的辅助方法。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import httpx

from app.core import metrics
from app.core.logging import get_logger
from app.models import CandidateNeed, SyncChannel
from app.schemas import CandidateNeedRead
from app.services import candidate_needs, mq, sync_audit

logger = get_logger(__name__)


@dataclass(slots=True)
class SyncDeliveryResult:
    """记录单条候选需求同步的结果。"""

    need_id: int
    success: bool
    channel: SyncChannel
    status_code: int | None = None
    error: str | None = None
    metadata: dict[str, str] | None = field(default=None)


async def deliver_need_to_webhook(
    need: CandidateNeed,
    *,
    webhook_url: str,
    client: httpx.AsyncClient,
    attempt: int = 1,
) -> SyncDeliveryResult:
    """将候选需求推送至配置的 webhook 并返回执行结果。"""

    payload = CandidateNeedRead.model_validate(need)
    payload_data = payload.model_dump()
    try:
        response = await client.post(webhook_url, json=payload_data)
    except httpx.HTTPError as exc:
        candidate_needs.mark_need_sync_failed(need.id, str(exc))
        metrics.record_downstream_delivery(SyncChannel.WEBHOOK.value, "network-error")
        sync_audit.log_sync_attempt(
            need.id,
            channel=SyncChannel.WEBHOOK,
            status="failed",
            attempt=attempt,
            message=str(exc),
        )
        return SyncDeliveryResult(
            need_id=need.id,
            success=False,
            channel=SyncChannel.WEBHOOK,
            status_code=None,
            error=str(exc),
        )

    if 200 <= response.status_code < 300:
        candidate_needs.mark_need_synced(need.id)
        metrics.record_downstream_delivery(SyncChannel.WEBHOOK.value, "success")
        sync_audit.log_sync_attempt(
            need.id,
            channel=SyncChannel.WEBHOOK,
            status="success",
            attempt=attempt,
            metadata={"status_code": response.status_code},
        )
        return SyncDeliveryResult(
            need_id=need.id,
            success=True,
            channel=SyncChannel.WEBHOOK,
            status_code=response.status_code,
            error=None,
        )

    message = f"HTTP {response.status_code}"
    candidate_needs.mark_need_sync_failed(need.id, message)
    metrics.record_downstream_delivery(SyncChannel.WEBHOOK.value, "http-error")
    sync_audit.log_sync_attempt(
        need.id,
        channel=SyncChannel.WEBHOOK,
        status="failed",
        attempt=attempt,
        message=message,
        metadata={"status_code": response.status_code},
    )
    return SyncDeliveryResult(
        need_id=need.id,
        success=False,
        channel=SyncChannel.WEBHOOK,
        status_code=response.status_code,
        error=message,
    )


def publish_need_to_mq(
    need: CandidateNeed,
    *,
    publisher: mq.BaseMQPublisher | None = None,
    attempt: int = 1,
) -> SyncDeliveryResult:
    """将候选需求写入消息队列。"""

    if publisher is None:
        publisher = mq.build_publisher()
    if publisher is None:
        raise RuntimeError("MQ publisher is not configured")

    payload = CandidateNeedRead.model_validate(need)
    result = publisher.publish(payload.model_dump())
    if result.success:
        candidate_needs.mark_need_synced(need.id)
        metrics.record_downstream_delivery(SyncChannel.MQ.value, "success")
        sync_audit.log_sync_attempt(
            need.id,
            channel=SyncChannel.MQ,
            status="success",
            attempt=attempt,
            metadata=result.metadata or {},
        )
        return SyncDeliveryResult(
            need_id=need.id,
            success=True,
            channel=SyncChannel.MQ,
            status_code=None,
        )

    message = result.error or "publish-failed"
    candidate_needs.mark_need_sync_failed(need.id, message)
    metrics.record_downstream_delivery(SyncChannel.MQ.value, "error")
    sync_audit.log_sync_attempt(
        need.id,
        channel=SyncChannel.MQ,
        status="failed",
        attempt=attempt,
        message=message,
    )
    logger.warning("downstream.mq.failed", need_id=need.id, error=message)
    return SyncDeliveryResult(
        need_id=need.id,
        success=False,
        channel=SyncChannel.MQ,
        error=message,
    )


def write_need_to_file_drop(
    need: CandidateNeed,
    *,
    directory: str,
    file_format: str = "json",
    attempt: int = 1,
) -> SyncDeliveryResult:
    """将候选需求写入文件系统通道。"""

    normalized_format = file_format.lower()
    if normalized_format not in {"json", "jsonl"}:
        raise ValueError(f"unsupported file drop format: {file_format}")

    payload = CandidateNeedRead.model_validate(need)
    target_dir = Path(directory)
    start = perf_counter()
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = _write_payload(target_dir, payload, normalized_format)
    except OSError as exc:
        candidate_needs.mark_need_sync_failed(need.id, str(exc))
        metrics.record_downstream_delivery(SyncChannel.FILE_DROP.value, "error")
        sync_audit.log_sync_attempt(
            need.id,
            channel=SyncChannel.FILE_DROP,
            status="failed",
            attempt=attempt,
            message=str(exc),
            metadata={"format": normalized_format},
        )
        return SyncDeliveryResult(
            need_id=need.id,
            success=False,
            channel=SyncChannel.FILE_DROP,
            error=str(exc),
        )

    duration = perf_counter() - start
    candidate_needs.mark_need_synced(need.id)
    metrics.record_downstream_delivery(SyncChannel.FILE_DROP.value, "success")
    metrics.record_file_drop_duration(duration, file_format=normalized_format)
    sync_audit.log_sync_attempt(
        need.id,
        channel=SyncChannel.FILE_DROP,
        status="success",
        attempt=attempt,
        metadata={
            "file_path": str(file_path),
            "format": normalized_format,
            "duration_ms": round(duration * 1000, 3),
        },
    )
    return SyncDeliveryResult(
        need_id=need.id,
        success=True,
        channel=SyncChannel.FILE_DROP,
        metadata={"file_path": str(file_path)},
    )


def _write_payload(directory: Path, payload: CandidateNeedRead, file_format: str) -> Path:
    timestamp = datetime.now(UTC)
    if file_format == "jsonl":
        target = directory / f"needs-{timestamp:%Y%m%d}.jsonl"
        with target.open("a", encoding="utf-8") as handle:
            handle.write(_render_payload(payload, indent=None) + "\n")
        return target

    target = directory / f"need-{payload.id}-{timestamp:%Y%m%d%H%M%S}.json"
    with target.open("w", encoding="utf-8") as handle:
        handle.write(_render_payload(payload, indent=2))
    return target


def _render_payload(payload: CandidateNeedRead, *, indent: int | None) -> str:
    return json.dumps(
        payload.model_dump(),
        ensure_ascii=False,
        indent=indent,
        default=_json_default,
    )


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value
