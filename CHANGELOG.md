# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
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
