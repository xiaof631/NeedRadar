"""面向调度器的一组高层任务。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

import httpx

from app.models import CandidateNeedStatus, RawEntryStatus, SourceStatus
from app.services import (
    candidate_needs,
    downstream,
    pipeline,
    raw_entries,
    rss_fetcher,
    rss_sources,
)
from app.services.pipeline import (
    CandidateAlreadyExistsError,
    EntryNotQualifiedError,
    PromotionResult,
)

_DEFAULT_TIMEOUT: Final[float] = 10.0


async def fetch_active_sources(
    *,
    limit: int | None = None,
    client: httpx.AsyncClient | None = None,
    request_timeout: float = _DEFAULT_TIMEOUT,
) -> list[rss_fetcher.FetchResult]:
    """抓取所有启用的 RSS 源并返回结果列表。"""

    _, sources = rss_sources.list_sources(status=SourceStatus.ACTIVE, limit=limit)
    if not sources:
        return []

    close_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=request_timeout)
        close_client = True

    try:
        results: list[rss_fetcher.FetchResult] = []
        for source in sources:
            result = await rss_fetcher.fetch_rss_source(source.id, client=client)
            results.append(result)
        return results
    finally:
        if close_client:
            await client.aclose()


def promote_pending_entries(
    *,
    batch_size: int = 20,
    min_score: float | None = None,
) -> list[PromotionResult]:
    """将待处理的原始条目自动晋升为候选需求。"""

    _, entries = raw_entries.list_entries(status=RawEntryStatus.PENDING, limit=batch_size)
    results: list[PromotionResult] = []
    for entry in entries:
        try:
            result = pipeline.promote_entry(entry.id, min_score=min_score)
        except (EntryNotQualifiedError, CandidateAlreadyExistsError):
            continue
        results.append(result)
    return results


async def sync_new_candidate_needs(
    *,
    webhook_url: str | None,
    statuses: Sequence[CandidateNeedStatus] | None = None,
    batch_size: int = 20,
    client: httpx.AsyncClient | None = None,
    request_timeout: float = _DEFAULT_TIMEOUT,
) -> list[downstream.SyncDeliveryResult]:
    """将尚未同步的候选需求推送至下游 Webhook。"""

    if not webhook_url:
        return []

    needs = candidate_needs.list_unsynced_needs(statuses=statuses, limit=batch_size)
    if not needs:
        return []

    close_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=request_timeout)
        close_client = True

    try:
        results: list[downstream.SyncDeliveryResult] = []
        for need in needs:
            result = await downstream.deliver_need_to_webhook(
                need,
                webhook_url=webhook_url,
                client=client,
                attempt=1,
            )
            results.append(result)
        return results
    finally:
        if close_client:
            await client.aclose()
