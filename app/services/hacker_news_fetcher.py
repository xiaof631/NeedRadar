"""Hacker News 数据源抓取。"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from urllib.parse import urlparse

import httpx

from app.core import metrics
from app.db.storage import db
from app.models import FetchStatus, RssSource
from app.services import raw_entries, rss_sources

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


async def fetch_hacker_news_source(
    source: RssSource,
    *,
    client: httpx.AsyncClient | None = None,
) -> object:
    """抓取 Hacker News 列表并转为原始条目。"""

    from app.services.rss_fetcher import FetchResult

    close_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=10.0)
        close_client = True

    try:
        try:
            response = await client.get(source.url)
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
            item_ids = response.json()
        except ValueError as exc:
            message = "failed to parse hacker news listing"
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

        if not isinstance(item_ids, list):
            message = "hacker news listing did not return an array"
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

        item_limit = _coerce_item_limit(source.config.get("item_limit"))
        item_url_template = _build_item_url_template(source)
        board = _detect_board_name(source.url)

        fetched_entries = 0
        new_entries = 0
        for item_id in item_ids[:item_limit]:
            item = await _fetch_item(client, item_url_template, item_id)
            if item is None:
                continue

            payload = _normalize_item(source.id, item, board=board)
            if payload is None:
                continue

            fetched_entries += 1
            payload["content_hash"] = raw_entries.calculate_content_hash(payload)
            try:
                raw_entries.create_entry(payload)
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


async def _fetch_item(
    client: httpx.AsyncClient, item_url_template: str, item_id: object
) -> dict | None:
    try:
        item_id_int = int(item_id)
    except (TypeError, ValueError):
        return None

    try:
        response = await client.get(item_url_template.format(item_id=item_id_int))
    except httpx.HTTPError:
        return None
    if response.status_code >= 400:
        return None
    try:
        payload = response.json()
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _normalize_item(source_id: int, item: dict, *, board: str | None) -> dict | None:
    if item.get("deleted") or item.get("dead"):
        return None

    guid = item.get("id")
    title = str(item.get("title") or "").strip()
    text = _clean_html(item.get("text"))
    if guid is None or not (title or text):
        return None

    item_type = str(item.get("type") or "story").strip() or "story"
    tags = [item_type]
    if board:
        tags.append(board)

    external_url = item.get("url")
    discussion_url = f"https://news.ycombinator.com/item?id={guid}"
    link = str(external_url).strip() if external_url else discussion_url

    return {
        "source_id": source_id,
        "guid": str(guid),
        "title": title or f"HN item {guid}",
        "summary": title or text or f"HN item {guid}",
        "content": text,
        "link": link,
        "published_at": _parse_unix_timestamp(item.get("time")),
        "author": str(item.get("by") or "").strip() or None,
        "tags": tags,
    }


def _build_item_url_template(source: RssSource) -> str:
    configured = source.config.get("item_url_template")
    if isinstance(configured, str) and "{item_id}" in configured:
        return configured

    parsed = urlparse(source.url)
    base_path = parsed.path.rsplit("/", 1)[0]
    base_url = f"{parsed.scheme}://{parsed.netloc}{base_path}"
    return f"{base_url}/item/{{item_id}}.json"


def _detect_board_name(url: str) -> str | None:
    last_segment = urlparse(url).path.rsplit("/", 1)[-1]
    if not last_segment.endswith(".json"):
        return None
    board = last_segment[:-5]
    return board or None


def _coerce_item_limit(value: object) -> int:
    try:
        if value is None:
            return 20
        parsed = int(value)
    except (TypeError, ValueError):
        return 20
    return max(1, min(parsed, 100))


def _parse_unix_timestamp(value: object) -> datetime | None:
    try:
        timestamp = int(value)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(timestamp, tz=UTC)


def _clean_html(value: object) -> str | None:
    if value is None:
        return None
    text = _HTML_TAG_RE.sub(" ", str(value))
    cleaned = _WHITESPACE_RE.sub(" ", text).strip()
    return cleaned or None
