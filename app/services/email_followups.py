"""Email follow-up queue for marketplace and customer radar leads."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from app.db.storage import db
from app.models import RawEntry, SourceType
from app.services import (
    candidate_needs,
    customer_radar,
    marketplace_leads,
    raw_entries,
    rss_sources,
)

_METADATA_KEY = "email_follow_up"
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")
_MARKETPLACE_SCAN_LIMIT = 600
_CUSTOMER_RADAR_SCAN_LIMIT = 240


class EmailFollowUpSource(StrEnum):
    ALL = "all"
    MARKETPLACE = "marketplace"
    CUSTOMER_RADAR = "customer_radar"


class EmailFollowUpStatus(StrEnum):
    DRAFT_READY = "draft_ready"
    DRAFTED = "drafted"
    SENT = "sent"
    REPLIED = "replied"
    NO_RESPONSE = "no_response"
    CLOSED = "closed"
    SKIPPED = "skipped"


class EmailFollowUpAction(StrEnum):
    CREATE_DRAFT = "create_draft"
    SEND_AFTER_REVIEW = "send_after_review"
    CHECK_REPLY = "check_reply"
    CLOSE_OR_RETRY = "close_or_retry"
    CLOSED = "closed"


@dataclass(slots=True)
class EmailDraft:
    recipient: str | None
    subject: str
    body: str
    source_url: str | None
    gmail_query_hint: str | None
    codex_handoff: str


@dataclass(slots=True)
class EmailFollowUpEvent:
    event_type: str
    created_at: datetime
    status_from: str | None = None
    status_to: str | None = None
    note: str | None = None


@dataclass(slots=True)
class EmailFollowUpTask:
    id: str
    raw_entry_id: int
    lead_id: int | None
    candidate_need_id: int | None
    opportunity_id: str | None
    source: EmailFollowUpSource
    title: str
    source_name: str
    platform: str | None
    source_url: str | None
    priority_score: int
    reason: str
    recommended_action: EmailFollowUpAction
    status: EmailFollowUpStatus
    recipient: str | None
    next_follow_up_at: datetime | None
    last_action_at: datetime
    risk_flags: list[str]
    evidence: list[str]
    draft: EmailDraft
    events: list[EmailFollowUpEvent]
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class EmailFollowUpSummary:
    total: int
    draft_ready: int
    drafted: int
    sent: int
    waiting_reply: int
    no_response: int
    replied: int
    closed: int
    skipped: int
    needs_recipient: int
    overdue: int


@dataclass(slots=True)
class EmailFollowUpResult:
    total: int
    summary: EmailFollowUpSummary
    items: list[EmailFollowUpTask]


def query_followups(
    *,
    source: EmailFollowUpSource = EmailFollowUpSource.ALL,
    status: EmailFollowUpStatus | None = None,
    min_score: int = 70,
    include_review_first: bool = True,
    skip: int = 0,
    limit: int = 30,
) -> EmailFollowUpResult:
    """Build a unified queue of email follow-up tasks."""

    tasks: list[EmailFollowUpTask] = []
    if source in {EmailFollowUpSource.ALL, EmailFollowUpSource.MARKETPLACE}:
        tasks.extend(_marketplace_tasks(min_score=min_score, scan_limit=_MARKETPLACE_SCAN_LIMIT))

    filtered_marketplace_count = len(_filter_tasks(tasks, status))
    should_scan_customer_radar = source == EmailFollowUpSource.CUSTOMER_RADAR or (
        source == EmailFollowUpSource.ALL and filtered_marketplace_count < skip + limit
    )
    if should_scan_customer_radar:
        tasks.extend(
            _customer_radar_tasks(
                min_score=min_score,
                include_review_first=include_review_first,
                scan_limit=_CUSTOMER_RADAR_SCAN_LIMIT,
            )
        )

    tasks = _filter_tasks(tasks, status)

    tasks.sort(key=_task_sort_key)
    total = len(tasks)
    page_items = tasks[skip : skip + limit]
    return EmailFollowUpResult(
        total=total,
        summary=_summarize(tasks),
        items=page_items,
    )


def _filter_tasks(
    tasks: list[EmailFollowUpTask],
    status: EmailFollowUpStatus | None,
) -> list[EmailFollowUpTask]:
    if status is None:
        return tasks
    return [task for task in tasks if task.status == status]


def get_followup_task(raw_entry_id: int) -> EmailFollowUpTask:
    """Return one follow-up task, falling back to raw entry metadata when needed."""

    entry = raw_entries.get_entry(raw_entry_id)
    source = rss_sources.get_source(entry.source_id)
    if source and source.source_type == SourceType.FREELANCE_MARKETPLACE:
        return _marketplace_task(_marketplace_lead_from_entry(entry), entry)

    need = candidate_needs.get_need_by_raw_entry(raw_entry_id)
    if need is not None and source is not None:
        opportunity = customer_radar._build_opportunity(need, entry, source)
        return _customer_radar_task(opportunity, entry)

    return _raw_entry_task(entry)


def update_followup_status(
    raw_entry_id: int,
    *,
    status: EmailFollowUpStatus,
    note: str | None = None,
    recipient: str | None = None,
    gmail_thread_id: str | None = None,
    next_follow_up_at: datetime | None = None,
) -> EmailFollowUpTask:
    """Update email follow-up state and mirror key marketplace status transitions."""

    entry = raw_entries.get_entry(raw_entry_id)
    source = rss_sources.get_source(entry.source_id)
    now = datetime.now(UTC)
    default_next_follow_up_at = None
    if status == EmailFollowUpStatus.SENT and next_follow_up_at is None:
        default_next_follow_up_at = now + timedelta(days=3)
    normalized_next_follow_up_at = _ensure_utc(
        next_follow_up_at or default_next_follow_up_at
    )
    cleaned_note = note.strip() if isinstance(note, str) and note.strip() else None
    cleaned_recipient = (
        recipient.strip() if isinstance(recipient, str) and recipient.strip() else None
    )
    cleaned_thread_id = (
        gmail_thread_id.strip()
        if isinstance(gmail_thread_id, str) and gmail_thread_id.strip()
        else None
    )

    def _apply(model: RawEntry) -> None:
        metadata = dict(model.metadata or {})
        state = _state_from_metadata(metadata)
        previous_status = _status_from_state(state, entry=entry, source_type=source.source_type if source else None)
        state["status"] = status.value
        state["last_action_at"] = now.isoformat()
        if cleaned_note:
            state["last_note"] = cleaned_note
        if cleaned_recipient:
            state["recipient"] = cleaned_recipient
        if cleaned_thread_id:
            state["gmail_thread_id"] = cleaned_thread_id
        if normalized_next_follow_up_at:
            state["next_follow_up_at"] = normalized_next_follow_up_at.isoformat()
        elif status in {EmailFollowUpStatus.REPLIED, EmailFollowUpStatus.CLOSED}:
            state.pop("next_follow_up_at", None)
        state["events"] = _append_event(
            state.get("events"),
            event_type="status_changed",
            status_from=previous_status.value,
            status_to=status.value,
            note=cleaned_note,
            created_at=now,
        )
        metadata[_METADATA_KEY] = state
        model.metadata = metadata

    db.update_raw_entry(raw_entry_id, _apply)

    if source and source.source_type == SourceType.FREELANCE_MARKETPLACE:
        if status == EmailFollowUpStatus.SENT:
            marketplace_leads.update_lead_status(
                raw_entry_id,
                marketplace_leads.MarketplaceLeadStatus.CONTACTED,
            )
            marketplace_leads.update_lead_follow_up(
                raw_entry_id,
                normalized_next_follow_up_at,
                "email_reply_check",
            )
        elif status == EmailFollowUpStatus.NO_RESPONSE:
            marketplace_leads.update_lead_outcome(
                raw_entry_id,
                marketplace_leads.MarketplaceLeadOutcome.NO_RESPONSE,
                ["email_no_response"],
            )
        elif status == EmailFollowUpStatus.REPLIED:
            marketplace_leads.update_lead_follow_up(raw_entry_id, None, None)

    return get_followup_task(raw_entry_id)


def _marketplace_tasks(*, min_score: int, scan_limit: int) -> list[EmailFollowUpTask]:
    _, entries = raw_entries.list_entries(
        source_type=SourceType.FREELANCE_MARKETPLACE,
        skip=0,
        limit=scan_limit,
    )
    tasks: list[EmailFollowUpTask] = []
    for entry in entries:
        try:
            lead = _marketplace_lead_from_entry(entry)
        except Exception:
            continue
        if lead.lead_kind not in {
            marketplace_leads.MarketplaceLeadKind.PROJECT,
            marketplace_leads.MarketplaceLeadKind.CONTRACT_ROLE,
        }:
            continue
        if lead.priority_score < min_score and not lead.is_follow_up_overdue:
            continue
        if lead.lead_outcome in {
            marketplace_leads.MarketplaceLeadOutcome.WON,
            marketplace_leads.MarketplaceLeadOutcome.LOST,
            marketplace_leads.MarketplaceLeadOutcome.NOT_FIT,
        }:
            continue
        tasks.append(_marketplace_task(lead, entry))
    return tasks


def _marketplace_lead_from_entry(entry: RawEntry) -> marketplace_leads.MarketplaceLead:
    lead = marketplace_leads._to_marketplace_lead(entry)
    context = marketplace_leads.MarketplacePriorityContext(
        source_history={},
        now=datetime.now(UTC),
    )
    return marketplace_leads._with_priority(lead, context)


def _marketplace_task(
    lead: marketplace_leads.MarketplaceLead,
    entry: RawEntry,
) -> EmailFollowUpTask:
    state = _state(entry)
    status = _status_from_state(
        state,
        entry=entry,
        source_type=SourceType.FREELANCE_MARKETPLACE,
    )
    recipient = _recipient_from_state_or_entry(state, entry)
    next_follow_up_at = _state_datetime(state, "next_follow_up_at") or lead.next_follow_up_at
    draft = _marketplace_draft(lead, entry, recipient)
    reason = lead.priority_reason
    if lead.is_follow_up_overdue:
        reason = f"Follow-up overdue. {reason}"
    return EmailFollowUpTask(
        id=f"marketplace-{lead.id}",
        raw_entry_id=lead.id,
        lead_id=lead.id,
        candidate_need_id=None,
        opportunity_id=None,
        source=EmailFollowUpSource.MARKETPLACE,
        title=lead.title,
        source_name=lead.source_name,
        platform=lead.platform,
        source_url=lead.link,
        priority_score=lead.priority_score,
        reason=reason,
        recommended_action=_recommended_action(status),
        status=status,
        recipient=recipient,
        next_follow_up_at=next_follow_up_at,
        last_action_at=_state_datetime(state, "last_action_at") or lead.last_action_at,
        risk_flags=[],
        evidence=[value for value in [lead.summary, lead.description] if value][:2],
        draft=draft,
        events=_events_from_state(state),
        created_at=lead.created_at,
        updated_at=lead.updated_at,
    )


def _customer_radar_tasks(
    *,
    min_score: int,
    include_review_first: bool,
    scan_limit: int,
) -> list[EmailFollowUpTask]:
    allowed_actions = {customer_radar.RecommendedAction.CONTACT_NOW}
    if include_review_first:
        allowed_actions.add(customer_radar.RecommendedAction.REVIEW_FIRST)
    tasks: list[EmailFollowUpTask] = []
    _, needs = candidate_needs.list_needs(
        source_type=SourceType.FREELANCE_MARKETPLACE,
        review_ready_only=True,
        skip=0,
        limit=scan_limit,
    )
    for need in needs:
        entry = raw_entries.get_entry(need.raw_entry_id)
        source = rss_sources.get_source(entry.source_id)
        if source is None:
            continue
        try:
            opportunity = customer_radar._build_opportunity(need, entry, source)
        except Exception:
            continue
        if opportunity.fit_score < min_score:
            continue
        if opportunity.recommended_action not in allowed_actions:
            continue
        tasks.append(_customer_radar_task(opportunity, entry))
    return tasks


def _customer_radar_task(
    opportunity: customer_radar.CustomerOpportunity,
    entry: RawEntry,
) -> EmailFollowUpTask:
    state = _state(entry)
    status = _status_from_state(state, entry=entry, source_type=entry_source_type(entry))
    recipient = _recipient_from_state_or_entry(state, entry)
    draft = _customer_radar_draft(opportunity, entry, recipient)
    return EmailFollowUpTask(
        id=f"customer-radar-{opportunity.raw_entry_id}",
        raw_entry_id=opportunity.raw_entry_id,
        lead_id=None,
        candidate_need_id=opportunity.candidate_need_id,
        opportunity_id=opportunity.id,
        source=EmailFollowUpSource.CUSTOMER_RADAR,
        title=opportunity.title,
        source_name=opportunity.source_name,
        platform=opportunity.platform,
        source_url=opportunity.link,
        priority_score=max(opportunity.fit_score, opportunity.credibility_score),
        reason=opportunity.product_angle,
        recommended_action=_recommended_action(status),
        status=status,
        recipient=recipient,
        next_follow_up_at=_state_datetime(state, "next_follow_up_at"),
        last_action_at=_state_datetime(state, "last_action_at") or opportunity.created_at,
        risk_flags=opportunity.risk_flags,
        evidence=opportunity.evidence,
        draft=draft,
        events=_events_from_state(state),
        created_at=opportunity.created_at,
        updated_at=entry.updated_at,
    )


def _raw_entry_task(entry: RawEntry) -> EmailFollowUpTask:
    source = rss_sources.get_source(entry.source_id)
    state = _state(entry)
    status = _status_from_state(state, entry=entry, source_type=source.source_type if source else None)
    recipient = _recipient_from_state_or_entry(state, entry)
    draft = _generic_draft(entry, recipient)
    return EmailFollowUpTask(
        id=f"raw-entry-{entry.id}",
        raw_entry_id=entry.id,
        lead_id=None,
        candidate_need_id=None,
        opportunity_id=None,
        source=EmailFollowUpSource.CUSTOMER_RADAR,
        title=entry.title,
        source_name=source.name if source else f"Source #{entry.source_id}",
        platform=_metadata_string(entry, "platform"),
        source_url=entry.link,
        priority_score=int(_state_from_metadata(entry.metadata).get("priority_score") or 0),
        reason=str(_state_from_metadata(entry.metadata).get("reason") or "Manual email follow-up"),
        recommended_action=_recommended_action(status),
        status=status,
        recipient=recipient,
        next_follow_up_at=_state_datetime(state, "next_follow_up_at"),
        last_action_at=_state_datetime(state, "last_action_at") or entry.updated_at,
        risk_flags=[],
        evidence=[value for value in [entry.summary, entry.content] if value][:2],
        draft=draft,
        events=_events_from_state(state),
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


def entry_source_type(entry: RawEntry) -> SourceType | None:
    source = rss_sources.get_source(entry.source_id)
    return source.source_type if source else None


def _recommended_action(status: EmailFollowUpStatus) -> EmailFollowUpAction:
    if status == EmailFollowUpStatus.DRAFT_READY:
        return EmailFollowUpAction.CREATE_DRAFT
    if status == EmailFollowUpStatus.DRAFTED:
        return EmailFollowUpAction.SEND_AFTER_REVIEW
    if status == EmailFollowUpStatus.SENT:
        return EmailFollowUpAction.CHECK_REPLY
    if status == EmailFollowUpStatus.NO_RESPONSE:
        return EmailFollowUpAction.CLOSE_OR_RETRY
    return EmailFollowUpAction.CLOSED


def _marketplace_draft(
    lead: marketplace_leads.MarketplaceLead,
    entry: RawEntry,
    recipient: str | None,
) -> EmailDraft:
    title = _truncate(lead.title, 90)
    summary = _truncate(lead.summary or lead.description or "your project", 180)
    context = " / ".join(
        value
        for value in [lead.normalized_budget or lead.budget, lead.normalized_timeline or lead.timeline]
        if value
    )
    if _looks_chinese(" ".join([lead.title, lead.summary or "", lead.description or ""])):
        subject = f"关于「{title}」的项目沟通"
        body = (
            f"您好，我看到您发布的「{title}」项目。"
            f"目前理解的重点是：{summary}。\n\n"
            "我可以先帮您把需求拆成一个小的首版里程碑，再确认是否继续扩大范围。"
            "为了避免误判，想先确认三点：\n"
            "1. 当前最需要交付的核心结果是什么？\n"
            "2. 是否已有参考系统、现有数据或必须对接的接口？\n"
            "3. 预算和时间是否仍按项目描述执行？\n\n"
            "如果方便，我可以基于现有说明先给出一个简短方案和时间预估。"
        )
        if context:
            body += f"\n\n我看到的项目约束：{context}。"
    else:
        subject = f"Re: {title}"
        body = (
            f"Hi, I saw your project about \"{title}\". "
            f"My current read is: {summary}.\n\n"
            "I can help turn this into a small first milestone before committing to a larger build. "
            "A few quick questions so I do not misread the scope:\n"
            "1. What is the most important outcome for the first version?\n"
            "2. Do you already have reference systems, data, or APIs that must be integrated?\n"
            "3. Are the budget and timeline in the project post still current?\n\n"
            "If helpful, I can send back a short implementation plan and estimate from the details you already shared."
        )
        if context:
            body += f"\n\nProject constraints I noticed: {context}."
    return _draft(
        recipient=recipient,
        subject=subject,
        body=body,
        source_url=lead.link or entry.link,
    )


def _customer_radar_draft(
    opportunity: customer_radar.CustomerOpportunity,
    entry: RawEntry,
    recipient: str | None,
) -> EmailDraft:
    title = _truncate(opportunity.title, 90)
    subject = f"Quick idea for {title}"
    body = opportunity.outreach_draft
    if opportunity.risk_flags:
        body += "\n\nA small sample would also help confirm whether this is the right fit before discussing a larger scope."
    return _draft(
        recipient=recipient,
        subject=subject,
        body=body,
        source_url=opportunity.link or entry.link,
    )


def _generic_draft(entry: RawEntry, recipient: str | None) -> EmailDraft:
    title = _truncate(entry.title, 90)
    summary = _truncate(entry.summary or entry.content or "your request", 180)
    subject = f"Re: {title}"
    body = (
        f"Hi, I saw your request about \"{title}\". "
        f"My current read is: {summary}.\n\n"
        "If helpful, I can send a short first-step plan and validate the scope with a small sample before any larger commitment."
    )
    return _draft(recipient=recipient, subject=subject, body=body, source_url=entry.link)


def _draft(
    *,
    recipient: str | None,
    subject: str,
    body: str,
    source_url: str | None,
) -> EmailDraft:
    gmail_query_hint = f'to:{recipient} OR from:{recipient}' if recipient else f'subject:"{_truncate(subject, 60)}"'
    recipient_text = recipient or "[confirm recipient]"
    codex_handoff = (
        "Use the Gmail connector to create a draft only after the recipient is confirmed.\n"
        f"Recipient: {recipient_text}\n"
        f"Subject: {subject}\n"
        f"Body:\n{body}"
    )
    return EmailDraft(
        recipient=recipient,
        subject=subject,
        body=body,
        source_url=source_url,
        gmail_query_hint=gmail_query_hint,
        codex_handoff=codex_handoff,
    )


def _summarize(tasks: list[EmailFollowUpTask]) -> EmailFollowUpSummary:
    now = datetime.now(UTC)
    return EmailFollowUpSummary(
        total=len(tasks),
        draft_ready=sum(1 for task in tasks if task.status == EmailFollowUpStatus.DRAFT_READY),
        drafted=sum(1 for task in tasks if task.status == EmailFollowUpStatus.DRAFTED),
        sent=sum(1 for task in tasks if task.status == EmailFollowUpStatus.SENT),
        waiting_reply=sum(1 for task in tasks if task.status == EmailFollowUpStatus.SENT),
        no_response=sum(1 for task in tasks if task.status == EmailFollowUpStatus.NO_RESPONSE),
        replied=sum(1 for task in tasks if task.status == EmailFollowUpStatus.REPLIED),
        closed=sum(1 for task in tasks if task.status == EmailFollowUpStatus.CLOSED),
        skipped=sum(1 for task in tasks if task.status == EmailFollowUpStatus.SKIPPED),
        needs_recipient=sum(
            1
            for task in tasks
            if not task.recipient
            and task.status
            in {EmailFollowUpStatus.DRAFT_READY, EmailFollowUpStatus.DRAFTED}
        ),
        overdue=sum(
            1
            for task in tasks
            if task.next_follow_up_at is not None
            and _ensure_utc(task.next_follow_up_at) <= now
            and task.status
            in {EmailFollowUpStatus.SENT, EmailFollowUpStatus.NO_RESPONSE}
        ),
    )


def _task_sort_key(task: EmailFollowUpTask) -> tuple[int, int, int, float]:
    status_rank = {
        EmailFollowUpStatus.DRAFT_READY: 0,
        EmailFollowUpStatus.DRAFTED: 1,
        EmailFollowUpStatus.SENT: 2,
        EmailFollowUpStatus.NO_RESPONSE: 3,
        EmailFollowUpStatus.REPLIED: 4,
        EmailFollowUpStatus.CLOSED: 5,
        EmailFollowUpStatus.SKIPPED: 6,
    }[task.status]
    overdue_rank = 0
    if task.next_follow_up_at and _ensure_utc(task.next_follow_up_at) <= datetime.now(UTC):
        overdue_rank = -1
    recency = _ensure_utc(task.created_at).timestamp()
    return (status_rank, overdue_rank, -task.priority_score, -recency)


def _state(entry: RawEntry) -> dict[str, Any]:
    return _state_from_metadata(entry.metadata)


def _state_from_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    value = (metadata or {}).get(_METADATA_KEY)
    return dict(value) if isinstance(value, dict) else {}


def _status_from_state(
    state: dict[str, Any],
    *,
    entry: RawEntry,
    source_type: SourceType | None,
) -> EmailFollowUpStatus:
    raw_status = state.get("status")
    if isinstance(raw_status, str):
        try:
            return EmailFollowUpStatus(raw_status)
        except ValueError:
            pass
    if source_type == SourceType.FREELANCE_MARKETPLACE:
        lead_status = str(entry.metadata.get("lead_status") or "")
        lead_outcome = str(entry.metadata.get("lead_outcome") or "")
        if lead_outcome == marketplace_leads.MarketplaceLeadOutcome.NO_RESPONSE.value:
            return EmailFollowUpStatus.NO_RESPONSE
        if lead_status == marketplace_leads.MarketplaceLeadStatus.CONTACTED.value:
            return EmailFollowUpStatus.SENT
    return EmailFollowUpStatus.DRAFT_READY


def _recipient_from_state_or_entry(state: dict[str, Any], entry: RawEntry) -> str | None:
    recipient = state.get("recipient")
    if isinstance(recipient, str) and _EMAIL_RE.fullmatch(recipient.strip()):
        return recipient.strip()
    return _extract_recipient(entry)


def _extract_recipient(entry: RawEntry) -> str | None:
    candidates: list[str] = []
    for key in ("email", "contact_email", "client_email", "reply_to"):
        value = entry.metadata.get(key)
        if isinstance(value, str):
            candidates.append(value)
    candidates.extend(
        value
        for value in [entry.author, entry.summary, entry.content]
        if isinstance(value, str)
    )
    for value in candidates:
        match = _EMAIL_RE.search(value)
        if match:
            return match.group(0)
    return None


def _events_from_state(state: dict[str, Any]) -> list[EmailFollowUpEvent]:
    events: list[EmailFollowUpEvent] = []
    raw_events = state.get("events")
    if not isinstance(raw_events, list):
        return events
    for item in raw_events:
        if not isinstance(item, dict):
            continue
        created_at = _parse_datetime(item.get("created_at")) or datetime.now(UTC)
        events.append(
            EmailFollowUpEvent(
                event_type=str(item.get("event_type") or "status_changed"),
                created_at=created_at,
                status_from=_optional_string(item.get("status_from")),
                status_to=_optional_string(item.get("status_to")),
                note=_optional_string(item.get("note")),
            )
        )
    events.sort(key=lambda event: event.created_at, reverse=True)
    return events


def _append_event(
    events: Any,
    *,
    event_type: str,
    status_from: str | None,
    status_to: str | None,
    note: str | None,
    created_at: datetime,
) -> list[dict[str, Any]]:
    normalized = [dict(item) for item in events if isinstance(item, dict)] if isinstance(events, list) else []
    normalized.append(
        {
            "event_type": event_type,
            "created_at": created_at.isoformat(),
            "status_from": status_from,
            "status_to": status_to,
            "note": note,
        }
    )
    return normalized[-50:]


def _state_datetime(state: dict[str, Any], key: str) -> datetime | None:
    return _parse_datetime(state.get(key))


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return _ensure_utc(value)
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return _ensure_utc(datetime.fromisoformat(value))
    except ValueError:
        return None


def _ensure_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _metadata_string(entry: RawEntry, key: str) -> str | None:
    value = entry.metadata.get(key)
    return str(value) if isinstance(value, (str, int, float)) and str(value).strip() else None


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _looks_chinese(value: str) -> bool:
    return len(_CHINESE_RE.findall(value)) >= 4


def _truncate(value: str, length: int) -> str:
    cleaned = " ".join(str(value).split())
    if len(cleaned) <= length:
        return cleaned
    return f"{cleaned[: max(0, length - 3)].rstrip()}..."
