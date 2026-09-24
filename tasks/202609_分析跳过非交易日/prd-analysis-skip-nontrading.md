# PRD: 持仓分析图跳过非交易日（analysis-skip-nontrading）

**Feature slug**: `analysis-skip-nontrading`

## 1. 概述

持仓分析页三个折线图（盈亏比例走势、持仓金额/市值走势、累计收益走势）当前渲染每日快照点，包含周末/节假日（快照备份任务在非交易日也生成数据，净值照搬前一交易日）。这些非交易日点在图上是无意义的平段。本功能让三图**只渲染真实交易日的点**，非交易日不显示。

判定口径：**基于真实净值日**--`fund_nav_history` 只在交易日有净值记录，用它作交易日历，过滤掉快照序列中非交易日的点。

## 2. 功能目标

- 后端 analysis 接口（`/api/positions/snapshot/analysis`）返回的 `series`（单持仓）与 `portfolio_series`（组合）**只含真实交易日的点**。
- 新增纯函数 `filter_trading_days(rows, trading_dates)`（analytics，可单测）。
- 新增 `FundNavHistoryStorage.get_trading_dates(start, end)`（distinct nav_date 集合，作交易日历）。
- 前端零改（照渲染后端过滤后的数据）。

## 3. 用户故事

- 作为用户，我在持仓分析看盈亏/市值/累计收益走势时，不想看到周末那些无意义的平段点，只想看真实交易日的走势。

## 4. 功能需求

1. **纯函数**（`position_analysis.py`）：`filter_trading_days(rows, trading_dates)` -> 保留 `snapshot_date` ∈ `trading_dates` 的行；`trading_dates` 为空集时原样返回（不误删，兜底）。
2. **storage**（`fund_nav_history_storage.py`）：`get_trading_dates(start_date=None, end_date=None)` -> 返回 `fund_nav_history` 中 distinct `nav_date` 的字符串集合（全局交易日历，所有基金净值日期并集；A股交易日一致）。
3. **接口过滤**（`api_server.py` 的 `get_position_snapshot_analysis`）：
   - 取交易日集合 `trading_dates = _nav_storage.get_trading_dates(start_date, end_date)`。
   - 单持仓 `series` 与组合 `portfolio_series` 均经 `filter_trading_days` 过滤后再返回。
   - overview/pie 等基于过滤后的 series 计算（保持一致）。
4. **前端**：无改动（三图 data 来自过滤后的 series/portfolio_series）。

## 5. 验收标准

- [ ] `filter_trading_days`：保留交易日行、剔除非交易日行；空 trading_dates 原样返回；顺序不变。
- [ ] `get_trading_dates` 返回 distinct nav_date 集合（周末不在内）。
- [ ] analysis 接口 series/portfolio_series 不含 7-18/7-19 等周末点（实测某持仓）。
- [ ] 三图前端渲染后周末平段消失，交易日走势连续。
- [ ] overview（最新/最高/最低/回撤）基于过滤后序列，无因删点异常。
- [ ] `filter_trading_days` 单测（TDD）；`pytest tests/ -q` 无回归。

## 6. 非目标

- 不改快照备份任务（周末仍备份，只是分析时不渲染）。
- 不删除已有周末快照数据（仅展示层过滤）。
- 不改成本-指数对应图（cost-index）--它已按快照日 join 指数，另论。
- 不做前端交易日历（后端过滤，前端零改）。
- 不引入节假日日历表（用 nav_history 真实净值日即可覆盖节假日）。

## 7. 依赖

- `fund_nav_history` 表（只在交易日有净值记录，作交易日历）。
- `_nav_storage`（FundNavHistoryStorage，api_server 已实例化）。
- `calc_position_overview`/`calc_portfolio_profit_series` 等（基于过滤后序列）。

## 8. 风险评估

- **组合视角交易日历取哪个基金**：用全局 distinct nav_date 并集（A股交易日一致，任一基金的净值日即交易日）。低风险。
- **某基金 nav_history 缺失**：若持仓关联基金在某交易日无净值记录，该点可能被误删。缓解：用全局并集（只要有一只基金有该日净值即保留）。
- **空 trading_dates 兜底**：nav_history 为空时 filter 原样返回，不致清空图。

## 9. Open Questions（Phase 3 已澄清）

- **非交易日判定**：基于真实净值日（`fund_nav_history` distinct nav_date 作交易日历）。
- **涉及前端**：否（后端过滤 series，前端零改，不触发 frontend-design）。
- **feature slug**：`analysis-skip-nontrading`。
