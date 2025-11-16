# NeedRadar

NeedRadar 是一个用于从公开 RSS 数据源挖掘潜在“小工具”需求的系统。此仓库当前包含后端 API 的基础工程骨架。更多背景可参考 `docs/` 目录。

## 快速开始

1. 安装依赖：

   ```bash
   pip install -e .[dev]
   ```

2. 启动 API：

   ```bash
   uvicorn app.main:app --reload
   ```

3. 运行命令行工具查看配置：

   ```bash
   python -m cli.main show-config
   ```

4. 启动基于 APScheduler 的调度器，自动执行 RSS 抓取与候选需求晋升任务：

   ```bash
   python -m jobs.scheduler
   ```

5. 执行测试与代码质量检查：

   ```bash
   ruff check
   pytest
   ```

## 目录结构

- `app/`：FastAPI 应用、配置与数据库基础设施。
- `cli/`：Typer 命令行程序。
- `alembic/`：数据库迁移配置。
- `docs/`：需求、设计与开发文档。

## 环境变量

复制 `.env.example` 为 `.env` 并根据需求调整：

```bash
cp .env.example .env
```

关键变量：

- `NEEDRADAR_DATABASE_URL`：异步 SQLAlchemy 连接串，默认使用 SQLite。
- `NEEDRADAR_ALEMBIC_DATABASE_URL`：可选，同步连接串用于 Alembic 迁移。
