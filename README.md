# NeedRadar

NeedRadar 是一个用于从公开 RSS 数据源挖掘潜在“小工具”需求的系统。此仓库当前包含后端 API 的基础工程骨架。更多背景可参考 `docs/` 目录。

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
   uvicorn app.main:app --reload --port 3106
   ```

4. 运行命令行工具查看配置：

   ```bash
   python -m cli.main show-config
   ```

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
   pnpm dev # 本地调试，默认 http://localhost:5206
   pnpm build # 产出 dist/ 静态资源
   pnpm test # 运行 Vitest + Vue Test Utils
   ```

   > 前端默认从 `VITE_API_BASE_URL` 指向的 NeedRadar API 读取数据，若未设置则回落至 `http://localhost:3106`。

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
- `NEEDRADAR_TELEMETRY_ENABLED`：是否启用 OpenTelemetry 采样与 Trace 导出，默认为 `False`。
- `NEEDRADAR_TELEMETRY_SERVICE_NAME`：Trace 中展示的服务名称，默认为 `needradar-api`。
- `NEEDRADAR_TELEMETRY_OTLP_ENDPOINT` / `NEEDRADAR_TELEMETRY_OTLP_INSECURE`：可选，指向外部 OTLP Collector；若为空则默认输出至控制台。
- `NEEDRADAR_TELEMETRY_SAMPLE_RATIO`：0-1 之间的采样率，默认为 `0.1`。
- `NEEDRADAR_TELEMETRY_EXCLUDED_URLS`：无需采样的 URL（逗号分隔），默认排除 `/metrics` 与 `/health`。
- `NEEDRADAR_DOWNSTREAM_FILESYSTEM_ENABLED` / `NEEDRADAR_DOWNSTREAM_FILESYSTEM_DIR` / `NEEDRADAR_DOWNSTREAM_FILESYSTEM_FORMAT`：启用基于文件系统的同步通道时需要的开关、输出目录与格式（支持 `jsonl`、`json`）。

前端 `.env` 中可配置：

- `VITE_API_BASE_URL`：NeedRadar API 根地址，默认 `http://localhost:3106`。

## Docker 与 PostgreSQL

执行以下命令可启动包含 PostgreSQL、Redis、API、Celery Worker、Beat 及 Prometheus 的本地环境：

```bash
docker compose up --build
```

默认推荐仅用该编排启动基础设施服务：PostgreSQL 暴露到 `localhost:5406`，Redis 暴露到 `localhost:6406`。`api`、`worker`、`scheduler`、`prometheus` 已被放入 `fullstack` profile，只有显式声明时才会启动。若需要完整容器化运行，可执行 `docker compose --profile fullstack up --build`。Prometheus 容器会抓取本机 `3106` 端口上的本地 API `/metrics`。

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
- 运行 `pnpm test` 可执行 Vitest + Vue Test Utils 单测，CI 亦可接入 `pnpm lint`、`pnpm build`。
