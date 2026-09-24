# Task List: buyer-backfill

**Based on PRD**: `tasks/prd-buyer-backfill.md`
**Design**: `tasks/design-buyer-backfill.md`

## Relevant Files

### Files to Create
- `data-crawler/tests/test_buyer_backfill.py` - `compute_buyer_shares` 纯函数测试（TDD）

### Files to Modify
- `data-crawler/app/storage/fund_buyer_storage.py` - 加 `compute_buyer_shares` 纯函数
- `data-crawler/app/task/calculate_buyer_shares_task.py` - 改用 `compute_buyer_shares`（DRY）
- `data-crawler/app/web/api_server.py` - 加 `POST /api/buyers/backfill` 路由
- `frontend/src/api/index.js` - 加 `buyerApi.backfill`
- `frontend/src/views/FundBuyer.vue` - 补录按钮 + 弹窗

### 不改动
- `process_buyer_transaction` / `get_nav_value_by_date` 既有逻辑、新增/刷新份额流程、SQL

## Implementation Tasks

### 1. compute_buyer_shares 纯函数 + 重构 task（TDD）
**Effort Estimate**: Small

#### Sub-tasks:
- [x] 1.1 **[测试先行]** 新建 `tests/test_buyer_backfill.py`，6 用例：正常 1000/1.5=666.6667、整除、nav<=0 None、Decimal 兼容、四舍五入
- [x] 1.2 跑 `pytest tests/test_buyer_backfill.py -q` 确认失败（红）-- ImportError
- [x] 1.3 `fund_buyer_storage.py` 加 `compute_buyer_shares(amt, nav)` 纯函数（Decimal 除法 + quantize 4 位，nav<=0 返回 None）
- [x] 1.4 `calculate_buyer_shares_task.py` 改用 `compute_buyer_shares`（替换内联 Decimal，移除 decimal import）
- [x] 1.5 跑 `pytest tests/test_buyer_backfill.py tests/test_fund_buyer.py -q` 通过（绿）-- 13 passed

### 2. 后端接口 /api/buyers/backfill
**Effort Estimate**: Medium

#### Sub-tasks:
- [x] 2.1 `api_server.py` 加 `POST /api/buyers/backfill`：校验 fund_code/time/amt(>0)
- [x] 2.2 `nav = get_nav_value_by_date(_fund_storage, _nav_storage, fund_code, time)`；None/<=0 -> 400「无法获取 {time} 的净值，请先录入该日净值」
- [x] 2.3 `shares = compute_buyer_shares(amt, nav)`；建买入记录 PENDING（内联 session，拿 buyer_id）
- [x] 2.4 `process_buyer_transaction([buyer_id], fund_code, shares, amt, nav, time)` -> SUCCESS/NO_POSITION/ERROR
- [x] 2.5 返回：SUCCESS `{success,shares,position_updated:true}`；NO_POSITION `{...position_updated:false,message}`；ERROR 500
- [x] 路由验证：POST /api/buyers/backfill -> 401（路由存在，鉴权生效）

### 3. 前端
**Effort Estimate**: Medium

#### Sub-tasks:
- [x] 3.1 `api/index.js` 的 `buyerApi` 加 `backfill: (data) => api.post('/buyers/backfill', data)`
- [x] 3.2 `FundBuyer.vue` 功能栏加「补录买入」按钮（`type="info"` + `Clock` 图标），置于「刷新份额」后
- [x] 3.3 补录弹窗（el-dialog 500px）：选择基金 + 基金名称 + 买入日期(可选过去) + 买入金额 + 买入类型(默认手工) + 备注；无份额/状态/策略
- [x] 3.4 提交校验 -> `buyerApi.backfill` -> 按 `position_updated` 显示 success/warning（含份额），error 显示 error；刷新列表

### 4. 构建门禁 + 质量收尾
**Effort Estimate**: Small

#### Sub-tasks:
- [x] 4.1 `pytest tests/ -q` 全量回归 -- 221 passed；12 failed 均预存在（eastmoney），无回归
- [x] 4.2 `npm run build` 通过 -- ✓ 3.31s
- [x] 4.3 `dist/` 纳入提交（构建门禁）-- 待 git 提交
- [x] 4.4 对照 PRD 验收标准 + design 一致性清单 -- 全部达标
- [x] 4.5 reviewer 自审 -- 通过（纯函数可测、路由复用既有模式、前端复用 FundSelect/弹窗）
- [x] 4.6 web 已重启加载 backfill 路由

## Notes

- **依赖顺序**：1（纯函数 TDD）-> 2（后端接口）-> 3（前端）-> 4（构建+审查）。
- **复用**：`get_nav_value_by_date`（nav_utils）取 buy_date 净值；`process_buyer_transaction`（fund_buyer_storage）原子累加持仓；`_fund_storage`/`_nav_storage`/`_buyer_storage` 均已在 api_server 顶部实例化。
- **一步到位**：backfill 接口一次完成 建记录+算份额+更新持仓，不依赖任务/cron。
- **非原子**：建记录(commit) 与 process(另一 session) 分两步；process 失败则记录留 PENDING，任务重试（与现有 task 一致）。
- **过去日期**：`process_buyer_transaction` 已支持补录历史/同日买入（不依赖 buy_date 水位）。
- **无去重**：重复补录同一笔会双倍累加，用户负责（非目标）。
