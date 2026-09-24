# PRD: 补录撞唯一键时复活软删记录（buyer-backfill-revive-deleted）

**Feature slug**: `buyer-backfill-revive-deleted`

## 1. 概述

`POST /api/buyers/backfill` 补录买入时遇到数据库 `IntegrityError`，当前实现**直接返回 400 报错**。但根因是**软删除（`del_flag='0'`）的同 `(fund_code, time, type)` 记录仍在唯一键 `uk_fund_code_time_type` 中生效**——UI 默认按 `del_flag='1'` 过滤看不到这条"幽灵记录"，用户感知为"今天没有手动买入、却报 2026-08-19 冲突"。

**真因**：`sql/alter/alter_fund_buyer_uk_code_time_type.sql` 把唯一键从 `(fund_code, time)` 放宽到 `(fund_code, time, type)`，但**没有把 `del_flag` 加进键**，导致软删记录不能被同键复用。**本 PR 不改 DDL**（DDL 改动需协调在线 alter + ORM 同步，影响面大），改在应用层做"复活"：补录时优先查 `(fund_code, time, type, del_flag='0')` 的软删记录，存在则原地 update 字段 + `del_flag='1'`，再走 `process_buyer_transaction`；不存在才走 `INSERT`。`IntegrityError` 兜底仍保留（处理并发场景：另一 session 已先复活），但此时返回的才是真正的"重复补录"。

## 2. 功能目标

- 补录同一 `(fund_code, time, type)` 软删记录时，**不再 400**，而是原地复活并继续走持仓更新。
- 补录真正重复（已有 `del_flag='1'` 活记录）时，仍返回 400，错误文案保留 `{buy_date}`。
- 单测覆盖"软删复活"和"无软删新建"两条核心路径，并保留回归套件无失败新增。

## 3. 用户故事

- 作为用户，我想补录一笔过去的手动买入（基金 011613、2026-08-19、1000元），即使这条历史记录被软删过，我也应该能**一键复活**而不是去数据库手工恢复。
- 作为用户，UI 列表只展示 `del_flag='1'` 的记录，所以"看不到的软删记录"不应该成为补录的拦路石。
- 作为用户，真正重复（活记录 + 新补录）时，错误消息应该清晰指出是哪一天、什么类型（保留现有 `{buy_date}` 文案）。

## 4. 功能需求

1. **后端路由**（`app/web/api_server.py` 的 `backfill_buyer`）：在 step 3「建买入记录」之前，先查 `(fund_code, time, type, del_flag='0')`：
   - **命中软删记录** → 原地 UPDATE：`fund_name/amt/remark/buy_status='PENDING'/update_by/update_time/del_flag='1'`，commit 后拿 id 继续走 step 4。
   - **未命中** → 走原 `INSERT FundBuyer(...)` 路径。
2. **并发兜底**：`INSERT` 撞 `IntegrityError` 时，**不立即 400**，回滚后再次查同 `(fund_code, time, type)` 任意 `del_flag` 记录：
   - 存在 → 视为真正的重复补录，返回原 buy_date 文案 400。
   - 不存在 → 视为其他约束冲突，记录 ERROR 日志后返回 500。
3. **错误文案**：保留 `该基金在 {buy_date} 该买入类型已存在记录，无法重复补录（可删除/编辑已有记录）`，**不**改 `{buy_date}` 语义。
4. **单测**（`data-crawler/tests/test_buyer_backfill_revive.py`）：覆盖
   - 「软删记录存在 → 复活（不 INSERT）」，校验 del_flag='1'、字段覆盖、最终 SUCCESS/NO_POSITION/ERROR 走 process。
   - 「无软删记录 → 新建」，校验走原 INSERT 路径。
   - 复用现有 `data-crawler/tests/test_buyer_backfill.py` 的 `compute_buyer_shares` 测试不破坏。

## 5. 验收标准

- [ ] server 117.72.53.38 上 fund_code=011613 + 2026-08-19 + type='1' 补录，若同键存在软删记录 → 返回 `201` + `{success, shares, position_updated, message}`，DB 中该记录 del_flag='1'、字段被新值覆盖。
- [ ] 同一 (fund_code, time, type) 已有活记录（del_flag='1'）→ 仍返回 `400` 且文案带 `{buy_date}`。
- [ ] 无任何 (fund_code, time, type) 记录 → 走 INSERT，行为与现状完全一致。
- [ ] 补录路由在 `data-crawler/tests/` 跑通：覆盖"软删复活"和"无软删新建"两条核心路径，全量 `pytest tests/ -q` 无新增失败。
- [ ] 不改 DDL、不改 `process_buyer_transaction` / `get_nav_value_by_date`、不改 `compute_buyer_shares`、不改前端 FundBuyer.vue（仅依赖既有的 `position_updated` 文案即可）。
- [ ] 不改 PRD 既有「非目标」中的"不去重"语义：本 PR 复活软删记录是修复可见性 bug，并非引入新的去重。

## 6. 非目标

- 不改 DDL（不改 `uk_fund_code_time_type` 唯一键定义、不加 `del_flag` 进键）。
- 不做真正重复（活记录）时的可视化冲突列表（保留 buy_date 文案足够）。
- 不改"新增买入"和"刷新份额"既有流程。
- 不改 `process_buyer_transaction` / `get_nav_value_by_date` / `compute_buyer_shares` 既有逻辑。
- 不在前端新增"是否覆盖软删记录"二次确认（应用层自动复活 = 显式补录动作的合理推论）。
- 不在 server 117.72.53.38 上做"清理已存在软删记录"的迁移（复活方案在跑通后，软删历史记录用户可自然消化）。

## 7. 依赖

- `app/web/api_server.py` 的 `backfill_buyer`（已存在）。
- `app/storage/fund_buyer_storage.py` 的 `FundBuyer` ORM、`_buyer_storage.Session()`、`_buyer_storage.process_buyer_transaction(...)`（已存在）。
- `sqlalchemy.exc.IntegrityError`（已 import）。
- `app/utils/logger.py` 的 `logger`（已存在）。
- 测试基建：pytest + 当前 `data-crawler/tests/` 下的 fixture 模式。

## 8. 风险评估

- **并发**：两个补录请求同时复活同一条软删记录 → 第二个 `UPDATE` 后 commit 仍可能撞键。`IntegrityError` 兜底已覆盖，回滚后再查 → 命中活记录（被第一个请求复活了）→ 返回 400。可接受。
- **复活覆盖历史字段**：用户用补录"恢复"一笔历史手动买入，会把 `amt/remark` 覆盖。**这是用户显式选择补录动作的合理推论**，且补录本身就是"修正历史记录"语义。
- **不打 del_flag='1' 的副作用**：复活的记录会进入 `process_buyer_transaction` → 持仓累加。**这是用户希望的**：补录就是要把"被删的买入"算回持仓。
- **测试与生产数据隔离**：单测如果连真实 MySQL，需小心不要污染线上数据。建议单测用 `tmp_path` SQLite 或 `try/finally` rollback，详见 tasks 阶段决定。

## 9. Open Questions（Phase 3 已澄清）

- **修复方向**：应用层复活（不修 DDL）。
- **错误消息**：保留 `{buy_date}` 文案，不带实际冲突行 id/状态。
- **回归测试**：需要 TDD 覆盖"软删复活" + "无软删新建"两条路径。
- **feature slug**：`buyer-backfill-revive-deleted`。
