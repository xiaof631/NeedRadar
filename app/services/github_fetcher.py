"""GitHub Issues 数据源抓取。"""

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


async def fetch_github_issues_source(
    source: RssSource,
    *,
    client: httpx.AsyncClient | None = None,
) -> object:
    """抓取公开 GitHub issue 列表并转为原始条目。"""

    from app.services.rss_fetcher import FetchResult

    close_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=10.0)
        close_client = True

    try:
        params = _build_query_params(source.config)
        settings = get_settings()
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "NeedRadar/0.1",
        }
        if settings.github_access_token:
            headers["Authorization"] = f"Bearer {settings.github_access_token}"
        try:
            response = await client.get(
                source.url,
                params=params,
                headers=headers,
                follow_redirects=True,
            )
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
            message = _build_error_message(response)
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
            issues = response.json()
        except ValueError as exc:
            message = "failed to parse github issues response"
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

        if not isinstance(issues, list):
            message = "github issues response did not return an array"
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

        include_pull_requests = _coerce_bool(source.config.get("include_pull_requests"))
        fetched_entries = 0
        new_entries = 0
        for issue in issues:
            payload = _normalize_issue(issue, source_id=source.id, include_pull_requests=include_pull_requests)
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


def _build_query_params(config: dict[str, Any]) -> dict[str, str | int]:
    item_limit = _coerce_item_limit(config.get("item_limit"))
    params: dict[str, str | int] = {
        "state": str(config.get("state") or "open"),
        "per_page": item_limit,
    }
    labels = config.get("labels")
    if isinstance(labels, str) and labels.strip():
        params["labels"] = labels.strip()
    since = config.get("since")
    if isinstance(since, str) and since.strip():
        params["since"] = since.strip()
    sort = config.get("sort")
    if isinstance(sort, str) and sort.strip():
        params["sort"] = sort.strip()
    direction = config.get("direction")
    if isinstance(direction, str) and direction.strip():
        params["direction"] = direction.strip()
    return params


def _normalize_issue(
    issue: Any, *, source_id: int, include_pull_requests: bool
) -> dict[str, Any] | None:
    if not isinstance(issue, dict):
        return None
    if not include_pull_requests and "pull_request" in issue:
        return None

    issue_id = issue.get("id")
    title = _normalize_text(issue.get("title"))
    body = _normalize_text(issue.get("body"))
    if issue_id is None or not title:
        return None

    user = issue.get("user") if isinstance(issue.get("user"), dict) else {}
    repo_name = _extract_repo_name(issue.get("repository_url"))
    labels = _extract_labels(issue.get("labels"))
    tags = ["github_issue", str(issue.get("state") or "open")]
    if repo_name:
        tags.append(repo_name)
    tags.extend(labels)

    return {
        "source_id": source_id,
        "guid": str(issue_id),
        "title": title,
        "summary": title,
        "content": body,
        "link": _normalize_text(issue.get("html_url")),
        "published_at": _parse_iso_datetime(issue.get("created_at")),
        "author": _normalize_text(user.get("login")) if isinstance(user, dict) else None,
        "tags": list(dict.fromkeys(tag for tag in tags if tag)),
    }


def _extract_repo_name(value: Any) -> str | None:
    text = _normalize_text(value)
    if not text:
        return None
    marker = "/repos/"
    if marker not in text:
        return None
    return text.split(marker, 1)[-1]


def _extract_labels(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    labels: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        name = _normalize_text(item.get("name"))
        if name:
            labels.append(name)
    return labels


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


def _normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = _WHITESPACE_RE.sub(" ", str(value)).strip()
    return text or None


def _coerce_item_limit(value: Any) -> int:
    try:
        parsed = int(value) if value is not None else 20
    except (TypeError, ValueError):
        parsed = 20
    return max(1, min(parsed, 100))


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def _build_error_message(response: httpx.Response) -> str:
    if response.status_code == 403:
        body_text = response.text.lower()
        if "rate limit" in body_text or response.headers.get("x-ratelimit-remaining") == "0":
            return "github api rate limit exceeded; configure NEEDRADAR_GITHUB_ACCESS_TOKEN"
    return f"unexpected status code {response.status_code}"
