"""RSS 抓取任务。"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

import httpx

from app.db.storage import db
from app.models import FetchStatus, RssSource
from app.services import raw_entries, rss_sources


class RssFeedParseError(Exception):
    """RSS 内容解析异常。"""


@dataclass(slots=True)
class ParsedEntry:
    """解析后的 RSS 条目数据。"""

    guid: str
    title: str
    link: str | None
    summary: str | None
    content: str | None
    published_at: datetime | None
    author: str | None
    tags: list[str]


@dataclass(slots=True)
class FetchResult:
    """抓取执行结果。"""

    source_id: int
    fetched_entries: int
    new_entries: int
    status: FetchStatus
    error_message: str | None = None


async def fetch_rss_source(
    source_id: int,
    *,
    client: httpx.AsyncClient | None = None,
) -> FetchResult:
    """抓取指定数据源的 RSS。"""

    source = rss_sources.get_source(source_id)
    return await _fetch_with_source(source, client=client)


async def _fetch_with_source(
    source: RssSource,
    *,
    client: httpx.AsyncClient | None = None,
) -> FetchResult:
    close_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=10.0)
        close_client = True

    try:
        headers = {}
        if source.etag:
            headers["If-None-Match"] = source.etag
        if source.last_modified:
            headers["If-Modified-Since"] = source.last_modified

        try:
            response = await client.get(source.url, headers=headers)
        except httpx.HTTPError as exc:  # 网络异常
            message = str(exc)
            db.add_fetch_log(
                source.id,
                status=FetchStatus.FAILURE,
                error_message=message,
            )
            return FetchResult(
                source_id=source.id,
                fetched_entries=0,
                new_entries=0,
                status=FetchStatus.FAILURE,
                error_message=message,
            )

        if response.status_code == 304:  # 内容未变更
            rss_sources.mark_source_fetched(
                source.id,
                etag=source.etag,
                last_modified=source.last_modified,
            )
            db.add_fetch_log(
                source.id,
                status=FetchStatus.SUCCESS,
                http_status=response.status_code,
            )
            return FetchResult(
                source_id=source.id,
                fetched_entries=0,
                new_entries=0,
                status=FetchStatus.SUCCESS,
            )

        if response.status_code >= 400:
            message = f"unexpected status code {response.status_code}"
            db.add_fetch_log(
                source.id,
                status=FetchStatus.FAILURE,
                http_status=response.status_code,
                error_message=message,
            )
            return FetchResult(
                source_id=source.id,
                fetched_entries=0,
                new_entries=0,
                status=FetchStatus.FAILURE,
                error_message=message,
            )

        try:
            parsed_entries = _parse_feed(response.text)
        except RssFeedParseError as exc:
            message = str(exc)
            db.add_fetch_log(
                source.id,
                status=FetchStatus.FAILURE,
                http_status=response.status_code,
                error_message=message,
            )
            return FetchResult(
                source_id=source.id,
                fetched_entries=0,
                new_entries=0,
                status=FetchStatus.FAILURE,
                error_message=message,
            )

        new_entries = 0
        for entry in parsed_entries:
            payload = {
                "source_id": source.id,
                "guid": entry.guid,
                "title": entry.title,
                "summary": entry.summary,
                "content": entry.content,
                "link": entry.link,
                "published_at": entry.published_at,
                "author": entry.author,
                "tags": entry.tags,
            }
            payload["content_hash"] = raw_entries.calculate_content_hash(payload)
            try:
                raw_entries.create_entry(payload)
            except raw_entries.RawEntryAlreadyExistsError:
                continue
            new_entries += 1

        etag = response.headers.get("ETag", source.etag)
        last_modified = response.headers.get("Last-Modified", source.last_modified)
        rss_sources.mark_source_fetched(source.id, etag=etag, last_modified=last_modified)
        db.add_fetch_log(source.id, status=FetchStatus.SUCCESS, http_status=response.status_code)

        return FetchResult(
            source_id=source.id,
            fetched_entries=len(parsed_entries),
            new_entries=new_entries,
            status=FetchStatus.SUCCESS,
        )
    finally:
        if close_client:
            await client.aclose()


def _parse_feed(payload: str) -> list[ParsedEntry]:
    """根据 XML 内容解析 RSS/Atom。"""

    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:  # XML 非法
        raise RssFeedParseError("failed to parse rss feed") from exc

    tag = _strip_tag(root.tag)
    if tag == "feed":
        entries = [_parse_atom_entry(node) for node in root.findall(".//{*}entry")]
    else:
        channel = root.find("channel") if tag != "channel" else root
        if channel is None:
            raise RssFeedParseError("rss feed missing channel")
        entries = [_parse_rss_item(node) for node in channel.findall("item")]

    return [entry for entry in entries if entry is not None]


def _parse_rss_item(node: ET.Element) -> ParsedEntry | None:
    children = _children_map(node)
    title = _get_child_text(children, "title") or ""
    link = _get_child_text(children, "link")
    guid = _get_child_text(children, "guid") or link or title
    if not guid:
        return None

    summary = _get_child_text(children, "description")
    content = _get_child_text(children, "encoded") or summary
    published = _get_child_text(children, "pubDate")
    author = _get_child_text(children, "author")
    tags = _collect_text(children.get("category", []))

    return ParsedEntry(
        guid=guid,
        title=title or guid,
        link=link,
        summary=summary,
        content=content,
        published_at=_parse_datetime(published),
        author=author,
        tags=tags,
    )


def _parse_atom_entry(node: ET.Element) -> ParsedEntry | None:
    children = _children_map(node)
    title = _get_child_text(children, "title") or ""

    link = None
    for link_node in children.get("link", []):
        href = link_node.attrib.get("href")
        if href:
            link = href
            break

    guid = _get_child_text(children, "id") or link or title
    if not guid:
        return None

    summary = _get_child_text(children, "summary")
    content = _get_child_text(children, "content") or summary
    published = _get_child_text(children, "updated") or _get_child_text(children, "published")

    author = None
    for author_node in children.get("author", []):
        sub_children = _children_map(author_node)
        author = _get_child_text(sub_children, "name") or (author_node.text or "").strip() or None
        if author:
            break

    tags = _collect_text(children.get("category", []))

    return ParsedEntry(
        guid=guid,
        title=title or guid,
        link=link,
        summary=summary,
        content=content,
        published_at=_parse_datetime(published),
        author=author,
        tags=tags,
    )


def _collect_text(nodes: Iterable[ET.Element]) -> list[str]:
    values: list[str] = []
    for node in nodes:
        text = (node.text or "").strip()
        if text:
            values.append(text)
    return values


def _children_map(node: ET.Element) -> dict[str, list[ET.Element]]:
    mapping: dict[str, list[ET.Element]] = {}
    for child in node:
        key = _strip_tag(child.tag)
        mapping.setdefault(key, []).append(child)
    return mapping


def _get_child_text(children: dict[str, list[ET.Element]], key: str) -> str | None:
    nodes = children.get(key)
    if not nodes:
        return None
    for child in nodes:
        pieces = [piece.strip() for piece in child.itertext() if piece.strip()]
        text = " ".join(pieces)
        if text:
            return text
    return None


def _strip_tag(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None

    # Atom 通常为 ISO8601，RSS 为 RFC2822
    try:
        iso_value = raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(iso_value)
    except ValueError:
        try:
            dt = parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)
