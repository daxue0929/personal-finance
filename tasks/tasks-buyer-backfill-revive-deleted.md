# Task List: buyer-backfill-revive-deleted

**Based on PRD**: `tasks/prd-buyer-backfill-revive-deleted.md`
**Design**: N/A（无前端改动）

## Relevant Files

### Files to Create
- `data-crawler/tests/test_buyer_backfill_revoke.py` - TDD 测试：软删复活路径 + 无软删新建路径

### Files to Modify
- `data-crawler/app/web/api_server.py` - `backfill_buyer` 路由：INSERT 前加软删复活分支；IntegrityError 兜底处理并发

### 不改动
- DDL（不动 `uk_fund_code_time_type` 唯一键定义、不动 `sql/alter/`）
- `process_buyer_transaction` / `get_nav_value_by_date` / `compute_buyer_shares` 既有逻辑
- `frontend/src/views/FundBuyer.vue` / `frontend/src/api/index.js`（前端依赖既有 `position_updated` 文案即可）
- `tasks-buyer-backfill.md` 既有任务清单（不追溯修改已完成任务）

## Implementation Tasks

### 1. TDD 写测试用例（红）
**Effort Estimate**: Small

#### Sub-tasks:
- [ ] 1.1 新建 `data-crawler/tests/test_buyer_backfill_revoke.py`，用 `conftest` 的 `client` + `business_storages_mock` + `login` 模式（不连真实库，opt-in mock）
- [ ] 1.2 写测试 `test_soft_deleted_record_revives`：mock `_buyer_storage.Session()` 返回的 session 模拟「query(filter by del_flag='0') 命中一条」→ 验证后续走 UPDATE（`session.add` 没被调用）且 `process_buyer_transaction` 用同一 id 被调，返回 201
- [ ] 1.3 写测试 `test_no_deleted_record_inserts`：mock session 模拟「query 返 None」→ 验证走 INSERT（`session.add` 被调一次）且 `process_buyer_transaction` 用新 id 被调，返回 201
- [ ] 1.4 写测试 `test_true_duplicate_returns_400`：mock session 模拟「query(任意 del_flag) 命中一条 del_flag='1' 活记录」→ 验证返回 400 且文案带 buy_date='2026-08-19'
- [ ] 1.5 跑 `pytest tests/test_buyer_backfill_revoke.py -q` 确认失败（红）：当前 backfill 路由没复活分支，新测试应 3 failed

### 2. 实现复活分支（绿）
**Effort Estimate**: Small

#### Sub-tasks:
- [ ] 2.1 `app/web/api_server.py` 的 `backfill_buyer` 函数在 step 3 之前，加一段：「用 `_buyer_storage.Session()` 新建 session，query `FundBuyer` 过滤 `(fund_code, time, type, del_flag='0')`」
- [ ] 2.2 命中软删记录 → 原地 UPDATE：`fund_name/amt/remark/buy_status='PENDING'/update_by='api'/update_time=get_beijing_now()/del_flag='1'`，commit + refresh 拿 id，标记 `revived=True`
- [ ] 2.3 未命中 → 走原 `FundBuyer(...)` + `session.add` + `session.commit` + `session.refresh` 拿 id 路径（保持原逻辑）
- [ ] 2.4 `IntegrityError` 兜底改写：回滚后**先 query** `(fund_code, time, type, del_flag IN ('0','1'))`，命中任意一条 → 视为真重复，返回 `400 {error: '该基金在 {buy_date} 该买入类型已存在记录...'}`；未命中 → 视为真约束冲突，ERROR 日志 + `500 {error: str(e)}`
- [ ] 2.5 step 4 调 `process_buyer_transaction` 用复活/新建的 id，**逻辑不变**（同 1453-1461 行）
- [ ] 2.6 跑 `pytest tests/test_buyer_backfill_revoke.py -q` 通过（绿）：3 passed
- [ ] 2.7 跑 `pytest tests/ -q` 全量回归：无新增失败

### 3. 部署 + server 复现
**Effort Estimate**: Small

#### Sub-tasks:
- [ ] 3.1 本地 `git status` 确认改动文件：`data-crawler/app/web/api_server.py` + `data-crawler/tests/test_buyer_backfill_revoke.py`
- [ ] 3.2 server 117.72.53.38 上 `cd /path/to/personal-finance && git pull` 拿代码
- [ ] 3.3 server 重启 web 容器（`docker-compose restart web` 或 `systemctl restart` 按 deploy.sh 走）
- [ ] 3.4 等 5s 启动，跑 server 上 curl 重现：
  ```bash
  curl --url 'http://117.72.53.38:83/prod-api/buyers/backfill' \
    -H 'Content-Type: application/json' \
    --data-raw '{"fund_code":"011613","fund_name":"华夏科创50ETF联接C","time":"2026-08-19","amt":"1000","type":"1","remark":""}' \
    --insecure
  ```
- [ ] 3.5 确认返回 201 + `{success, shares, position_updated, message}`；DB 中 011613/2026-08-19/type=1 那条记录 del_flag='1'，字段被新值覆盖

## Notes

- **依赖顺序**：1（红）→ 2（绿+全量回归）→ 3（部署+复现）。严格 TDD，不允许先写实现后补测试。
- **mock 策略**：单测全 mock（opt-in `business_storages_mock` + 自建 session MagicMock），不连真实 MySQL。理由：conftest 顶部明确「测试通过 mock UserStorage 避免连接真实数据库（项目 .env 指向生产库，绝不在测试中触碰）」。
- **复活 vs 真重复的判定**：在 `IntegrityError` 兜底里靠二次 `query(任意 del_flag)` 区分——这是为了处理"两个并发请求同时复活同一条软删记录"的竞态：第一个请求先 commit 把软删改成 del_flag='1'，第二个请求 INSERT 撞键后回滚，再查就能查到那条活记录，返回 400 是正确的（用户最终只看到一条记录被补录）。
- **错误文案不动**：保留 buy_date 占位，不暴露实际冲突行 id/状态（用户已确认）。
- **风险**：复活软删记录会改写历史 amt/remark 字段——这是用户显式补录动作的合理推论（PRD §8 风险已记录）。
- **DDL 风险**：当前实现不修 DDL；如果后续真的有多笔不同 fund_code 的同 (time, type) 软删复活性能问题，再考虑把 `del_flag` 加进键。本 PR 范围不动。
