# PRD: Dashboard 首页 + 持仓分析提示（dashboard-home）

**Feature slug**: `dashboard-home`

## 1. 概述

新增系统 Dashboard 首页（面板页），作为登录后默认落地页。首版放一个「持仓占比饼图」，基于**实时 position 数据**（当前持仓，非历史快照）--满足"晚上快照未备份前，也能看到今日最新持仓占比"。另在持仓分析页标题后加问号 tips，说明该页分析基于前一交易日快照，与 Dashboard 的实时口径区分。

## 2. 功能目标

- 新增 `Dashboard.vue`（顶级菜单第一项 + 根路径 redirect 目标）。
- Dashboard 首版含持仓占比饼图，数据源 = 实时 position（`current_value`）。
- 新增后端方法 `get_all_active_positions`（全量有效持仓）+ 接口 `GET /api/positions/allocation`（复用 `calc_position_allocation`）。
- 持仓分析页（`PositionAnalysis.vue`）顶部标题后加问号 tips：「本页分析基于每日持仓快照（前一交易日数据）」。

## 3. 用户故事

- 作为用户，登录后想先看到一个系统面板（Dashboard），一眼掌握当前持仓分布。
- 作为用户，晚上快照还没备份时，想在 Dashboard 看到**今日最新**的持仓占比（实时），而非昨天的。
- 作为用户，在持仓分析页想知道"这里的数字是基于前一交易日快照的"，避免与实时数据混淆。

## 4. 功能需求

1. **后端 storage**（`position_storage.py`）：`get_all_active_positions()` -> 返回全部 `del_flag='1'` 持仓 dict（含 `fund_code/fund_name/current_value`），供实时饼图。
2. **后端接口**（`api_server.py`）：`GET /api/positions/allocation` -> 取全量实时持仓 -> `calc_position_allocation` -> 返回 `{data: [{fund_code, fund_name, value, percent}]}`。
3. **前端 API**（`api/index.js`）：`positionApi`（或复用 portfolioApi）加 `getAllocation()`。
4. **前端 Dashboard**（新建 `views/Dashboard.vue`）：持仓占比饼图（复用 `useEChart` + PositionAnalysis 饼图渲染逻辑），标题「持仓占比（实时）」，空数据 el-empty。
5. **路由**（`router/index.js`）：新增 `/dashboard`（Dashboard，sort 最前），根 `/` redirect 改为 `/dashboard`；iconMap 加图标；TagsView 首页 affix 改为 `/dashboard`。
6. **持仓分析 tips**（`PositionAnalysis.vue`）：顶部加标题栏（若无）+ 问号图标（`QuestionFilled`）+ `el-tooltip`，内容「本页分析基于每日持仓快照（前一交易日数据）」。

## 5. 验收标准

- [ ] `get_all_active_positions` 返回全量有效持仓（含 current_value），软删除排除。
- [ ] `GET /api/positions/allocation` 返回实时占比 `[{fund_code,fund_name,value,percent}]`，percent 求和≈100（无持仓返回空）。
- [ ] Dashboard 首页显示持仓占比饼图（实时），登录后默认落到 Dashboard。
- [ ] 无持仓时 Dashboard 饼图区显示 el-empty，不报错。
- [ ] 持仓分析页标题后有问号 tips，hover 显示「基于前一交易日快照」文案。
- [ ] Dashboard 进菜单第一项；TagsView 首页 affix 为 Dashboard。
- [ ] `calc_position_allocation` 已有测试覆盖；新增 `get_all_active_positions` 相关测试（TDD，mock session）。
- [ ] `pytest tests/ -q` 无回归；`npm run build` 通过，`dist/` 提交。

## 6. 非目标

- Dashboard 首版**只做持仓占比饼图**，其他面板卡片（总资产/收益等）后续迭代。
- 饼图**只做实时**，不加实时/快照切换（快照维度持仓分析页已有）。
- 不改持仓分析页既有 4 图逻辑（只加 tips）。
- 不改快照备份任务、不改 position 表结构。
- 不做实时市值重算（直接用 position.current_value 冗余字段）。

## 7. 依赖

- `calc_position_allocation`（analytics，已存在，复用）。
- `position` 表 current_value 字段（买入/刷新份额时维护）。
- `useEChart` composable + ECharts 饼图（已存在）。
- `router` + `useTagsView`（本会话新增，首页 affix 需同步改）。

## 8. 风险评估

- **current_value 冗余字段过期**：position.current_value 由买入/刷新份额时维护，若未及时刷新可能非最新净值市值。占比是相对值，影响小；且用户已认可用 current_value（非目标重算）。
- **首页 redirect 改动**：`/` 从 `/portfolio` 改到 `/dashboard`，需确认登录跳转、TagsView affix 同步。
- **空持仓**：allocation 返回空 -> 前端 el-empty。

## 9. Open Questions（Phase 3 已澄清）

- **实时/快照**：Dashboard 饼图仅实时（position 表），默认即实时，不切换。
- **市值口径**：用 `position.current_value`（冗余字段，不重算）。
- **菜单位置**：Dashboard 顶级菜单第一项 + 根路径 redirect 到 `/dashboard`。
- **tips 文案**：「本页分析基于每日持仓快照（前一交易日数据）」。
- **饼图维度**：仅实时。
- **feature slug**：`dashboard-home`。
