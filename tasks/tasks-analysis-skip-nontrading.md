# Task List: analysis-skip-nontrading

**Based on PRD**: `tasks/prd-analysis-skip-nontrading.md`
**Design**: 后端改动，前端零改（不触发 frontend-design）

## Relevant Files

### Files to Create
- `data-crawler/tests/test_analysis_skip_nontrading.py` - `filter_trading_days` 纯函数测试（TDD）

### Files to Modify
- `data-crawler/app/analytics/position_analysis.py` - 加 `filter_trading_days`
- `data-crawler/app/analytics/__init__.py` - 导出 `filter_trading_days`
- `data-crawler/app/storage/fund_nav_history_storage.py` - 加 `get_trading_dates`
- `data-crawler/app/web/api_server.py` - analysis 接口过滤 series/portfolio_series

### 不改动
- 快照备份任务、已有周末快照数据、cost-index 图、前端

## Implementation Tasks

### 1. filter_trading_days 纯函数（TDD）
**Effort Estimate**: Small

#### Sub-tasks:
- [ ] 1.1 **[测试先行]** 新建 `tests/test_analysis_skip_nontrading.py`：① 保留交易日行、剔除非交易日行；② 空 trading_dates 原样返回；③ 顺序不变；④ 空 rows 返回 []
- [ ] 1.2 跑 `pytest tests/test_analysis_skip_nontrading.py -q` 确认失败（红）
- [ ] 1.3 `position_analysis.py` 加 `filter_trading_days(rows, trading_dates)`（保留 snapshot_date ∈ trading_dates，空集兜底原样返回）
- [ ] 1.4 `__init__.py` 导出 `filter_trading_days`
- [ ] 1.5 跑测试通过（绿）

### 2. get_trading_dates storage 方法
**Effort Estimate**: Small

#### Sub-tasks:
- [ ] 2.1 `fund_nav_history_storage.py` 加 `get_trading_dates(start_date=None, end_date=None)` -> distinct nav_date 字符串集合（区间可选）
- [ ] 2.2 端到端验证：返回集合不含 7-18/7-19 周末

### 3. analysis 接口过滤
**Effort Estimate**: Small

#### Sub-tasks:
- [ ] 3.1 `get_position_snapshot_analysis`：取 `trading_dates = _nav_storage.get_trading_dates(start_date, end_date)`
- [ ] 3.2 单持仓 `series` = `filter_trading_days(series, trading_dates)`（在 overview 计算前过滤，保证 overview 基于过滤后序列）
- [ ] 3.3 组合 `portfolio_rows` 过滤后再 `calc_portfolio_profit_series` / `calc_portfolio_overview`
- [ ] 3.4 import filter_trading_days

### 4. 验证收尾
**Effort Estimate**: Small

#### Sub-tasks:
- [ ] 4.1 `pytest tests/ -q` 全量回归，无新增失败
- [ ] 4.2 端到端：某持仓 analysis 的 series/portfolio_series 不含 7-18/7-19
- [ ] 4.3 对照 PRD 验收标准逐条核对
- [ ] 4.4 reviewer 自审
- [ ] 4.5 总结：点文档状态，改动文件清单，后续建议（重启 web 生效）

## Notes

- **依赖顺序**：1（纯函数 TDD）-> 2（storage）-> 3（接口）-> 4（验证）。
- **交易日历口径**：全局 distinct nav_date 并集（A股交易日统一，任一基金净值日即交易日）。
- **前端零改**：三图 data 来自过滤后 series/portfolio_series。
- **纯后端**：无前端改动，无需 npm build。
- **过滤时机**：在 overview/profit_series 计算前过滤 series，保证概览与图一致。
- **空集兜底**：nav_history 为空时 filter 原样返回，不清空图。
