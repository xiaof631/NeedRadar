# Marketplace 运营节奏

这份文档定义 `marketplace` 线索池的最小运营动作，目标是让结果回填、来源复盘和规则调整形成固定节奏，而不是停留在一次性手工操作。

## 目录约定

- 回填样本：`docs/marketplace-retrospectives/YYYY-MM-DD-outcome-backfill.csv`
- 复盘记录：`docs/marketplace-retrospectives/YYYY-MM-DD.md`

建议所有回填和复盘都留痕到这两个文件里，后续来源调优、扩源和规则收紧都以仓库中的记录为准。

## 一次性历史回填

1. 从当前 `high_purity` 队列里优先挑选已有明确结果的线索。
2. 按下面的 CSV 结构整理样本：

```csv
lead_id,outcome,reason_tags,notes
498,won,scope_fit;fast_response,Closed from prior outreach
497,lost,budget_low;timeline_risk,Scope and timeline did not match
```

3. 执行回填：

```bash
python3 -m cli.main marketplace backfill-outcomes docs/marketplace-retrospectives/YYYY-MM-DD-outcome-backfill.csv
```

4. 回填后导出最新复盘草稿：

```bash
python3 -m cli.main marketplace retrospective-report --output docs/marketplace-retrospectives/YYYY-MM-DD.md
```

## 每周来源复盘

固定在每周一次，推荐周五执行。

### 操作步骤

1. 运行 `retrospective-report` 导出最新快照。
2. 查看来源效果看板和转化复盘看板，重点记录：
   - 哪些来源持续产出 `won`
   - 哪些来源主要产出 `no_response / not_fit`
   - 哪些来源高纯度高但仍缺少结果样本
3. 在当周复盘文件里写明：
   - `保留`
   - `扩同类来源`
   - `建议降频`
   - `建议暂停`
4. 把结论同步到 issue 或后续开发计划中。

### 最小记录模板

- 本周新增结果样本数
- 来源机会榜
- 来源噪音榜
- 下周动作

## 每两周规则复盘

固定每两周一次，推荐与来源复盘错开一周执行。

### 复核内容

- `high_purity` 是否混入不该进主队列的线索
- `expanded` 是否遗漏了值得提升到主队列的项目
- `not_fit / lost` 的高频原因标签是否暴露了过滤边界问题
- `full_time_job`、硬件实施、招聘型噪音是否还在持续进入

### 决策输出

- 收紧哪些过滤词或分类边界
- 放宽哪些扩展线索条件供人工筛选
- 哪些来源需要单独增加噪音过滤

## 结果原因标签建议

优先复用短标签，避免同义词失控。当前建议优先使用：

- `scope_fit`
- `fast_response`
- `budget_confirmed`
- `budget_low`
- `timeline_risk`
- `scope_unclear`
- `ghosted`
- `slow_process`
- `full_time_hiring`
- `out_of_scope`

如果要新增标签，先在复盘记录里说明原因，再用于批量回填。

## 回写原则

- 来源结论优先回写到来源调优建议和扩源计划。
- 规则结论优先回写到抓取过滤、`lead_tier` 边界和优先级规则。
- 每次复盘至少要留下一个明确动作，避免只写结论不落改动。
