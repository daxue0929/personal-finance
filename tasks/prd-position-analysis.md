# PRD：持仓分析功能

> 创建日期：2026-07-13
> 状态：需求已确认，待架构设计
> 来源：`/feature-dev` 流程 Phase 3.5

---

## 1. 概述（Introduction/Overview）

个人基金定投管理系统当前只能查看持仓的**当前**状态（持仓看板 `PortfolioBoard`），无法回顾持仓盈亏随时间的变化趋势，也缺少独立的持仓信息管理入口。

本功能新增「持仓分析」一级菜单，包含两个二级页面：

- **持仓信息管理**：独立表格管理页，集中管理持仓 CRUD（基金代码、份额、成本价、现价、盈亏等），不依赖组合上下文。
- **持仓分析**：参考「指数分析」的多区域分析布局，通过每日持仓快照数据，展示盈亏比例折线图、持仓金额折线图、最大回撤/峰值、持仓占比饼图等指标，帮助用户回顾持仓变化、评估定投效果。

核心问题：`position` 表只存当前状态，且其 `current_price/profit_loss` 等**冗余字段不会随基金净值自动刷新**（`update_fund_net_values_task` 只更新 `fund_info`，不回写 `position`），因此必须新建每日快照表，并在快照时根据最新净值重算盈亏，才能得到真实的历史盈亏曲线。

## 2. 目标（Goals）

1. **新增数据基础**：建立 `position_daily_snapshot` 每日持仓快照表，记录每个有效持仓每天的份额、成本、现价、市值、盈亏，唯一键 `(position_id, snapshot_date)`。
2. **盈亏真实性**：快照记录的盈亏按当天最新净值（`fund_info.net_asset_value`）实时重算，而非照搬 `position` 表的冻结值。
3. **自动积累**：每日凌晨 3 点定时备份昨日所有有效持仓的快照，与 `fund_nav_history` 备份任务同时段，零人工干预。
4. **持仓分析可视化**：持仓分析页按单个持仓选择，展示盈亏比例折线图、持仓金额折线图、最大回撤/峰值；另以饼图展示全部持仓当前市值占比。
5. **独立持仓管理**：持仓信息管理页提供表格化的持仓增删改查，与持仓看板职责分离。
6. **可测试性**：盈亏重算、最大回撤等计算逻辑独立为纯函数（`app/analytics/`），无数据库依赖，便于 TDD。

## 3. 用户故事（User Stories）

作为系统的**单一管理员用户**：

1. 作为用户，我想在侧边栏看到「持仓分析」一级菜单，下含「持仓信息管理」和「持仓分析」两项，以便集中管理持仓并分析其变化趋势。
2. 作为用户，我想在「持仓信息管理」页用表格查看所有持仓（基金代码、名称、份额、成本价、现价、市值、盈亏、盈亏率、买入日期），支持按代码/名称搜索和分页，以便快速定位某个持仓。
3. 作为用户，我想在持仓信息管理页新增/编辑/删除持仓，以便在脱离组合上下文时也能维护持仓基础信息。
4. 作为用户，我想在「持仓分析」页选择某个持仓，查看其盈亏比例随时间变化的折线图，以便判断该基金定投的盈亏走势。
5. 作为用户，我想查看该持仓市值金额随时间变化的折线图，以便直观感受持仓资产规模的变化（受净值波动与加减仓共同影响）。
6. 作为用户，我想看到该持仓在选定区间的最大回撤率、峰值市值等风险指标，以便评估持仓的波动风险。
7. 作为用户，我想看到全部持仓当前市值占比的饼图，以便了解资产配置结构（该饼图不受单持仓选择影响，始终反映全貌）。
8. 作为用户，我希望快照数据每日自动生成、无需手动操作，且盈亏是按当天真实净值计算的，以便分析图反映真实情况。

## 4. 功能需求（Functional Requirements）

### 4.1 数据层

- **FR-1** 新建 `position_daily_snapshot` 表，字段：`id`(主键)、`position_id`(bigint)、`snapshot_date`(date)、`fund_code`、`fund_name`、`shares`、`cost_price`、`current_price`、`cost_amount`、`current_value`、`profit_loss`、`profit_loss_rate`、`source`(manual/system)、`create_time`。金额用 `DECIMAL`。
- **FR-2** 表的唯一键为 `(position_id, snapshot_date)`，保证同一持仓同一天只有一条快照。
- **FR-3** 索引：`position_id`、`snapshot_date`、`(position_id, snapshot_date)` 复合索引、`fund_code`、`create_time`。
- **FR-4** 新增 `PositionDailySnapshot` ORM 模型与 `PositionDailySnapshotStorage`（继承 `StorageBase`），并在 `app/storage/__init__.py` 导出。
- **FR-5** Storage 提供查询方法：按 `position_id` + 日期范围查询快照序列、按 `snapshot_date` 查询当日全部持仓快照（供饼图）、分页查询（供管理页/调试）。
- **FR-6** Storage 提供写入方法：单条 upsert（应用层「查+改/插」，参考 `fund_nav_history_storage.add_nav_record`），与批量备份方法（调用存储过程，参考 `backup_nav_history`）。

### 4.2 计算层（Analytics 纯函数）

- **FR-7** 新增 `app/analytics/position_analysis.py`，所有函数无 DB 依赖，输入为已查出的快照序列，便于单元测试。
- **FR-8** 提供「区间概览」计算：区间起始/结束日期、最新市值、最新盈亏率、区间最高市值、区间最低市值、最大回撤率、区间累计盈亏变化。
- **FR-9** 提供「最大回撤」计算：遍历市值序列，求峰值到后续谷值的最大跌幅比例。
- **FR-10** 提供「占比」计算：给定当日全部持仓快照，计算各持仓市值占总市值比例（供饼图）。
- **FR-11** 盈亏率口径统一为 `profit_loss / cost_amount × 100`（百分比数值），与 `position` 表一致。

### 4.3 后端任务

- **FR-12** 新增 `backup_position_snapshot_task`，每日凌晨 3 点（cron `0 3 * * *`）执行，备份**昨日**所有有效持仓（`position.del_flag='1'`）的快照。
- **FR-13** 快照时盈亏重算：取每个持仓的 `shares`/`cost_price`/`cost_amount`，结合当天 `fund_info.net_asset_value` 作为 `current_price`，重算 `current_value = shares × current_price`、`profit_loss = current_value - cost_amount`、`profit_loss_rate = profit_loss / cost_amount × 100`。
- **FR-14** 备份走「应用层 + 存储过程双路径」：日常定时备份走应用层（可测试、可日志追踪），另提供存储过程 `backup_position_daily_snapshot()` 供 DBA 手动运维（幂等：先按 `snapshot_date` 删除再插入）。`source` 标记为 `system`。
- **FR-15** 任务在 `app/task/register_task.py` 注册，并在 `task_schedule` 表配置 cron（调度器每 60 秒 hash 比对热加载，无需重启）。
- **FR-16** 任务异常不中断调度器，由 `run_with_trace_context` 捕获并记录到 `system_log`。

### 4.4 后端 API

- **FR-17** 持仓信息管理复用现有 `/api/positions` CRUD（已存在），无需新增。
- **FR-18** 新增 `GET /api/positions/snapshot/options`：返回可选持仓列表（`position_id`、`fund_code`、`fund_name`），供分析页下拉选择。
- **FR-19** 新增 `GET /api/positions/snapshot/analysis`：参数 `position_id`、可选 `start_date`/`end_date`，返回 `{overview, series, max_drawdown, pie}`。其中 `series` 为该持仓的每日快照序列（日期、市值、盈亏、盈亏率）；`pie` 为当日全部持仓市值占比。
- **FR-20** 新增 `GET /api/positions/snapshots`：分页查询快照列表（供调试/管理页可选展示），参数 `position_id`、`fund_code`、日期范围、分页。
- **FR-21** 所有接口统一 `try/except`，异常返回 `{error}` + 适当 HTTP 状态码；用 `@log_request` 装饰器记录 trace_id 链路。

### 4.5 前端

- **FR-22** 新增「持仓分析」一级菜单（`meta.sort=15`），下含两个二级菜单：持仓信息管理（`sort=16`）、持仓分析（`sort=17`），通过 `isParent:true` + `children` + `parentTitle` 配置。
- **FR-23** 在 `Layout.vue` 的 `iconMap` 添加父菜单与两个子菜单的图标映射（从 `@element-plus/icons-vue` 选取）。
- **FR-24** 新增 `PositionManage.vue`（持仓信息管理）：搜索区（基金代码/名称）+ `el-table`（基金代码、名称、份额、成本价、现价、市值、盈亏、盈亏率、买入日期、操作）+ `el-pagination` + 增删改弹窗。风格参考 `IndexInfo.vue`。
- **FR-25** 新增 `PositionAnalysis.vue`（持仓分析）：参考 `IndexAnalysis.vue` 多区域布局——顶部控制栏（持仓下拉 + 快捷时间范围 radio + 日期选择器 + 查询按钮）、概览卡片、盈亏比例折线图、持仓金额折线图、最大回撤/峰值指标区、持仓占比饼图。
- **FR-26** 分析页默认时间范围为「全部」（因不回填历史，初期数据点少）；快捷范围含近1月/3月/6月/1年/全部。
- **FR-27** 分析页按单个持仓选择；盈亏比例折线图、持仓金额折线图、最大回撤/峰值针对选中持仓；持仓占比饼图固定展示全部持仓当前市值占比（不受单持仓选择影响）。
- **FR-28** 配色遵循 A 股惯例：涨红（`#f56c6c`/`#ef4444`）、跌绿（`#67c23a`/`#10b981`），与 `IndexAnalysis.vue`/`PortfolioBoard.vue` 一致。
- **FR-29** 图表用 `useEChart` composable 管理生命周期；饼图需在 `utils/echarts.js` 注册 `PieChart` 及所需 Component。
- **FR-30** 新增 `positionAnalysisApi` API 对象（`src/api/index.js`），方法：`getOptions`、`getAnalysis`、`getSnapshots`。
- **FR-31** 前端改动后必须在 `frontend/` 目录执行 `npm run build` 并提交 `dist/`（CLAUDE.md 前端构建门禁）。

### 4.6 SQL

- **FR-32** 新建 `sql/struct/position_daily_snapshot.sql` 建表脚本。
- **FR-33** 新建 `sql/program/持仓每日快照备份.sql` 存储过程脚本。
- **FR-34** 在 `task_schedule` 表新增任务配置行（可用 `sql/alter/` 下的 seed 脚本）。

## 5. 非目标（Out of Scope）

- **不回填历史快照**：快照表从今天开始积累，不利用 `fund_nav_history` 历史净值回填历史。
- **不修复 `position` 表盈亏不刷新问题**：本功能仅在快照时重算盈亏，不改动 `update_fund_net_values_task` 对 `position` 的回写逻辑（避免影响现有持仓看板）。
- **不管理组合-持仓关联**：持仓信息管理页只做持仓 CRUD，组合关联仍在 `PortfolioBoard` 管理。
- **不做组合级分析**：分析页按单持仓选择，不提供组合汇总分析曲线。
- **不做定投模拟**：持仓分析不含定投模拟（指数分析已有该功能，持仓场景不同）。
- **不做多用户权限**：沿用单用户设计，菜单对所有登录用户可见。

## 6. 依赖（Dependencies）

- **`position` 表**：快照数据源（份额、成本、买入日期）。
- **`fund_info` 表**：最新净值来源（`net_asset_value`），用于快照时重算盈亏。
- **`fund_nav_history` 表**：参考其快照表设计模式（唯一键、source、备份任务），不直接依赖其数据。
- **现有 `/api/positions` CRUD**：持仓信息管理页复用。
- **`useEChart` composable、`utils/echarts.js`**：前端图表渲染。
- **`StorageBase`、`get_db_engine`/`get_db_session`**：后端 Storage 基础设施。
- **APScheduler + `task_schedule` 表**：定时任务调度与热加载。
- **`run_with_trace_context`**：任务异常隔离与 trace_id 链路。

## 7. 时间线与优先级（Timeline & Priority）

单用户个人项目，无外部 deadline。建议按以下阶段交付（Phase 5 实现时遵循 TDD）：

- **P0 数据层**：建表脚本 + Storage + `__init__.py` 导出（FR-1~6）。
- **P0 计算层（TDD 先行）**：`analytics/position_analysis.py` 纯函数 + 单元测试（FR-7~11）。
- **P0 任务层**：备份任务 + 注册 + cron 配置 + 存储过程（FR-12~16, 32~34）。
- **P1 API 层**：3 个新接口（FR-18~21）。
- **P1 前端-管理页**：`PositionManage.vue` + 路由 + API（FR-22~24, 30）。
- **P1 前端-分析页**：`PositionAnalysis.vue` + 饼图注册（FR-25~31）。
- **P2 构建**：`npm run build` + 提交 `dist/`（FR-31）。

## 8. 风险评估（Risk Assessment）

| 风险 | 类型 | 影响 | 缓解 |
|------|------|------|------|
| `fund_info` 净值未更新时快照盈亏失真 | 技术 | 快照用旧净值，曲线失真 | 备份任务凌晨 3 点跑，此时当日净值任务（每30分钟）已多次执行；日志记录每个持仓取到的净值 |
| 持仓软删除但 `portfolio_position` 关联未清理 | 数据 | 已知问题，快照只取 `position.del_flag='1'`，不受影响 | 快照范围明确只含有效持仓；不在本功能修复关联问题 |
| 最大回撤计算口径歧义 | UX | 用户对回撤定义有不同理解 | PRD 明确：峰值到后续谷值的最大跌幅比例，文档说明 |
| 饼图与单持仓选择逻辑矛盾 | UX | 选单持仓时饼图无意义 | 已决策：饼图固定展示全部持仓，不受选择影响（FR-27） |
| 初期数据点少，折线图几乎空白 | UX | 上线初期体验差 | 默认时间范围设为「全部」（FR-26）；随时间自然改善 |
| 存储过程与应用层双路径逻辑不一致 | 技术 | 两条路径算出的盈亏可能不同 | 两者盈亏公式统一（FR-11/13），应用层为主路径，存储过程仅手动运维用 |
| `echarts.js` 未注册 PieChart 导致饼图报错 | 技术 | 饼图不显示 | FR-29 明确需注册 PieChart；实现时验证 |

## 9. 无障碍要求（Accessibility）

- 图表提供标题（`el-card` header 文字说明），非纯视觉依赖。
- 概览卡片数值用文字 + 颜色双编码（涨红跌绿同时有 `+/-` 符号），不仅依赖颜色辨识。
- 表格用 `el-table` 原生组件，支持键盘导航。
- 遵循项目现有 Element Plus 默认无障碍水平，无额外特殊要求。

## 10. 设计考量（Design Considerations）

- **布局参考**：`PositionAnalysis.vue` 复用 `IndexAnalysis.vue` 的 6 区域结构（控制栏 → 概览卡片 → 主图 → 辅助图区 → 指标区），保持视觉一致。
- **配色**：A 股涨红跌绿，与 `IndexAnalysis.vue`/`PortfolioBoard.vue` 统一。
- **组件复用**：`useEChart` composable、`el-card`、`el-table`、`el-pagination`、`el-date-picker`、`el-radio-group`（快捷时间）。
- **菜单图标**：持仓分析父菜单用 `PieChart`/`DataAnalysis` 类图标，子菜单用 `Document`/`DataLine` 类（从 `@element-plus/icons-vue` 选取，避免与现有图标重复）。
- **详细设计规范**：架构设计阶段（Phase 4）通过 `/frontend-design` 输出 `DESIGN.md`，明确色彩、字体、组件规范。

## 11. 技术考量（Technical Considerations）

- **盈亏重算跨表**：快照需 JOIN `position`（份额/成本）与 `fund_info`（净值）。应用层实现可测试性更好；存储过程实现性能更好但逻辑埋在 SQL。已决策双路径并存（FR-14）。
- **幂等备份**：存储过程采用「先按 `snapshot_date` 删除再插入」，允许重复执行不产生重复数据（参考 `backup_fund_nav_history`）。
- **快照范围**：仅 `position.del_flag='1'` 的有效持仓；不快照已软删除持仓。
- **无物理外键**：`position_id` 不建物理外键（项目惯例，数据一致性靠应用层），但加索引。
- **存储引擎/字符集**：`InnoDB` + `utf8mb4`，与全库一致。
- **TDD**：计算层（`analytics`）纯函数先写测试（最大回撤、占比、概览），再写实现。Storage/Task/API 按 `pytest` 现有模式补集成测试。
- **调度热加载**：新增 `task_schedule` 行后无需重启 scheduler，60 秒内自动加载。

## 12. 成功指标（Success Metrics）

- 快照任务每日成功执行，`system_log` 无 ERROR；`position_daily_snapshot` 表每日新增 N 条（N=当日有效持仓数）记录。
- 快照记录的盈亏与「当天净值重算」结果一致（抽查验证）。
- 持仓分析页四类图表正常渲染，无控制台报错；饼图正确展示全部持仓占比。
- 持仓信息管理页增删改查功能正常，与持仓看板数据同步。
- `analytics` 纯函数单元测试全绿。
- `npm run build` 成功，`dist/` 更新并提交。

## 13. 待解决问题（Open Questions）

- 快照表 `position_id` 若对应持仓被软删除，历史快照是否保留？**建议保留**（历史分析需要），实现时确认。
- 持仓信息管理页是否需要「立即触发一次快照」的按钮（手动补当天数据）？**建议作为后续增强**，不在本期范围。
- 存储过程 `backup_position_daily_snapshot()` 的盈亏重算 SQL 与应用层逻辑需保持公式完全一致，实现时对照验证。

---

## 附录：已确认决策汇总

| # | 决策项 | 选择 |
|---|--------|------|
| 1 | 快照粒度 | 按每条持仓（`position_id`+`snapshot_date`） |
| 2 | 盈亏口径 | 快照时按最新净值重算 |
| 3 | 持仓信息管理 | 独立表格管理页 |
| 4 | 分析图表 | 盈亏比例折线图 + 持仓金额折线图 + 最大回撤/峰值 + 持仓占比饼图 |
| 5 | 快照频率 | 每日凌晨 3 点备份昨天 |
| 6 | 历史回填 | 不回填 |
| 7 | 分析范围 | 按单个持仓选择 |
| 8 | 菜单排序 | sort=15 紧跟持仓看板 |
| 9 | 饼图矛盾 | 饼图固定展示全部持仓当前市值占比 |
| 10 | 备份实现 | 应用层 + 存储过程双路径 |
| 11 | 管理页范围 | 仅持仓 CRUD |
| 12 | 默认时间范围 | 默认全部 |
