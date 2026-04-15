"""Reddit 数据源抓取。"""

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
_REDDIT_BASE_URL = "https://www.reddit.com"
_COMPLAINT_PATTERNS = (
    "annoying",
    "frustrating",
    "painful",
    "pain point",
    "manual",
    "takes too long",
    "tedious",
    "hate",
    "broken",
    "clunky",
    "messy",
    "slow",
)
_ALTERNATIVE_PATTERNS = (
    "alternative",
    "replace",
    "replacement",
    "switch from",
    "better than",
    "looking for",
    "any tool",
    "any app",
    "recommend",
)


async def fetch_reddit_source(
    source: RssSource,
    *,
    client: httpx.AsyncClient | None = None,
) -> object:
    """抓取 Reddit listing 并转为原始条目。"""

    from app.services.rss_fetcher import FetchResult

    close_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=10.0)
        close_client = True

    try:
        settings = get_settings()
        headers = {"User-Agent": settings.reddit_user_agent}
        if settings.reddit_access_token:
            headers["Authorization"] = f"Bearer {settings.reddit_access_token}"

        params = _build_query_params(source.config)
        target_url = _normalize_listing_url(source.url)
        try:
            response = await client.get(target_url, params=params, headers=headers)
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
            listing = response.json()
        except ValueError as exc:
            message = "failed to parse reddit listing response"
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

        children = listing.get("data", {}).get("children") if isinstance(listing, dict) else None
        if not isinstance(children, list):
            message = "reddit listing response did not contain children"
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
        for child in children:
            payload = _normalize_listing_child(child, source_id=source.id)
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


def _normalize_listing_url(url: str) -> str:
    normalized = url.rstrip("/")
    if normalized.endswith(".json"):
        return normalized
    return f"{normalized}.json"


def _build_query_params(config: dict[str, Any]) -> dict[str, str | int]:
    params: dict[str, str | int] = {
        "limit": _coerce_item_limit(config.get("item_limit")),
        "raw_json": 1,
    }
    time_filter = config.get("time")
    if isinstance(time_filter, str) and time_filter.strip():
        params["t"] = time_filter.strip()
    sort = config.get("sort")
    if isinstance(sort, str) and sort.strip():
        params["sort"] = sort.strip()
    return params


def _normalize_listing_child(child: Any, *, source_id: int) -> dict[str, Any] | None:
    if not isinstance(child, dict):
        return None
    kind = _normalize_text(child.get("kind"))
    data = child.get("data")
    if not isinstance(data, dict):
        return None
    if kind == "t1":
        return _normalize_comment_child(data, source_id=source_id)
    return _normalize_post_child(data, source_id=source_id)


def _normalize_post_child(data: dict[str, Any], *, source_id: int) -> dict[str, Any] | None:
    if data.get("stickied") or data.get("is_self") is None:
        return None

    guid = _normalize_text(data.get("name")) or _normalize_text(data.get("id"))
    title = _normalize_text(data.get("title"))
    if not guid or not title:
        return None

    permalink = _normalize_text(data.get("permalink"))
    discussion_link = f"{_REDDIT_BASE_URL}{permalink}" if permalink else None
    outbound_link = _normalize_text(data.get("url"))
    text_content = _normalize_text(data.get("selftext"))

    tags = _build_common_tags(data)
    post_hint = _normalize_text(data.get("post_hint"))
    if post_hint:
        tags.append(post_hint)
    tags.append("reddit_post")
    tags.extend(_infer_signal_tags(" ".join(part for part in (title, text_content or "") if part)))

    return {
        "source_id": source_id,
        "guid": guid,
        "title": title,
        "summary": title,
        "content": text_content,
        "link": discussion_link or outbound_link,
        "published_at": _parse_created_at(data.get("created_utc")),
        "author": _normalize_text(data.get("author")),
        "tags": list(dict.fromkeys(tags)),
    }


def _normalize_comment_child(data: dict[str, Any], *, source_id: int) -> dict[str, Any] | None:
    if data.get("stickied"):
        return None

    guid = _normalize_text(data.get("name")) or _normalize_text(data.get("id"))
    body = _normalize_text(data.get("body"))
    if not guid or not body:
        return None

    link_title = _normalize_text(data.get("link_title")) or "Reddit discussion"
    author = _normalize_text(data.get("author"))
    title = f"Comment on {link_title}"

    permalink = _normalize_text(data.get("permalink"))
    discussion_link = f"{_REDDIT_BASE_URL}{permalink}" if permalink else None

    tags = _build_common_tags(data)
    tags.append("reddit_comment")
    tags.extend(_infer_signal_tags(body))

    return {
        "source_id": source_id,
        "guid": guid,
        "title": title,
        "summary": _truncate_text(body, limit=140),
        "content": body,
        "link": discussion_link,
        "published_at": _parse_created_at(data.get("created_utc")),
        "author": author,
        "tags": list(dict.fromkeys(tags)),
    }


def _build_common_tags(data: dict[str, Any]) -> list[str]:
    tags = []
    subreddit = _normalize_text(data.get("subreddit"))
    if subreddit:
        tags.append(subreddit)
    flair = _normalize_text(data.get("link_flair_text")) or _normalize_text(data.get("author_flair_text"))
    if flair:
        tags.append(flair)
    tags.append("reddit")
    return tags


def _infer_signal_tags(text: str) -> list[str]:
    lowered = text.lower()
    tags: list[str] = []
    if any(pattern in lowered for pattern in _COMPLAINT_PATTERNS):
        tags.append("complaint_signal")
    if any(pattern in lowered for pattern in _ALTERNATIVE_PATTERNS):
        tags.append("alternative_request")
    return tags


def _truncate_text(value: str, *, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def _parse_created_at(value: Any) -> datetime | None:
    try:
        timestamp = float(value)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(timestamp, tz=UTC)


def _coerce_item_limit(value: Any) -> int:
    try:
        parsed = int(value) if value is not None else 20
    except (TypeError, ValueError):
        parsed = 20
    return max(1, min(parsed, 100))


def _normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = _WHITESPACE_RE.sub(" ", str(value)).strip()
    return text or None
