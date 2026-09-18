# NeedRadar

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/xiaof631/NeedRadar/actions/workflows/ci.yml/badge.svg)](https://github.com/xiaof631/NeedRadar/actions/workflows/ci.yml)

**从公开渠道聚合软件外包线索，用规则 + LLM 挖掘真实项目需求。**

NeedRadar 持续抓取自由职业平台、RSS 和公开 API 中的项目机会，自动解析项目画像（预算、技术栈、交付范围、地区），通过规则引擎和可选 LLM 识别高质量线索，并提供待办队列、跟进时间线和转化率复盘。

适用场景：独立开发者接外包、小型外包团队拓客、远程工作机会搜索。

## 架构概览

```
┌─────────────┐    ┌──────────────┐    ┌───────────────┐
│  Vue 3 Web   │───▶│  FastAPI      │───▶│  PostgreSQL    │
│  (Vite:5207) │    │  (uvicorn)    │    │  (:5406)       │
└─────────────┘    └──────┬───────┘    └───────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                  ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  Celery       │  │  APScheduler │  │  Redis        │
│  Worker       │  │  (cron jobs) │  │  (:6406)      │
└──────┬───────┘  └──────┬───────┘  └──────────────┘
       │                 │
       ▼                 ▼
┌──────────────────────────────────────────────┐
│  抓取层 (marketplace_fetcher / rss_fetcher)    │
│  软件项目交易网 · Freelancer · Jobicy ·        │
│  Remotive · WeWorkRemotely · PeoplePerHour ·  │
│  Contra · 猪八戒 · Reddit · HN · GitHub · RSS  │
└──────────────────────────────────────────────┘
```

> **数据抓取声明**：所有数据源均为公开可访问的网页或 API。NeedRadar 以合理的频率抓取公开信息，仅用于个人线索聚合。使用前请确认目标网站的 ToS 和使用条款。建议在 `rss_sources` 中将不需要的源设为 `paused`。

## 快速开始

1. 安装依赖：

   ```bash
   pip install -e .[dev]
   ```

2. 初始化数据库（默认连接本地 PostgreSQL `needradar` 库；测试环境会自动切换到 SQLite）：

   ```bash
   cp .env.example .env
   ```

   若本地 PostgreSQL 尚未启动，可直接使用仓库内的 Docker Compose：

   ```bash
   docker compose up -d postgres redis
   ```

   然后执行迁移：

   ```bash
   alembic upgrade head
   ```

3. 启动 API：

   ```bash
   uvicorn app.main:app --reload --port 3107
   ```

   也可以直接使用仓库自带的本地编排脚本统一启动/停止服务：

   ```bash
   ./scripts/local_stack.sh start
   ./scripts/local_stack.sh status
   ./scripts/local_stack.sh stop
   ```

   该脚本仅用于本地开发，仍然沿用现有的 `uvicorn` / `celery` / `python -m jobs.scheduler` / `pnpm` 命令，不替换正式部署入口。

4. 运行命令行工具查看配置：

   ```bash
   python -m cli.main show-config
   ```

   若要导入长期扩源用的 GitHub public issue 源目录，可执行：

   ```bash
   python -m cli.main rss seed-catalog --profile github-public-expanded
   ```

   若当前未配置 `NEEDRADAR_GITHUB_ACCESS_TOKEN`，该目录会默认以 `paused` 状态导入，避免调度器持续打出 GitHub `403` 失败日志；配置 token 后可重新导入或在后台批量改回 `active`。

5. 启动 Celery worker（负责执行 RSS 抓取、晋升与同步等耗时任务）：

   ```bash
   celery -A jobs.celery_app worker --loglevel=info
   ```

   > 注：仓库内包含的 `jobs.simple_celery` 仅用于离线/测试环境兜底，不具备真实的消息队列能力，部署环境请安装 `celery[redis]` 并启动独立 worker。

6. 使用 Celery beat 或 `jobs.scheduler` 启动调度器以周期性派发任务：

   ```bash
   # Celery beat（推荐）
   celery -A jobs.celery_app beat --loglevel=info

   # 或沿用 APScheduler 调度器
   python -m jobs.scheduler
   ```

7. 执行测试与代码质量检查（`python -m tools.coverage_runner` 会运行 pytest 并校验覆盖率 ≥ 75%）：

   ```bash
   ruff check
   python -m tools.coverage_runner
   mypy app/services jobs
   ```

   运行 `python -m tools.coverage_runner` 会在项目根目录生成 `coverage-summary.json`。针对主干的 push / PR（或手动触发 `workflow_dispatch`）时，CI 也会上传该文件以供审阅；若仅需在开发分支迭代，可在提交信息中追加 `[skip ci]` 以跳过流水线。

8. 访问 `http://localhost:8000/metrics` 即可查看 Prometheus 指标；若使用 `docker compose up`，可同时访问 `http://localhost:9090` 获取预置的 Prometheus 控制台。

9. 启动 Web 管理前端：

   ```bash
   cd web
   pnpm install
   pnpm dev # 本地调试，默认 http://localhost:5207
   pnpm build # 产出 dist/ 静态资源
   pnpm test # 运行 Vitest + Vue Test Utils
   ```

   > 前端默认从 `VITE_API_BASE_URL` 指向的 NeedRadar API 读取数据，若未设置则回落至 `http://localhost:3107`。

## 目录结构

- `app/`：FastAPI 应用、配置与数据库基础设施。
- `cli/`：Typer 命令行程序。
- `alembic/`：数据库迁移配置。
- `docs/`：需求、设计与开发文档。
- `web/`：Vue 3 + TypeScript + Vite 构建的管理前端，包含仪表盘、数据源、筛选监控等页面骨架与 Vitest 用例。
- `.github/workflows/`：CI 工作流定义，目前包含 `ci.yml`，默认只在主干 push / PR 或手动 `workflow_dispatch` 时运行 `ruff`、`pytest` 和 `mypy`，开发分支可通过 `[skip ci]` 提交避免流水线阻塞。

## 环境变量

复制 `.env.example` 为 `.env` 并根据需求调整：

```bash
cp .env.example .env
```

关键变量：

- `NEEDRADAR_DATABASE_URL`：异步 SQLAlchemy 连接串，默认使用 PostgreSQL `postgresql+asyncpg://needradar:needradar@localhost:5406/needradar`。
- `NEEDRADAR_ALEMBIC_DATABASE_URL`：可选，同步连接串用于 Alembic 迁移；未配置时会自动从 `asyncpg` 映射到 `psycopg`。
- `NEEDRADAR_API_TOKENS`：可选，逗号分隔的 API Token 列表，配置后所有 `/api` 请求需携带 `X-API-Key` 头或 `api_token` 查询参数。
- `NEEDRADAR_CELERY_BROKER_URL`：Celery 消息队列地址，默认指向 `redis://localhost:6406/0`。
- `NEEDRADAR_CELERY_RESULT_BACKEND`：Celery 任务结果存储地址，默认 Redis `1` 号库，可设为 `null` 关闭。
- `NEEDRADAR_CELERY_TASK_ALWAYS_EAGER`：调试/测试模式下是否同步执行任务，默认为 `False`。
- `NEEDRADAR_REDDIT_ACCESS_TOKEN` / `NEEDRADAR_REDDIT_USER_AGENT`：可选，配置后 Reddit 源走 OAuth JSON API；未配置 token 时会自动回退到公开 RSS。
- `NEEDRADAR_GITHUB_ACCESS_TOKEN`：可选，GitHub Issues 源在共享公网出口下建议配置，用于避免匿名 API rate limit。长期扩源场景建议使用 GitHub `Fine-grained personal access token`，仓库范围选 `All public repositories`，权限仅保留 `Issues: Read-only` 与 `Metadata: Read-only`。
- `NEEDRADAR_TELEMETRY_ENABLED`：是否启用 OpenTelemetry 采样与 Trace 导出，默认为 `False`。
- `NEEDRADAR_TELEMETRY_SERVICE_NAME`：Trace 中展示的服务名称，默认为 `needradar-api`。
- `NEEDRADAR_TELEMETRY_OTLP_ENDPOINT` / `NEEDRADAR_TELEMETRY_OTLP_INSECURE`：可选，指向外部 OTLP Collector；若为空则默认输出至控制台。
- `NEEDRADAR_TELEMETRY_SAMPLE_RATIO`：0-1 之间的采样率，默认为 `0.1`。
- `NEEDRADAR_TELEMETRY_EXCLUDED_URLS`：无需采样的 URL（逗号分隔），默认排除 `/metrics` 与 `/health`。
- `NEEDRADAR_DOWNSTREAM_FILESYSTEM_ENABLED` / `NEEDRADAR_DOWNSTREAM_FILESYSTEM_DIR` / `NEEDRADAR_DOWNSTREAM_FILESYSTEM_FORMAT`：启用基于文件系统的同步通道时需要的开关、输出目录与格式（支持 `jsonl`、`json`）。
- `NEEDRADAR_DATAFORSEO_API_LOGIN` / `NEEDRADAR_DATAFORSEO_API_PASSWORD`：可选，DataForSEO 凭据；配置后启用关键词种子的搜索量验证，未配置时降级为纯抽取模式。
- `NEEDRADAR_DATAFORSEO_SANDBOX`：DataForSEO 是否走沙箱环境，默认 `false`，可先用沙箱验证联调。
- `NEEDRADAR_KEYWORD_PROVIDER`：关键词验证数据源，`auto`（默认：有 DataForSEO 凭据用真实搜索量，否则退到免费的 Google suggest 存在性校验）/ `dataforseo` / `autocomplete` / `none`。
- `NEEDRADAR_KEYWORD_AUTOCOMPLETE_INTERVAL_MS`：免费 suggest 校验相邻请求的间隔（毫秒），默认 `800`，避免被限流。
- `NEEDRADAR_KEYWORD_VALIDATION_BATCH_SIZE`：单次批量验证的关键词种子数量上限，默认 `50`。
- `NEEDRADAR_SCHEDULER_KEYWORD_EXTRACT_INTERVAL_SECONDS` / `NEEDRADAR_SCHEDULER_KEYWORD_VALIDATE_INTERVAL_SECONDS`：关键词种子抽取（默认 6 小时）与搜索量验证（默认 24 小时）的调度间隔。

前端 `.env` 中可配置：

- `VITE_API_BASE_URL`：NeedRadar API 根地址，默认 `http://localhost:3107`。

## 关键词种子（关键词反选闭环）

从已挖掘的候选需求文本中自动抽取工具型长尾关键词（覆盖 `convert X to Y`、`X to Y converter`、`extract X from Y`、`X extractor`、`scrape X` 及中文 `X转成Y`、`从X提取Y` 等句式），按短语去重聚合出现次数并回链原始线索作为证据；结合搜索验证计算 0-100 机会分，用于反选下一个工具站方向。

验证分两档，默认全部免费可用：

- **免费档（默认，无需任何凭据）**：调用 Google suggest 公开端点做存在性校验——短语出现在自身联想列表（含前缀扩展）即标记为"真实搜索词"（`validated` + `confirmed_by_suggest`），并获得机会分加成；没有任何联想命中则标记 `no_volume`。原话常是复数形式而标准搜索词多为单数，未确认时会自动回查至多两个单数变体（如 `convert pdfs to excel` → `convert pdf to excel`）。请求间默认限速 1.5 秒、被限流时退避重试，中文短语自动切换 `hl=zh-CN`（并强制 `oe=utf-8` 避免该端点的 GBK 编码坑）。
- **数据档（可选升级）**：配置 DataForSEO 凭据后自动切换为真实月搜索量 / 关键词难度 / CPC 验证（按量付费，约 $0.09/次请求，单次可带千词）。

建议的免费工作流：批量验证筛出 `validated` 种子 → 按"出现次数 + 机会分"排序取 top 30 → 人工到 Google Keyword Planner 网页版核对真实搜索量后再立项。

- Web 端在"关键词种子"页面查看与操作：手动抽取、批量/单条验证、入围（shortlist）与忽略（dismiss），证据抽屉可直接跳转原始帖子。
- API 位于 `/api/v1/keyword-seeds/`（列表 / `extract` / `validate-pending` / `{id}/validate` / `{id}` PATCH）。
- 调度任务 `jobs.extract_keyword_seeds`（6h）与 `jobs.validate_keyword_seeds`（24h）已同时注册进 Celery beat 与 APScheduler。
- Prometheus 指标：`needradar_keyword_seeds_extracted_total{result}` 与 `needradar_keyword_validations_total{status}`。

## Docker 与 PostgreSQL

执行以下命令可启动包含 PostgreSQL、Redis、API、Celery Worker、Beat 及 Prometheus 的本地环境：

```bash
docker compose up --build
```

默认推荐仅用该编排启动基础设施服务：PostgreSQL 暴露到 `localhost:5406`，Redis 暴露到 `localhost:6406`。`api`、`worker`、`scheduler`、`prometheus` 已被放入 `fullstack` profile，只有显式声明时才会启动。若需要完整容器化运行，可执行 `docker compose --profile fullstack up --build`。Prometheus 容器会抓取本机 `3107` 端口上的本地 API `/metrics`。

如需脱离 PostgreSQL 做轻量本地验证，仍可在 `.env` 中手动改回 SQLite：

```bash
NEEDRADAR_DATABASE_URL=sqlite+aiosqlite:///./data/needradar.db
NEEDRADAR_ALEMBIC_DATABASE_URL=sqlite:///./data/needradar.db
```

## 监控与可观测性

- FastAPI 应用默认挂载 `/metrics`，通过 `app/core/metrics.py` 注入的请求包装统计 HTTP 数量、耗时，并输出 RSS 抓取、候选需求晋升与下游同步等业务指标。
- `monitoring/prometheus.yml` 提供最小可用的 Prometheus 配置，可直接用 docker-compose 中的 `prometheus` 服务加载。
- `monitoring/grafana_downstream.json` 是下游同步通道的 Grafana 仪表盘示例，包含成功率、状态拆分、最近错误以及 file drop 落盘耗时面板，导入后选择 Prometheus 数据源即可。
- 设置 `NEEDRADAR_TELEMETRY_ENABLED=true` 及对应的 OTLP Endpoint 后，`app/core/telemetry.py` 会自动为 FastAPI 与 Celery 任务注入 OpenTelemetry Trace，便于与 Jaeger/Tempo 等系统联动。
- 下游同步相关的 Prometheus 指标包括 `needradar_downstream_deliveries_total` 与 `needradar_downstream_file_drop_duration_seconds`，后者用于追踪 file drop 通道的写入耗时。
- 需要立即下发候选需求时，可使用 `python -m cli.main candidates sync --channel webhook --limit 20`（或 `mq`/`file_drop`/`all`）手动派发任务，并可配合 `--status`、`--webhook-url` 等参数。

## Web 管理前端

- 代码位于 `web/`，采用 Vue 3 + TypeScript + Vite + Element Plus，并接入 Pinia、Vue Router、Vue Query、Vue I18n；当前已启用按路由拆包与 vendor chunk 分离，降低首屏 bundle 体积。
- 页面包含仪表盘、RSS 源管理、原始内容、筛选监控、候选需求工作台与系统告警模块，提供示例数据与组件骨架，便于后续与后端 `/api/v1` 接口联调。
- 后端内置 `github-public-expanded` 目录，可一键导入一批长期扩源用的 GitHub issue 源，当前覆盖 Supabase、Next.js、Vercel AI SDK、OpenAI Python、LangChain、LangGraph、n8n、Activepieces、Cal.com 等公开仓库。
- 运行 `pnpm test` 可执行 Vitest + Vue Test Utils 单测，CI 亦可接入 `pnpm lint`、`pnpm build`。
