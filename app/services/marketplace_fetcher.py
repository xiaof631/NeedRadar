"""公开外包项目/自由职业市场抓取。"""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin
from xml.etree import ElementTree as ET

import httpx

from app.core import metrics
from app.db.storage import db
from app.models import FetchStatus, RssSource
from app.services import raw_entries, rss_sources

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DAYS_LEFT_RE = re.compile(r"^\d+\s+days?\s+left$", re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"\s+")
_TRAILING_HOURS_RE = re.compile(r"(?P<budget>.+?/hr)\s*(?P<hours>\d+\s*hrs/wk)\b", re.IGNORECASE)
_TRAILING_ENGAGEMENT_RE = re.compile(r"(?P<budget>.+?)(?P<engagement>One-time|Ongoing)\b", re.IGNORECASE)
_ZBJ_TASK_ITEM_RE = re.compile(
    r'<div class="task-list-item[^"]*" data-tid="(?P<task_id>\d+)">\s*'
    r'<p class="task-title"><span class="orange">(?P<budget>[^<]+)</span>\s*(?P<title>[^<]+)</p>\s*'
    r'<p class="task-detail"><span class="fr">(?P<timeline>[^<]+)</span><span class="fl">(?P<bids>[^<]+)</span></p>',
    re.IGNORECASE | re.DOTALL,
)
_ZBJ_TASK_CARD_RE = re.compile(
    r'<a\s+href="(?P<href>//task\.zbj\.com/(?P<task_id>\d+)/)"[^>]*title="(?P<title>[^"]+)"[^>]*>.*?</a>\s*'
    r'<div class="hall-floor-main-footer">\s*'
    r'<p class="title"><span class="orange">(?P<budget>[^<]+)</span>.*?</p>\s*'
    r'(?:<p class="state"><span class="state [^"]+">(?P<state>[^<]+)</span>)?',
    re.IGNORECASE | re.DOTALL,
)
_PPH_ITEM_BLOCK_RE = re.compile(r'<li class="list__item[^"]*".*?</li>', re.IGNORECASE | re.DOTALL)
_WWR_COMPENSATION_RE = re.compile(
    r"\$(?:\d[\d,.]*)(?:k)?(?:/\w+| per annual)?(?:\s*(?:to|-)\s*\$(?:\d[\d,.]*)(?:k)?(?:/\w+| per annual)?)?",
    re.IGNORECASE,
)
_WWR_COMPANY_RE = re.compile(r"^(?P<company>[^:]+):\s*(?P<title>.+)$")
_WWR_CONTRACT_HINTS = ("contract", "contract-based", "freelance", "project-based", "/hr", "hourly")
_JOBICY_DEV_TITLE_HINTS = (
    "developer",
    "engineer",
    "full stack",
    "full-stack",
    "frontend",
    "backend",
    "web developer",
    "mobile engineer",
    "software developer",
)
_JOBICY_CONTRACT_HINTS = (
    "freelance",
    "project-based",
    "part-time, non-permanent",
    "non-permanent projects",
    "flexible participation",
    "hours per week",
    "hour equivalent",
    "b2b",
)
_JOBICY_EXCLUDE_HINTS = (
    "trainer",
    "data scientist",
    "data science",
    "analyst",
    "physics",
    "chemistry",
    "civil engineer",
    "mathematics",
)
_MARKETPLACE_SKILL_HINTS = (
    "react",
    "next.js",
    "python",
    "django",
    "node.js",
    "node",
    "typescript",
    "javascript",
    "php",
    "laravel",
    "wordpress",
    "android",
    "ios",
    "flutter",
    "react native",
    ".net",
    "c#",
    "api",
    "graphql",
    "sql",
    "postgres",
    "postgresql",
    "docker",
    "kubernetes",
)


@dataclass(slots=True)
class ParsedMarketplaceLead:
    guid: str
    title: str
    summary: str | None
    description: str | None
    link: str | None
    published_at: datetime | None
    author: str | None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


async def fetch_marketplace_source(
    source: RssSource,
    *,
    client: httpx.AsyncClient | None = None,
) -> object:
    """抓取外包项目线索并转为原始条目。"""

    from app.services.rss_fetcher import FetchResult

    close_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=15.0)
        close_client = True

    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/135.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }
        try:
            response = await client.get(source.url, headers=headers, follow_redirects=True)
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
            parsed_entries = _parse_marketplace_page(source, response.text)
        except ValueError as exc:
            message = str(exc)
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
        filtered_entries = _filter_marketplace_items(source, parsed_entries)[:item_limit]

        new_entries = 0
        for item in filtered_entries:
            payload = {
                "source_id": source.id,
                "guid": item.guid,
                "title": item.title,
                "summary": item.summary,
                "content": item.description,
                "link": item.link,
                "published_at": item.published_at,
                "author": item.author,
                "tags": item.tags,
                "metadata": item.metadata,
            }
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
            fetched_entries=len(filtered_entries),
            new_entries=new_entries,
            status=FetchStatus.SUCCESS,
        )
        metrics.record_rss_fetch(result.status.value, new_entries=result.new_entries)
        return result
    finally:
        if close_client:
            await client.aclose()


def _parse_marketplace_page(source: RssSource, payload: str) -> list[ParsedMarketplaceLead]:
    adapter = str(source.config.get("adapter") or "").strip().lower()
    item_limit = _coerce_item_limit(source.config.get("item_limit"))
    if adapter == "sxsoft_latest":
        return _parse_sxsoft_latest(payload, source=source, item_limit=item_limit)
    if adapter == "freelancer_jobs":
        return _parse_freelancer_jobs(payload, source=source, item_limit=item_limit)
    if adapter == "contra_featured_jobs":
        return _parse_contra_featured_jobs(payload, source=source, item_limit=item_limit)
    if adapter == "peopleperhour_technology":
        return _parse_peopleperhour_technology(payload, source=source, item_limit=item_limit)
    if adapter == "jobicy_api":
        return _parse_jobicy_api(payload, source=source, item_limit=item_limit)
    if adapter == "remotive_api":
        return _parse_remotive_api(payload, source=source, item_limit=item_limit)
    if adapter == "wwr_programming_rss":
        return _parse_wwr_programming_rss(payload, source=source, item_limit=item_limit)
    if adapter == "zbj_hall_scroll":
        return _parse_zbj_hall_scroll(payload, source=source, item_limit=item_limit)
    raise ValueError(f"unsupported marketplace adapter: {adapter or 'unknown'}")


def _parse_sxsoft_latest(
    payload: str,
    *,
    source: RssSource,
    item_limit: int,
) -> list[ParsedMarketplaceLead]:
    lines = _extract_lines(payload)
    links = _build_anchor_lookup(payload, source.url)
    start = _find_sxsoft_listing_start(lines)
    if start is None:
        raise ValueError("failed to parse sxsoft marketplace listing")

    items: list[ParsedMarketplaceLead] = []
    index = start
    while index + 5 < len(lines) and len(items) < item_limit:
        if _is_sxsoft_stop_line(lines, index):
            break
        if _is_sxsoft_header_line(lines[index]):
            index += 1
            continue
        category = lines[index]
        title = lines[index + 1]
        budget = lines[index + 2]
        timeline = lines[index + 3]
        published_text = lines[index + 4]
        bids = lines[index + 5]
        status = lines[index + 6] if index + 6 < len(lines) and "中" in lines[index + 6] else None
        if not _DATE_RE.match(published_text):
            index += 1
            continue

        published_at = _parse_date(published_text)
        link = _lookup_anchor_href(links, title)
        tags = ["marketplace", "sxsoft"]
        if category:
            tags.append(category)
        metadata = {
            "platform": "软件项目交易网",
            "category": category,
            "budget": budget,
            "timeline": timeline,
            "engagement": "招标·按项目付费",
            "location": None,
            "skills": [category] if category else [],
            "bids": bids,
            "listing_status": status,
        }
        items.append(
            ParsedMarketplaceLead(
                guid=link or f"sxsoft:{title}:{published_text}",
                title=title,
                summary=_join_summary(title, budget=budget, timeline=timeline, platform="软件项目交易网"),
                description=None,
                link=link,
                published_at=published_at,
                author=None,
                tags=list(dict.fromkeys(tags)),
                metadata=metadata,
            )
        )
        index += 7 if status else 6
    return items


def _find_sxsoft_listing_start(lines: list[str]) -> int | None:
    combined_header = "标题 项目预算 开发周期 发布日期 已有竞标"
    if combined_header in lines:
        return lines.index(combined_header) + 1
    for idx in range(len(lines) - 4):
        if lines[idx : idx + 5] == ["标题", "项目预算", "开发周期", "发布日期", "已有竞标"]:
            return idx + 5
    if "最新发布" in lines:
        return lines.index("最新发布") + 1
    return None


def _is_sxsoft_header_line(value: str) -> bool:
    return value in {"最新发布", "开发中", "优秀软件服务商", "标题", "项目预算", "开发周期", "发布日期", "已有竞标"}


def _is_sxsoft_stop_line(lines: list[str], index: int) -> bool:
    if lines[index] == "标题 项目资金 接包方 开发周期 开工日期":
        return True
    return lines[index : index + 5] == ["标题", "项目资金", "接包方", "开发周期", "开工日期"]


def _parse_freelancer_jobs(
    payload: str,
    *,
    source: RssSource,
    item_limit: int,
) -> list[ParsedMarketplaceLead]:
    lines = _extract_lines(payload)
    links = _build_anchor_lookup(payload, source.url)
    items: list[ParsedMarketplaceLead] = []

    start = 0
    for idx, line in enumerate(lines):
        if line.endswith("jobs found"):
            start = idx + 1
            break

    index = start
    while index + 2 < len(lines) and len(items) < item_limit:
        title = lines[index]
        if title in {"First", "Next", "Last", "Bid now"} or not title:
            index += 1
            continue
        if not _DAYS_LEFT_RE.match(lines[index + 1]):
            index += 1
            continue

        timeline = lines[index + 1]
        cursor = index + 2
        description_lines: list[str] = []
        skills: list[str] = []
        budget: str | None = None
        bids: str | None = None

        while cursor < len(lines):
            line = lines[cursor]
            if not line:
                cursor += 1
                continue
            if line == "Bid now":
                cursor += 1
                break
            if "Average bid" in line:
                budget = _normalize_text(line)
                cursor += 1
                continue
            if re.search(r"\b\d+\s+bids?\b", line, flags=re.IGNORECASE):
                bids = line
                cursor += 1
                continue
            if line.startswith("$") and ("Avg Bid" in line or "/ hr" in line):
                budget = budget or _normalize_text(line)
                cursor += 1
                continue
            if budget is None:
                description_lines.append(line)
            elif _looks_like_skill_token(line):
                skills.append(line)
            cursor += 1

        link = _lookup_anchor_href(links, title)
        category = str(source.config.get("topic") or source.category or "").strip() or None
        description = _normalize_text(" ".join(description_lines))
        metadata = {
            "platform": "Freelancer",
            "category": category,
            "budget": budget,
            "timeline": timeline,
            "engagement": _infer_engagement(budget),
            "location": None,
            "skills": skills,
            "bids": bids,
        }
        tags = ["marketplace", "freelancer"]
        if category:
            tags.append(category)
        items.append(
            ParsedMarketplaceLead(
                guid=link or f"freelancer:{title}:{timeline}",
                title=title,
                summary=_join_summary(title, budget=budget, timeline=timeline, platform="Freelancer"),
                description=description,
                link=link,
                published_at=None,
                author=None,
                tags=list(dict.fromkeys(tags)),
                metadata=metadata,
            )
        )
        index = cursor
    return items


def _parse_contra_featured_jobs(
    payload: str,
    *,
    source: RssSource,
    item_limit: int,
) -> list[ParsedMarketplaceLead]:
    lines = _extract_lines(payload)
    links = _build_anchor_lookup(payload, source.url)
    try:
        start = lines.index("Featured remote creative jobs") + 1
    except ValueError as exc:
        raise ValueError("failed to parse contra marketplace listing") from exc

    items: list[ParsedMarketplaceLead] = []
    index = start
    while index + 2 < len(lines) and len(items) < item_limit:
        if lines[index] == "FAQs":
            break
        if lines[index] != "Company":
            index += 1
            continue
        title = lines[index + 1]
        detail = lines[index + 2]
        link = _lookup_anchor_href(links, title)
        budget, timeline = _split_budget_timeline(detail)
        items.append(
            ParsedMarketplaceLead(
                guid=link or f"contra:{title}:{detail}",
                title=title,
                summary=_join_summary(title, budget=budget, timeline=timeline, platform="Contra"),
                description=None,
                link=link,
                published_at=None,
                author=None,
                tags=["marketplace", "contra", "remote"],
                metadata={
                    "platform": "Contra",
                    "category": str(source.config.get("topic") or source.category or "").strip() or None,
                    "budget": budget,
                    "timeline": timeline,
                    "engagement": _infer_engagement(detail),
                    "location": "Remote",
                    "skills": [],
                },
            )
        )
        index += 3
    return items


def _parse_peopleperhour_technology(
    payload: str,
    *,
    source: RssSource,
    item_limit: int,
) -> list[ParsedMarketplaceLead]:
    items: list[ParsedMarketplaceLead] = []
    for match in _PPH_ITEM_BLOCK_RE.finditer(payload):
        block = match.group(0)
        title_match = re.search(
            r'item__url[^"]*" href="(?P<href>[^"]+)">(?P<title>[^<]+)</a>',
            block,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if title_match is None:
            continue
        title = _normalize_text(title_match.group("title"))
        href = _normalize_text(title_match.group("href"))
        if not title or not href:
            continue
        description_match = re.search(
            r'item__desc[^"]*">(?P<description>.*?)</p>',
            block,
            flags=re.IGNORECASE | re.DOTALL,
        )
        footer_match = re.search(
            r'card__footer-left[^"]*"><span>(?P<published>[^<]+)</span><span class="u-mgl--1">(?P<proposals>\d+).*?</span>'
            r'<span class="u-mgl--1"><span><i class="fpph fpph-location"></i>(?P<location>[^<]+)</span>',
            block,
            flags=re.IGNORECASE | re.DOTALL,
        )
        budget_match = re.search(
            r'card__price[^"]*"><span class="title-nano"><div><span>(?P<budget>[^<]+)</span>',
            block,
            flags=re.IGNORECASE | re.DOTALL,
        )
        author_match = re.search(
            r'card__username[^"]*">\s*&nbsp;\s*(?P<author>[^<]+)</span>',
            block,
            flags=re.IGNORECASE | re.DOTALL,
        )
        description = _strip_html_tags(description_match.group("description")) if description_match else None
        published_text = _normalize_text(footer_match.group("published")) if footer_match else None
        proposals = _normalize_text(footer_match.group("proposals")) if footer_match else None
        location = _normalize_text(footer_match.group("location")) if footer_match else None
        budget = _normalize_text(budget_match.group("budget")) if budget_match else None
        link = urljoin(source.url, href)
        tags = ["marketplace", "peopleperhour", "remote"]
        category = str(source.config.get("topic") or source.category or "").strip() or None
        if category:
            tags.append(category)
        items.append(
            ParsedMarketplaceLead(
                guid=link,
                title=title,
                summary=_join_summary(title, budget=budget, timeline=published_text, platform="PeoplePerHour"),
                description=description,
                link=link,
                published_at=None,
                author=_normalize_text(author_match.group("author")) if author_match else None,
                tags=list(dict.fromkeys(tags)),
                metadata={
                    "platform": "PeoplePerHour",
                    "category": category,
                    "budget": budget,
                    "timeline": published_text,
                    "engagement": _infer_engagement(budget) or "fixed-price",
                    "location": location,
                    "skills": [],
                    "bids": proposals,
                },
            )
        )
        if len(items) >= item_limit:
            break
    if not items:
        raise ValueError("failed to parse peopleperhour marketplace listing")
    return items


def _parse_remotive_api(
    payload: str,
    *,
    source: RssSource,
    item_limit: int,
) -> list[ParsedMarketplaceLead]:
    try:
        document = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError("failed to parse remotive api response") from exc

    jobs = document.get("jobs")
    if not isinstance(jobs, list):
        raise ValueError("failed to parse remotive api response")

    allowed_job_types = {
        item
        for item in _normalize_keywords(source.config.get("job_types"))
        if item
    }
    items: list[ParsedMarketplaceLead] = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        link = _normalize_text(job.get("url"))
        title = _normalize_text(job.get("title"))
        if not link or not title:
            continue
        job_type = _normalize_text(job.get("job_type"))
        description_html = _normalize_text(job.get("description"))
        description = _strip_html_tags(description_html or "")
        category = _normalize_text(job.get("category"))
        company = _normalize_text(job.get("company_name"))
        location = _normalize_text(job.get("candidate_required_location"))
        salary = _normalize_text(job.get("salary"))
        tags = ["marketplace", "remotive", "remote"]
        if category:
            tags.append(category)

        if allowed_job_types:
            normalized_job_type = (job_type or "").lower()
            haystack = " ".join(part for part in (title, description or "") if part).lower()
            if normalized_job_type not in allowed_job_types and not any(
                keyword in haystack for keyword in allowed_job_types
            ):
                continue

        items.append(
            ParsedMarketplaceLead(
                guid=link,
                title=title,
                summary=_join_summary(title, budget=salary, timeline=location, platform="Remotive"),
                description=description,
                link=link,
                published_at=_parse_datetime(job.get("publication_date")),
                author=company,
                tags=list(dict.fromkeys(tags)),
                metadata={
                    "platform": "Remotive",
                    "category": category,
                    "budget": salary,
                    "timeline": location,
                    "engagement": job_type,
                    "location": location,
                    "skills": _extract_remotive_skills(job),
                    "bids": None,
                },
            )
        )
        if len(items) >= item_limit:
            break

    if not items:
        raise ValueError("failed to parse remotive api response")
    return items


def _parse_jobicy_api(
    payload: str,
    *,
    source: RssSource,
    item_limit: int,
) -> list[ParsedMarketplaceLead]:
    try:
        document = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError("failed to parse jobicy api response") from exc

    jobs = document.get("jobs")
    if not isinstance(jobs, list):
        raise ValueError("failed to parse jobicy api response")

    items: list[ParsedMarketplaceLead] = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        link = _normalize_text(job.get("url"))
        title = _normalize_text(job.get("jobTitle"))
        if not link or not title:
            continue

        company = _normalize_text(job.get("companyName"))
        description_html = _normalize_text(job.get("jobDescription"))
        description = _strip_html_tags(description_html or "")
        excerpt = _normalize_text(job.get("jobExcerpt"))
        location = _normalize_text(job.get("jobGeo"))
        level = _normalize_text(job.get("jobLevel"))
        industries = [
            text
            for item in job.get("jobIndustry", [])
            if (text := _normalize_text(item))
        ]
        industry = ", ".join(industries) or None
        job_types = [
            text
            for item in job.get("jobType", [])
            if (text := _normalize_text(item))
        ]
        title_haystack = " ".join(part for part in (title, industry or "") if part).lower()
        contract_haystack = " ".join(
            part for part in (title, excerpt or "", description or "", industry or "") if part
        ).lower()

        if not any(keyword in title_haystack for keyword in _JOBICY_DEV_TITLE_HINTS):
            continue
        if any(keyword in title_haystack for keyword in _JOBICY_EXCLUDE_HINTS):
            continue
        if not any(keyword in contract_haystack for keyword in _JOBICY_CONTRACT_HINTS):
            continue

        salary = _format_jobicy_salary(job)
        engagement = _infer_jobicy_engagement(job_types, contract_haystack)
        tags = ["marketplace", "jobicy", "remote"]
        if industry:
            tags.append(industry)
        if engagement:
            tags.append(engagement)

        items.append(
            ParsedMarketplaceLead(
                guid=link,
                title=title,
                summary=_join_summary(title, budget=salary, timeline=location, platform="Jobicy"),
                description=description or excerpt,
                link=link,
                published_at=_parse_datetime(job.get("pubDate")),
                author=company,
                tags=list(dict.fromkeys(tags)),
                metadata={
                    "platform": "Jobicy",
                    "category": industry,
                    "budget": salary,
                    "timeline": location,
                    "engagement": engagement,
                    "location": location,
                    "skills": _extract_jobicy_skills(title, description, industry),
                    "bids": None,
                    "level": level,
                },
            )
        )
        if len(items) >= item_limit:
            break

    if not items:
        raise ValueError("failed to parse jobicy api response")
    return items


def _parse_wwr_programming_rss(
    payload: str,
    *,
    source: RssSource,
    item_limit: int,
) -> list[ParsedMarketplaceLead]:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise ValueError("failed to parse weworkremotely rss feed") from exc

    channel = root.find("channel")
    if channel is None:
        raise ValueError("failed to parse weworkremotely rss feed")

    items: list[ParsedMarketplaceLead] = []
    for item in channel.findall("item"):
        raw_title = _normalize_text(item.findtext("title"))
        link = _normalize_text(item.findtext("link"))
        if not raw_title or not link:
            continue
        title_match = _WWR_COMPANY_RE.match(raw_title)
        company = _normalize_text(title_match.group("company")) if title_match else None
        title = _normalize_text(title_match.group("title")) if title_match else raw_title
        description_html = item.findtext("description") or ""
        description = _strip_html_tags(description_html)
        region = _normalize_text(item.findtext("region"))
        category = _normalize_text(item.findtext("category"))
        compensation = _extract_wwr_compensation(description)
        engagement = _infer_wwr_engagement(raw_title, description)
        tags = ["marketplace", "weworkremotely", "remote"]
        if category:
            tags.append(category)
        published_at = _parse_pubdate(item.findtext("pubDate"))
        items.append(
            ParsedMarketplaceLead(
                guid=link,
                title=title or raw_title,
                summary=_join_summary(title or raw_title, budget=compensation, timeline=region, platform="We Work Remotely"),
                description=description,
                link=link,
                published_at=published_at,
                author=company,
                tags=list(dict.fromkeys(tags)),
                metadata={
                    "platform": "We Work Remotely",
                    "category": category,
                    "budget": compensation,
                    "timeline": region,
                    "engagement": engagement,
                    "location": region,
                    "skills": [category] if category else [],
                    "bids": None,
                },
            )
        )
        if len(items) >= item_limit:
            break
    if not items:
        raise ValueError("failed to parse weworkremotely rss feed")
    return items


def _parse_zbj_hall_scroll(
    payload: str,
    *,
    source: RssSource,
    item_limit: int,
) -> list[ParsedMarketplaceLead]:
    items_by_guid: dict[str, ParsedMarketplaceLead] = {}
    for match in _ZBJ_TASK_ITEM_RE.finditer(payload):
        task_id = match.group("task_id")
        raw_title = _normalize_text(match.group("title")) or ""
        budget = _normalize_text(match.group("budget"))
        timeline = _normalize_text(match.group("timeline"))
        bids = _normalize_text(match.group("bids"))
        location, title = _split_location_title(raw_title)
        link = f"https://task.zbj.com/{task_id}/"
        metadata: dict[str, object] = {
            "platform": "猪八戒",
            "category": str(source.config.get("topic") or source.category or "").strip() or None,
            "budget": budget,
            "timeline": timeline,
            "engagement": "fixed-price",
            "location": location,
            "skills": [],
            "bids": bids,
        }
        items_by_guid[f"zbj:{task_id}"] = ParsedMarketplaceLead(
            guid=f"zbj:{task_id}",
            title=title or raw_title,
            summary=_join_summary(title or raw_title, budget=budget, timeline=timeline, platform="猪八戒"),
            description=bids,
            link=link,
            published_at=None,
            author=None,
            tags=["marketplace", "zbj"],
            metadata=metadata,
        )

    for match in _ZBJ_TASK_CARD_RE.finditer(payload):
        task_id = match.group("task_id")
        raw_title = _normalize_text(match.group("title")) or ""
        location, title = _split_location_title(raw_title)
        state = _normalize_text(match.group("state"))
        guid = f"zbj:{task_id}"
        if guid in items_by_guid:
            continue
        items_by_guid[guid] = ParsedMarketplaceLead(
            guid=guid,
            title=title or raw_title,
            summary=_join_summary(
                title or raw_title,
                budget=_normalize_text(match.group("budget")),
                timeline=state,
                platform="猪八戒",
            ),
            description=state,
            link=urljoin(source.url, match.group("href")),
            published_at=None,
            author=None,
            tags=["marketplace", "zbj"],
            metadata={
                "platform": "猪八戒",
                "category": str(source.config.get("topic") or source.category or "").strip() or None,
                "budget": _normalize_text(match.group("budget")),
                "timeline": state,
                "engagement": "fixed-price",
                "location": location,
                "skills": [],
                "bids": None,
            },
        )

    items = list(items_by_guid.values())
    if not items:
        raise ValueError("failed to parse zbj marketplace listing")
    return items


def _join_summary(
    title: str,
    *,
    budget: str | None,
    timeline: str | None,
    platform: str,
) -> str:
    extras = [value for value in (budget, timeline) if value]
    if not extras:
        return f"{title} | {platform}"
    return f"{title} | {' | '.join(extras)}"


def _split_budget_timeline(detail: str) -> tuple[str | None, str | None]:
    text = _normalize_text(detail)
    if not text:
        return None, None

    budget = text
    timeline_parts: list[str] = []

    if "Duration:" in budget:
        budget, duration = budget.split("Duration:", 1)
        timeline_parts.append(_clean_timeline_text(f"Duration: {duration}"))
    elif "Delivery time:" in budget:
        budget, delivery = budget.split("Delivery time:", 1)
        timeline_parts.append(_clean_timeline_text(f"Delivery time: {delivery}"))

    hours_match = _TRAILING_HOURS_RE.match(budget)
    if hours_match:
        budget = hours_match.group("budget")
        timeline_parts.insert(0, _normalize_text(hours_match.group("hours")) or "")

    engagement_match = _TRAILING_ENGAGEMENT_RE.match(budget)
    if engagement_match:
        budget = engagement_match.group("budget")
        timeline_parts.insert(0, _normalize_text(engagement_match.group("engagement")) or "")

    cleaned_budget = _normalize_text(budget)
    cleaned_timeline = _normalize_text(" | ".join(part for part in timeline_parts if part))
    return cleaned_budget, cleaned_timeline


def _clean_timeline_text(value: str) -> str:
    text = _normalize_text(value) or ""
    text = re.sub(r"(?<=[A-Za-z])\(", " (", text)
    return _normalize_text(text) or value


def _infer_engagement(value: str | None) -> str | None:
    text = _normalize_text(value)
    if not text:
        return None
    lowered = text.lower()
    if "/ hr" in lowered or "hrs/wk" in lowered:
        return "hourly"
    if "/mo" in lowered or "ongoing" in lowered:
        return "monthly"
    if "one-time" in lowered:
        return "one-time"
    return None


def _split_location_title(value: str) -> tuple[str | None, str]:
    text = _normalize_text(value) or ""
    if "：" in text:
        location, title = text.split("：", 1)
        return _normalize_text(location), _normalize_text(title) or text
    if ":" in text:
        location, title = text.split(":", 1)
        return _normalize_text(location), _normalize_text(title) or text
    return None, text


def _filter_marketplace_items(
    source: RssSource,
    items: list[ParsedMarketplaceLead],
) -> list[ParsedMarketplaceLead]:
    include_keywords = _normalize_keywords(source.config.get("include_keywords"))
    exclude_keywords = _normalize_keywords(source.config.get("exclude_keywords"))
    if not include_keywords and not exclude_keywords:
        return items

    filtered: list[ParsedMarketplaceLead] = []
    for item in items:
        haystack = _build_keyword_haystack(item)
        if include_keywords and not any(keyword in haystack for keyword in include_keywords):
            continue
        if exclude_keywords and any(keyword in haystack for keyword in exclude_keywords):
            continue
        filtered.append(item)
    return filtered


def _normalize_keywords(value: object) -> list[str]:
    if isinstance(value, str):
        return [text.lower() for item in value.split(",") if (text := _normalize_text(item))]
    if not isinstance(value, list):
        return []
    normalized = []
    for item in value:
        text = _normalize_text(item)
        if text:
            normalized.append(text.lower())
    return normalized


def _strip_html_tags(value: str) -> str | None:
    text = re.sub(r"<[^>]+>", " ", value)
    return _normalize_text(text)


def _parse_pubdate(value: str | None) -> datetime | None:
    text = _normalize_text(value)
    if not text:
        return None
    try:
        parsed = parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _extract_wwr_compensation(description: str | None) -> str | None:
    text = _normalize_text(description)
    if not text:
        return None
    match = _WWR_COMPENSATION_RE.search(text)
    return match.group(0) if match else None


def _infer_wwr_engagement(title: str, description: str | None) -> str:
    haystack = " ".join(part for part in (title, description or "") if part).lower()
    if any(keyword in haystack for keyword in _WWR_CONTRACT_HINTS):
        return "contract"
    return "full-time"


def _build_keyword_haystack(item: ParsedMarketplaceLead) -> str:
    fields = [
        item.title,
        item.summary,
        item.description,
        item.metadata.get("category"),
        item.metadata.get("location"),
        " ".join(item.tags),
        " ".join(str(skill) for skill in item.metadata.get("skills", []) if skill),
    ]
    return " ".join(_normalize_text(field) or "" for field in fields if field).lower()


def _build_anchor_lookup(payload: str, base_url: str) -> dict[str, list[str]]:
    parser = _AnchorCollector(base_url)
    parser.feed(payload)
    mapping: dict[str, list[str]] = {}
    for text, href in parser.links:
        mapping.setdefault(text, []).append(href)
    return mapping


def _lookup_anchor_href(mapping: dict[str, list[str]], text: str) -> str | None:
    candidates = mapping.get(text) or []
    for href in candidates:
        if href:
            return href
    return None


def _extract_lines(payload: str) -> list[str]:
    parser = _TextCollector()
    parser.feed(payload)
    lines = []
    for line in parser.text.splitlines():
        normalized = _normalize_text(line)
        if normalized:
            lines.append(normalized)
    return lines


def _looks_like_skill_token(value: str) -> bool:
    text = _normalize_text(value)
    if not text:
        return False
    if len(text) > 40:
        return False
    if any(marker in text for marker in (".", "•", ":", "(", ")")):
        return False
    return True


def _parse_date(value: str | None) -> datetime | None:
    text = _normalize_text(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text).replace(tzinfo=UTC)
    except ValueError:
        return None


def _parse_datetime(value: object) -> datetime | None:
    text = _normalize_text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _format_jobicy_salary(job: dict[str, Any]) -> str | None:
    currency = _normalize_text(job.get("salaryCurrency"))
    period = _normalize_text(job.get("salaryPeriod"))
    minimum = job.get("salaryMin")
    maximum = job.get("salaryMax")
    if minimum in (None, "") and maximum in (None, ""):
        return None

    prefix = "$" if currency == "USD" else f"{currency or ''} ".strip()
    if minimum not in (None, "") and maximum not in (None, ""):
        amount = f"{prefix}{minimum:,} - {prefix}{maximum:,}"
    elif minimum not in (None, ""):
        amount = f"{prefix}{minimum:,}+"
    else:
        amount = f"up to {prefix}{maximum:,}"
    return f"{amount}/{period}" if period else amount


def _infer_jobicy_engagement(job_types: list[str], haystack: str) -> str:
    normalized_types = {job_type.lower() for job_type in job_types}
    if "contract" in normalized_types:
        return "contract"
    if "freelance" in normalized_types:
        return "freelance"
    if "hour equivalent" in haystack or "hours per week" in haystack:
        return "hourly-contract"
    if "project-based" in haystack or "non-permanent" in haystack or "freelance" in haystack:
        return "project-based"
    if "b2b" in haystack:
        return "b2b"
    return "contract-like"


def _extract_remotive_skills(job: dict[str, Any]) -> list[str]:
    candidates = job.get("tags")
    if not isinstance(candidates, list):
        return []
    skills: list[str] = []
    for item in candidates:
        text = _normalize_text(item)
        if text:
            skills.append(text)
    return skills


def _extract_jobicy_skills(title: str | None, description: str | None, industry: str | None) -> list[str]:
    haystack = " ".join(part for part in (title or "", description or "", industry or "") if part).lower()
    skills: list[str] = []
    for keyword in _MARKETPLACE_SKILL_HINTS:
        if keyword in haystack:
            skills.append(keyword)
    if industry:
        skills.append(industry)
    return list(dict.fromkeys(skills))


def _coerce_item_limit(value: Any) -> int:
    try:
        parsed = int(value) if value is not None else 20
    except (TypeError, ValueError):
        parsed = 20
    return max(1, min(parsed, 50))


def _normalize_text(value: object) -> str | None:
    if value is None:
        return None
    text = html.unescape(str(value))
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text or None


class _TextCollector(HTMLParser):
    _BLOCK_TAGS = {
        "p",
        "div",
        "section",
        "article",
        "header",
        "footer",
        "main",
        "aside",
        "li",
        "ul",
        "ol",
        "tr",
        "td",
        "th",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "br",
    }

    def __init__(self) -> None:
        super().__init__()
        self.text = ""
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._ignored_depth += 1
            return
        if self._ignored_depth == 0 and tag in self._BLOCK_TAGS:
            self.text += "\n"

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._ignored_depth > 0:
            self._ignored_depth -= 1
            return
        if self._ignored_depth == 0 and tag in self._BLOCK_TAGS:
            self.text += "\n"

    def handle_data(self, data: str) -> None:
        if self._ignored_depth == 0:
            self.text += data


class _AnchorCollector(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self._base_url = base_url
        self._current_href: str | None = None
        self._current_parts: list[str] = []
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        href = dict(attrs).get("href")
        self._current_href = urljoin(self._base_url, href) if href else None
        self._current_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or not self._current_href:
            self._current_href = None
            self._current_parts = []
            return
        text = _normalize_text(" ".join(self._current_parts))
        if text:
            self.links.append((text, self._current_href))
        self._current_href = None
        self._current_parts = []

    def handle_data(self, data: str) -> None:
        if self._current_href:
            self._current_parts.append(data)
