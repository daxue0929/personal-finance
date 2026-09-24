# Task List: dashboard-home

**Based on PRD**: `tasks/prd-dashboard-home.md`
**Design**: `tasks/design-dashboard-home.md`

## Relevant Files

### Files to Create
- `data-crawler/tests/test_dashboard_home.py` - `get_all_active_positions` 测试（TDD，mock session）
- `frontend/src/views/Dashboard.vue` - Dashboard 首页（持仓占比饼图）

### Files to Modify
- `data-crawler/app/storage/position_storage.py` - 加 `get_all_active_positions`
- `data-crawler/app/web/api_server.py` - 加 `GET /api/positions/allocation`
- `frontend/src/api/index.js` - 加 `getAllocation`
- `frontend/src/router/index.js` - 新增 /dashboard + 根 redirect + import
- `frontend/src/components/Layout.vue` - iconMap 加 /dashboard
- `frontend/src/composables/useTagsView.js` - HOME affix 改 /dashboard
- `frontend/src/composables/useTagsView.spec.js` - 同步改首页 path 断言
- `frontend/src/views/PositionAnalysis.vue` - 标题后加问号 tips

### 不改动
- 快照备份任务、position 表结构、既有 4 图逻辑、`calc_position_allocation`

## Implementation Tasks

### 1. 后端数据源（TDD）
**Effort Estimate**: Small

#### Sub-tasks:
- [x] 1.1 **[测试先行]** 新建 `tests/test_dashboard_home.py`（3 例：全量 dict 含字段/仅 del_flag=1/空返回/current_value None→0）
- [x] 1.2 跑测试确认失败（红）
- [x] 1.3 `position_storage.py` 加 `get_all_active_positions()`
- [x] 1.4 跑测试通过（绿）-- 3 passed
- [x] 1.5 `api_server.py` 加 `GET /api/positions/allocation`（端到端验证：18 持仓、percent 求和 100）

### 2. 前端 Dashboard 页 ✅
- [x] 2.1 `api/index.js` portfolioApi 加 `getAllocation`
- [x] 2.2 新建 `views/Dashboard.vue`：useEChart 饼图 + onMounted getAllocation + renderPie
- [x] 2.3 持仓占比卡 header「持仓占比（实时）」高度 360，空数据 el-empty，el-row/el-col 栅格
- [x] 2.4 接口失败 ElMessage.error + el-empty

### 3. 路由 + TagsView 首页切换 ✅
- [x] 3.1 router import Dashboard；新增 /dashboard（title「首页」sort 5）；根 redirect 改 /dashboard
- [x] 3.2 Layout iconMap 加 /dashboard（Odometer）
- [x] 3.3 useTagsView HOME 改 {path:'/dashboard', title:'首页', affix:true}
- [x] 3.4 useTagsView.spec.js 同步改 /portfolio->/dashboard + vitest 32 通过

### 4. 持仓分析 tips ✅
- [x] 4.1 PositionAnalysis 控制栏加标题「持仓分析」+ QuestionFilled + el-tooltip「本页分析基于每日持仓快照（前一交易日数据）」
- [x] 4.2 import QuestionFilled；图标 #909399 16px cursor:help

### 5. 构建门禁 + 质量收尾 ✅
- [x] 5.1 `pytest tests/ -q` -- 222 passed；12 failed+2 error 预存在，无回归
- [x] 5.2 `npm run test` vitest -- 32 passed
- [x] 5.3 `npm run build` 通过（修复 api/index.js getAllocation 误置悬空的语法错）
- [x] 5.4 dist 待提交
- [x] 5.5 对照 PRD + design -- 全部达标
- [x] 5.6 reviewer 自审 -- 通过
- [x] 5.7 总结见下

## Notes

- **依赖顺序**：1（后端 TDD）-> 2（Dashboard 页）-> 3（路由+TagsView）-> 4（tips）-> 5（构建+审查）。
- **复用**：`calc_position_allocation`（analytics）算占比；PositionAnalysis `renderPie` 结构直接搬到 Dashboard。
- **首页切换**：`/` redirect 从 /portfolio 改 /dashboard；TagsView 首页 affix 同步改 /dashboard（持仓组合变普通可关 tab）。
- **市值口径**：用 position.current_value 冗余字段（已确认，不重算）。
- **纯前端 tips**：仅 PositionAnalysis 加图标+tooltip，不改分析逻辑。
