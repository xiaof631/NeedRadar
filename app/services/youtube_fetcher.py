"""YouTube 数据源抓取。"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core import metrics
from app.core.config import get_settings
from app.db.storage import db
from app.models import FetchStatus, RssSource
from app.services import raw_entries, rss_sources

_WHITESPACE_RE = re.compile(r"\s+")
_YOUTUBE_VIDEO_URL = "https://www.youtube.com/watch?v={video_id}"


async def fetch_youtube_source(
    source: RssSource,
    *,
    client: httpx.AsyncClient | None = None,
) -> object:
    """抓取 YouTube 搜索结果并转为原始条目。"""

    from app.services.rss_fetcher import FetchResult

    close_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=10.0)
        close_client = True

    try:
        settings = get_settings()
        if not settings.youtube_api_key:
            message = "youtube api key is not configured"
            db.add_fetch_log(source.id, status=FetchStatus.FAILURE, error_message=message)
            result = FetchResult(
                source_id=source.id,
                fetched_entries=0,
                new_entries=0,
                status=FetchStatus.FAILURE,
                error_message=message,
            )
            metrics.record_rss_fetch(result.status.value, new_entries=result.new_entries)
            return result

        params = _build_query_params(source.config, settings.youtube_api_key)
        if "q" not in params and "channelId" not in params:
            message = "youtube source requires query or channelId in config"
            db.add_fetch_log(source.id, status=FetchStatus.FAILURE, error_message=message)
            result = FetchResult(
                source_id=source.id,
                fetched_entries=0,
                new_entries=0,
                status=FetchStatus.FAILURE,
                error_message=message,
            )
            metrics.record_rss_fetch(result.status.value, new_entries=result.new_entries)
            return result

        try:
            response = await client.get(source.url, params=params)
        except httpx.HTTPError as exc:
            message = str(exc)
            db.add_fetch_log(source.id, status=FetchStatus.FAILURE, error_message=message)
            result = FetchResult(
                source_id=source.id,
                fetched_entries=0,
                new_entries=0,
                status=FetchStatus.FAILURE,
                error_message=message,
            )
            metrics.record_rss_fetch(result.status.value, new_entries=result.new_entries)
            return result

        if response.status_code >= 400:
            message = f"unexpected status code {response.status_code}"
            db.add_fetch_log(
                source.id,
                status=FetchStatus.FAILURE,
                http_status=response.status_code,
                error_message=message,
            )
            result = FetchResult(
                source_id=source.id,
                fetched_entries=0,
                new_entries=0,
                status=FetchStatus.FAILURE,
                error_message=message,
            )
            metrics.record_rss_fetch(result.status.value, new_entries=result.new_entries)
            return result

        try:
            payload = response.json()
        except ValueError as exc:
            message = "failed to parse youtube search response"
            db.add_fetch_log(
                source.id,
                status=FetchStatus.FAILURE,
                http_status=response.status_code,
                error_message=message,
            )
            result = FetchResult(
                source_id=source.id,
                fetched_entries=0,
                new_entries=0,
                status=FetchStatus.FAILURE,
                error_message=f"{message}: {exc}",
            )
            metrics.record_rss_fetch(result.status.value, new_entries=result.new_entries)
            return result

        items = payload.get("items") if isinstance(payload, dict) else None
        if not isinstance(items, list):
            message = "youtube search response did not contain items"
            db.add_fetch_log(
                source.id,
                status=FetchStatus.FAILURE,
                http_status=response.status_code,
                error_message=message,
            )
            result = FetchResult(
                source_id=source.id,
                fetched_entries=0,
                new_entries=0,
                status=FetchStatus.FAILURE,
                error_message=message,
            )
            metrics.record_rss_fetch(result.status.value, new_entries=result.new_entries)
            return result

        fetched_entries = 0
        new_entries = 0
        for item in items:
            normalized = _normalize_item(item, source_id=source.id)
            if normalized is None:
                continue
            fetched_entries += 1
            normalized["content_hash"] = raw_entries.calculate_content_hash(normalized)
            try:
                raw_entries.create_entry(normalized)
            except raw_entries.RawEntryAlreadyExistsError:
                continue
            new_entries += 1

        rss_sources.mark_source_fetched(source.id)
        db.add_fetch_log(source.id, status=FetchStatus.SUCCESS, http_status=response.status_code)
        result = FetchResult(
            source_id=source.id,
            fetched_entries=fetched_entries,
            new_entries=new_entries,
            status=FetchStatus.SUCCESS,
        )
        metrics.record_rss_fetch(result.status.value, new_entries=result.new_entries)
        return result
    finally:
        if close_client:
            await client.aclose()


def _build_query_params(config: dict[str, Any], api_key: str) -> dict[str, str | int]:
    params: dict[str, str | int] = {
        "part": "snippet",
        "type": "video",
        "maxResults": _coerce_item_limit(config.get("item_limit")),
        "key": api_key,
    }
    query = config.get("query")
    if isinstance(query, str) and query.strip():
        params["q"] = query.strip()
    channel_id = config.get("channel_id")
    if isinstance(channel_id, str) and channel_id.strip():
        params["channelId"] = channel_id.strip()
    order = config.get("order")
    if isinstance(order, str) and order.strip():
        params["order"] = order.strip()
    published_after = config.get("published_after")
    if isinstance(published_after, str) and published_after.strip():
        params["publishedAfter"] = published_after.strip()
    relevance_language = config.get("relevance_language")
    if isinstance(relevance_language, str) and relevance_language.strip():
        params["relevanceLanguage"] = relevance_language.strip()
    return params


def _normalize_item(item: Any, *, source_id: int) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    id_payload = item.get("id")
    snippet = item.get("snippet")
    if not isinstance(id_payload, dict) or not isinstance(snippet, dict):
        return None

    video_id = _normalize_text(id_payload.get("videoId"))
    title = _normalize_text(snippet.get("title"))
    if not video_id or not title:
        return None

    channel_title = _normalize_text(snippet.get("channelTitle"))
    tags = ["youtube"]
    if channel_title:
        tags.append(channel_title)

    return {
        "source_id": source_id,
        "guid": f"youtube:{video_id}",
        "title": title,
        "summary": title,
        "content": _normalize_text(snippet.get("description")),
        "link": _YOUTUBE_VIDEO_URL.format(video_id=video_id),
        "published_at": _parse_iso_datetime(snippet.get("publishedAt")),
        "author": channel_title,
        "tags": tags,
    }


def _parse_iso_datetime(value: Any) -> datetime | None:
    text = _normalize_text(value)
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _coerce_item_limit(value: Any) -> int:
    try:
        parsed = int(value) if value is not None else 20
    except (TypeError, ValueError):
        parsed = 20
    return max(1, min(parsed, 50))


def _normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = _WHITESPACE_RE.sub(" ", str(value)).strip()
    return text or None
