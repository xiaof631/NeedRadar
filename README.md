# NeedRadar

NeedRadar 是一个用于从公开 RSS 数据源挖掘潜在“小工具”需求的系统。此仓库当前包含后端 API 的基础工程骨架。更多背景可参考 `docs/` 目录。

## 快速开始

1. 安装依赖：

   ```bash
   pip install -e .[dev]
   ```

2. 初始化数据库（默认 SQLite 文件位于 `./data/needradar.db`，也可通过 Docker 使用 PostgreSQL）：

   ```bash
   alembic upgrade head
   ```

3. 启动 API：

   ```bash
   uvicorn app.main:app --reload
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

   运行 `python -m tools.coverage_runner` 会在项目根目录生成 `coverage-summary.json`，CI 也会上传该文件以供审阅。

8. 访问 `http://localhost:8000/metrics` 即可查看 Prometheus 指标；若使用 `docker compose up`，可同时访问 `http://localhost:9090` 获取预置的 Prometheus 控制台。

9. 启动 Web 管理前端：

   ```bash
   cd web
   pnpm install
   pnpm dev # 本地调试
   pnpm build # 产出 dist/ 静态资源
   pnpm test # 运行 Vitest + Vue Test Utils
   ```

   > 前端默认从 `VITE_API_BASE_URL` 指向的 NeedRadar API 读取数据，若未设置则回落至 `http://localhost:8000`。

## 目录结构

- `app/`：FastAPI 应用、配置与数据库基础设施。
- `cli/`：Typer 命令行程序。
- `alembic/`：数据库迁移配置。
- `docs/`：需求、设计与开发文档。
- `web/`：Vue 3 + TypeScript + Vite 构建的管理前端，包含仪表盘、数据源、筛选监控等页面骨架与 Vitest 用例。
- `.github/workflows/`：CI 工作流定义，目前包含 `ci.yml`，在 PR 与 push 时自动运行 `ruff`、`pytest` 和 `mypy`。

## 环境变量

复制 `.env.example` 为 `.env` 并根据需求调整：

```bash
cp .env.example .env
```

关键变量：

- `NEEDRADAR_DATABASE_URL`：异步 SQLAlchemy 连接串，默认使用 SQLite。
- `NEEDRADAR_ALEMBIC_DATABASE_URL`：可选，同步连接串用于 Alembic 迁移。
- `NEEDRADAR_API_TOKENS`：可选，逗号分隔的 API Token 列表，配置后所有 `/api` 请求需携带 `X-API-Key` 头或 `api_token` 查询参数。
- `NEEDRADAR_CELERY_BROKER_URL`：Celery 消息队列地址，默认指向 `redis://localhost:6379/0`。
- `NEEDRADAR_CELERY_RESULT_BACKEND`：Celery 任务结果存储地址，默认 Redis `1` 号库，可设为 `null` 关闭。
- `NEEDRADAR_CELERY_TASK_ALWAYS_EAGER`：调试/测试模式下是否同步执行任务，默认为 `False`。
- `NEEDRADAR_TELEMETRY_ENABLED`：是否启用 OpenTelemetry 采样与 Trace 导出，默认为 `False`。
- `NEEDRADAR_TELEMETRY_SERVICE_NAME`：Trace 中展示的服务名称，默认为 `needradar-api`。
- `NEEDRADAR_TELEMETRY_OTLP_ENDPOINT` / `NEEDRADAR_TELEMETRY_OTLP_INSECURE`：可选，指向外部 OTLP Collector；若为空则默认输出至控制台。
- `NEEDRADAR_TELEMETRY_SAMPLE_RATIO`：0-1 之间的采样率，默认为 `0.1`。
- `NEEDRADAR_TELEMETRY_EXCLUDED_URLS`：无需采样的 URL（逗号分隔），默认排除 `/metrics` 与 `/health`。
- `NEEDRADAR_DOWNSTREAM_FILESYSTEM_ENABLED` / `NEEDRADAR_DOWNSTREAM_FILESYSTEM_DIR` / `NEEDRADAR_DOWNSTREAM_FILESYSTEM_FORMAT`：启用基于文件系统的同步通道时需要的开关、输出目录与格式（支持 `jsonl`、`json`）。

前端 `.env` 中可配置：

- `VITE_API_BASE_URL`：NeedRadar API 根地址，默认 `http://localhost:8000`。

## Docker 与 PostgreSQL

执行以下命令可启动包含 PostgreSQL、Redis、API、Celery Worker、Beat 及 Prometheus 的本地环境：

```bash
docker compose up --build
```

该组合会默认使用 `postgresql+asyncpg` 连接串，并在 `postgres-data`、`redis-data` 卷中持久化数据。Celery beat 会根据配置每隔一段时间扫描数据库，并向 worker 派发抓取/晋升/同步任务。Prometheus 使用 `monitoring/prometheus.yml` 中的配置抓取 `api:8000/metrics` 指标，首次启动前仍需执行 `alembic upgrade head` 以创建表结构。

## 监控与可观测性

- FastAPI 应用默认挂载 `/metrics`，通过 `app/core/metrics.py` 注入的请求包装统计 HTTP 数量、耗时，并输出 RSS 抓取、候选需求晋升与下游同步等业务指标。
- `monitoring/prometheus.yml` 提供最小可用的 Prometheus 配置，可直接用 docker-compose 中的 `prometheus` 服务加载。
- `monitoring/grafana_downstream.json` 是下游同步通道的 Grafana 仪表盘示例，包含成功率、状态拆分与最近错误面板，导入后选择 Prometheus 数据源即可。
- 设置 `NEEDRADAR_TELEMETRY_ENABLED=true` 及对应的 OTLP Endpoint 后，`app/core/telemetry.py` 会自动为 FastAPI 与 Celery 任务注入 OpenTelemetry Trace，便于与 Jaeger/Tempo 等系统联动。
- 需要立即下发候选需求到 Webhook/MQ/文件同步通道时，可使用 `python -m cli.main candidates sync --channel file_drop --limit 20` 手动派发任务。

## Web 管理前端

- 代码位于 `web/`，采用 Vue 3 + TypeScript + Vite + Element Plus，并接入 Pinia、Vue Router、Vue Query、Vue I18n。
- 页面包含仪表盘、RSS 源管理、原始内容、筛选监控、候选需求工作台与系统告警模块，提供示例数据与组件骨架，便于后续与后端 `/api/v1` 接口联调。
- 运行 `pnpm test` 可执行 Vitest + Vue Test Utils 单测，CI 亦可接入 `pnpm lint`、`pnpm build`。
