# PRD: 持仓成本价↔指数对应图表（position-cost-index-chart）

**Feature slug**: `position-cost-index-chart`

## 1. 概述

持仓分析页（`PositionAnalysis.vue`）新增一张图表：基金持仓成本价折线 + 其关联指数的实际点位 + 成本价对应的指数点位（按规则 A 转换）。让用户直观看到"我的成本基准在指数多少点"，与指数实际走势对比。

## 2. 功能目标

- 新增纯函数 `compute_cost_index_series(snapshots, index_history)`（规则 A：固定比例·最新日）。
  - `ratio = 最新基金净值 / 最新指数点位`（各取序列最后一日）。
  - `cost_in_index(t) = cost_price(t) / ratio`。
- 新增 API `GET /api/positions/snapshot/cost-index?position_id=&start_date=&end_date=`，返回图表数据。
- 持仓分析页加一张**双轴合并图**：成本价（左轴·基金净值步进）+ 实际指数（右轴·点位）+ 成本对应指数点（右轴·转换步进）。
- 仅单持仓时显示该图；选「全部持仓」时隐藏。单持仓无关联指数时只画成本价（不画指数部分）。

## 3. 用户故事

- 作为用户，我想看到持仓成本价的步进走势（加仓后变化）。
- 作为用户，我想知道这个成本价对应关联指数的多少点，并与指数实际走势对比，判断"我的成本基准在指数的什么位置"。

## 4. 功能需求

1. **Analytics 纯函数**（`app/analytics/position_analysis.py`）：`compute_cost_index_series(snapshots, index_history)` -> `{ratio, latest_fund_nav, latest_index_close, points:[{date, cost_price, index_close, cost_in_index}]}`。
   - 最新基金净值 = snapshots 最后一日的 `current_price`；最新指数点位 = index_history 最后一日的 `close_price`。
   - x 轴用快照日期；指数收盘按日期 join（缺失则该点 `index_close=None`）。
   - 无快照 -> `{points:[]}`；无指数/无法算 ratio -> `ratio=None`，各点 `cost_in_index=None`。
2. **API 路由**（`app/web/api_server.py`）：`/api/positions/snapshot/cost-index`。
   - 查 `position.index_code`（PositionStorage.get_position_by_id）。
   - 取快照序列（get_position_snapshot_series）、指数日线（IndexInfoStorage.get_index_history，仅当有 index_code）。
   - 调 analytics，返回 `{index_code, index_name, ratio, latest_fund_nav, latest_index_close, points}`。
3. **前端 API**（`api/index.js`）：`positionAnalysisApi.getCostIndex(params)`。
4. **前端图表**（`PositionAnalysis.vue`）：新卡片「成本价与指数对应走势」，双轴 ECharts。
   - 单持仓时 fetch + 渲染；全部持仓时 `v-if` 隐藏。
   - 无关联指数（index_code 空 / ratio 空）时只画成本价折线（左轴）。
5. **数据来源**：复用现有表（`position_daily_snapshot` / `index_info` / `position`），无表结构变更、无新 storage 方法。

## 5. 验收标准

- [ ] `compute_cost_index_series`：ratio = 最新基金净值/最新指数点位；cost_in_index = cost_price/ratio；按日期 join 指数收盘，缺失为 None；无指数时 ratio=None、cost_in_index=None；无快照返回空。
- [ ] API `/api/positions/snapshot/cost-index` 单持仓返回正确 points；无关联指数时 index_code=None、ratio=None、points 仅含 cost_price。
- [ ] 前端双轴图：成本价（左轴步进）+ 实际指数（右轴）+ 成本对应指数点（右轴步进）三线；全部持仓隐藏；无指数时只画成本价。
- [ ] analytics 纯函数单测覆盖（TDD）。
- [ ] `pytest tests/ -q` 无回归；前端 `npm run build` 通过、`dist/` 提交。

## 6. 非目标

- 不改 `position_daily_snapshot` / `index_info` / `position` 表结构。
- 不改现有 4 张图（盈亏率/市值/占比/累计收益）。
- 不做规则 B（逐日比例）/ C（买入日指数加权）--已选 A。
- 不对"全部持仓"做成本-指数聚合（该图仅单持仓）。
- 不重算成本价（直接用快照已有的 `cost_price`）。

## 7. 依赖

- `position_daily_snapshot.cost_price` / `current_price`（快照已有）。
- `position.index_code`（持仓关联指数，position-index-link 已加）。
- `IndexInfoStorage.get_index_history`（已存在）。
- `PositionStorage.get_position_by_id`（返回 index_code，已存在）。
- 前端 `useEChart` composable（已存在）。

## 8. 风险评估

- **规则 A 的失真**：用最新 ratio 反推历史成本价，因基金管理费使 NAV 涨得比指数慢，会系统性高估历史成本对应指数点位（幅度≈累计基金费率，1-2 年 <1%）。用户认可（管理费本就是成本）。非目标，不修。
- **指数数据缺失**：某快照日无指数收盘 -> 该点 index_close None，指数线断点；ECharts 默认不连接 null。可接受。
- **快照/指数日期不对齐**：两者均为交易日日线，基本对齐；个别缺漏由 join 兜底为 None。
- **最新基金净值取快照最后一日 current_price**：若快照非最新日，ratio 略偏；可接受（快照每日备份）。

## 9. Open Questions（Phase 3 已澄清，实现中修订）

- 对应规则：**B（逐日比例）**--实现中用户修订（原 Phase 3 选 A）。每日 `ratio(t) = 当日指数收盘 / 当日快照基金净值(current_price)`，`cost_in_index(t) = cost_price(t) × ratio(t)`。某日无指数 -> 该点 `cost_in_index=None`。A（固定最新日比例）已弃用（用户澄清：每日对应关系应用当日净值+当日指数算）。
- 图表形式：**双轴合并图**（两轴 `scale:true` 自适应数据区间，不从 0 起，看清小幅波动）。
- 适用范围：**单持仓显示（有指数画全，无指数只画成本价），全部持仓隐藏**。
