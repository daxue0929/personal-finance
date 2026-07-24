# Task List: position-cost-index-chart

**Based on PRD**: `tasks/prd-position-cost-index-chart.md`
**Design**: `tasks/design-position-cost-index-chart.md`
**状态**: ✅ 全部完成（6 测试绿、端到端验证 ratio=1277.94、web 新路由已注册）

## Relevant Files

### Files to Create
- `data-crawler/tests/test_position_cost_index_chart.py` - `compute_cost_index_series` 纯函数测试（6 例）✅

### Files to Modify
- `data-crawler/app/analytics/position_analysis.py` - 加 `compute_cost_index_series`（规则 A）✅
- `data-crawler/app/analytics/__init__.py` - 导出 `compute_cost_index_series` ✅
- `data-crawler/app/web/api_server.py` - 加 `GET /api/positions/snapshot/cost-index` 路由 ✅
- `frontend/src/api/index.js` - 加 `positionAnalysisApi.getCostIndex` ✅
- `frontend/src/views/PositionAnalysis.vue` - 加双轴图表卡 + fetch + render ✅

### 不改动
- 表结构、storage 方法（复用 `get_position_by_id`/`get_position_snapshot_series`/`get_index_history`）、现有 4 图

## Implementation Tasks

### 1. Analytics 纯函数（TDD）✅
- [x] 1.1 **[测试先行]** 新建 `tests/test_position_cost_index_chart.py`，6 用例：正常 ratio/cost_in_index、指数缺失 join、无 index_history、无 snapshots、单点、Decimal 兼容
- [x] 1.2 跑测试确认失败（红）-- ImportError
- [x] 1.3 `app/analytics/position_analysis.py` 加 `compute_cost_index_series`（ratio=最新指数/最新净值，cost_in_index=cost_price×ratio）
- [x] 1.4 跑测试通过（绿）-- 6 passed

### 2. API 路由 ✅
- [x] 2.1 `app/web/api_server.py` 加 `GET /api/positions/snapshot/cost-index`：查 index_code + 取快照/指数日线 + 调 analytics；`__init__.py` 导出函数 + api_server import
- [x] 2.2 无关联指数时 `index_code=None`、`ratio=None`、points 仅含 cost_price
- [x] 2.3 try/except 异常返回 500 + logger.error
- [x] 端到端验证：持仓 2（011613/科创50）ratio=1277.94，末点成本 1.4856 对应 1898.51 点（实际 1787.2）

### 3. 前端图表 ✅
- [x] 3.1 `api/index.js` 加 `positionAnalysisApi.getCostIndex`
- [x] 3.2 `PositionAnalysis.vue` 加 `costIndex` ref + `useEChart`(costChartRef/setCost) + `fetchCostIndex`（单持仓时调）
- [x] 3.3 加图表卡 `v-if="positionId !== 'all'"`：双轴 -- 成本价(左轴步进·#5470C6) + 实际指数(右轴·#FAC858) + 成本对应指数点(右轴虚线步进·#EE6666)；legend + tooltip
- [x] 3.4 无关联指数（ratio 空）时只画成本价、隐藏右轴与 series 2/3
- [x] 3.5 `fetchAnalysis` 末尾 `if (positionId!=='all') fetchCostIndex()`，随各查询入口触发

### 4. 构建门禁 + 质量收尾 ✅
- [x] 4.1 `frontend/` `npm run build` 通过 -- ✓ built in 3.55s
- [x] 4.2 `dist/` 纳入提交（构建门禁）-- 待 git 提交
- [x] 4.3 `pytest tests/ -q` 全量回归 -- 211 passed；12 failed+2 error 均预存在（eastmoney/fund_homepage_fetch），无回归
- [x] 4.4 对照 PRD 验收标准 + design 一致性清单 -- 全部达标
- [x] 4.5 reviewer 自审 -- 通过（纯函数可测、路由薄、前端复用 useEChart）
- [x] 4.6 web 进程已重启加载新路由（401 路由存在，非 404）

## Notes

- **规则 A 已实现**：`ratio = 最新指数点位 / 最新基金净值`，`cost_in_index = cost_price × ratio`。最新基金净值取快照末尾 `current_price`，最新指数点位取指数日线末尾 `close_price`。
- **规则 A 失真**：用最新 ratio 反推历史成本价，因基金管理费系统性高估历史成本对应指数点位（1-2 年 <1%），用户认可（管理费即成本）。
- **web 进程已重启**（本会话）：加载新路由。scheduler 未动（新功能不涉及 scheduler）。
- **前端 dev server 仍在 3000 运行**，代理 /api -> 5001，登录后可验证新图。
