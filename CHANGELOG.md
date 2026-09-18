# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- Free keyword validation tier: Google suggest endpoint existence check (no credentials, rate-limited, CJK-aware) used as the default `auto` provider fallback; confirmed phrases are marked `validated` with a `confirmed_by_suggest` badge and receive an opportunity-score bonus, while DataForSEO remains the paid upgrade for real volume data
- Singular-variant fallback in suggest validation: when a verbatim phrase (often plural) is not confirmed, up to two singularized variants are re-queried, since canonical search forms are usually singular (e.g. "convert pdfs to excel" → "convert pdf to excel")
- Keyword seed mining loop: extract tool-intent long-tail phrases (EN/ZH patterns) from candidate needs, aggregate evidence per phrase, optionally validate monthly search volume / difficulty / CPC via DataForSEO, and compute a 0-100 opportunity score combining lead intent with keyword metrics
- Keyword seeds API (`/api/v1/keyword-seeds/`) with list / extract / validate / shortlist endpoints and a Vue admin page (summary cards, filters, evidence drawer)
- Celery + APScheduler schedules for keyword extraction (6h) and validation (24h), with Prometheus metrics `needradar_keyword_seeds_extracted_total` / `needradar_keyword_validations_total`
- Multi-dimensional sorting for marketplace todo queue (default / newest / oldest / priority)
- Page title banner above filter controls for clearer visual hierarchy
- MIT LICENSE, enhanced README with architecture diagram, CONTRIBUTING.md

### Changed
- Polished todo panel UI: iOS-style segmented sort control, white todo cards with hover effects
- Priority score displayed as blue gradient pill badge
- Metric cards now maintain consistent height regardless of label length

### Fixed
- `_AnchorCollector` state reset bug caused by nested HTML tags inside `<a>`, affecting sxsoft link extraction
- Candidate needs returning empty due to missing trailing slash in API path
- Local stack `python3` → `python` for scheduler compatibility on macOS

## [0.1.0] - 2026-03

### Added
- Marketplace lead aggregation from 8+ sources (sxsoft, Freelancer, Jobicy, Remotive, WeWorkRemotely, PeoplePerHour, Contra, 猪八戒)
- Lead profiling: budget band, delivery scope, tech stack normalization, region, timezone fit
- Priority scoring and tiered queues (high_purity / expanded)
- Lead workflow: status tracking, outcome recording, notes, follow-up scheduling
- Conversion rate analytics and source effectiveness dashboard
- Source health monitoring and tuning recommendations
- Todo queue with severity-based reminders
- Candidate need extraction with rule engine + optional LLM review
- Candidate clustering and deduplication
- RSS source management with multi-format fetchers (RSS, HN, GitHub Issues, Reddit, YouTube)
- Fetch logging, filter metrics, and downstream sync (webhook / MQ / file_drop / export)
- FastAPI backend with SQLAlchemy async, Alembic migrations, Celery task queue
- Vue 3 + TypeScript + Element Plus web frontend with i18n (zh-CN / en)
- Docker Compose local stack with PostgreSQL, Redis, Prometheus
- GitHub Actions CI (ruff, pytest, mypy)
- Prometheus metrics and OpenTelemetry tracing support
