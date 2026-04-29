# 贡献指南

感谢你对 NeedRadar 的关注！

## 快速开始

1. Fork 本仓库
2. 创建特性分支：`git checkout -b feat/your-feature`
3. 安装开发依赖：`pip install -e ".[dev]" && cd web && pnpm install`
4. 启动本地服务：`./scripts/local_stack.sh start`
5. 修改代码，添加测试
6. 运行检查：`ruff check && python -m tools.coverage_runner && mypy app/services jobs`
7. 提交并推送

## 提交规范

- 提交信息使用英文，格式：`type: description`（如 `feat:`, `fix:`, `docs:`, `refactor:`）
- 一个 commit 只做一件事
- 禁止使用 `git commit --amend` 修改已推送的 commit

## 代码风格

- **Python**：Ruff 格式化，行宽 100，类型注解强制
- **前端**：Vue 3 Composition API + TypeScript，Element Plus 组件库
- 所有新增功能需通过 `python -m tools.coverage_runner`（覆盖率 >= 75%）

## 添加新数据源

1. 在 `app/services/marketplace_fetcher.py` 实现解析器
2. 在 `_parse_marketplace_page` 注册 adapter
3. 在 RSS 源管理中添加源配置（config 中指定 `adapter`）
4. 添加对应的测试

数据源必须是公开可访问的网页或 API，请确认合规性。

## 目录约定

| 目录 | 用途 |
|------|------|
| `app/` | FastAPI 应用、服务层、数据库 |
| `jobs/` | Celery 任务与调度器 |
| `web/` | Vue 3 管理前端 |
| `cli/` | Typer 命令行工具 |
| `alembic/` | 数据库迁移 |
| `docs/` | 设计文档 |
| `tests/` | 测试用例 |
| `scripts/` | 辅助脚本 |

## 行为准则

请保持友善、专业。对新手保持耐心，公开讨论技术问题。
