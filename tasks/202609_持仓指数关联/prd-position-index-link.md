# PRD: 持仓关联指数（position-index-link）

**Feature slug**: `position-index-link`

## 1. 概述（Introduction/Overview）

持仓管理页（`PositionManage.vue`）当前只记录基金本身的持仓信息（代码/份额/成本/盈亏等），无法表达"这只基金跟踪/对标某个市场指数"的关联关系。本功能在持仓表新增一个"关联指数"字段，用户可在新增/编辑持仓时从指数信息列表（`index_info` 去重后的指数）中选择一个指数进行关联，并在持仓列表中展示。

本次只做"关联关系的存储与展示"，为后续"基金 vs 指数"对比分析打基础，不做对比计算。

## 2. 功能目标（Goals）

- `position` 表新增 `index_code` 字段（可空），存储关联的指数代码。
- 持仓管理页新增/编辑弹窗提供指数选择器（内联 `el-select`，数据源 `indexApi.getOptions()`），选填。
- 持仓列表表格新增"关联指数"列，展示指数名称（前端 `code -> name` 映射）。
- 后端 `PositionStorage` 与 `/api/positions` 接口透传 `index_code`。
- 存量持仓不受影响（`index_code` 为 NULL，列表该列显示"-"）。

## 3. 用户故事（User Stories）

- 作为定投用户，我想给某只基金持仓关联一个对标指数（如沪深300），以便后续对比基金与指数走势。
- 作为定投用户，我想在持仓列表直接看到每条持仓关联的指数名称。
- 作为定投用户，我想在编辑持仓时修改或取消关联的指数。
- 作为定投用户，存量未关联指数的持仓仍能正常显示，不强制补录。

## 4. 功能需求（Functional Requirements）

1. **数据库**：`position` 表新增 `index_code varchar(10) NULL DEFAULT NULL`，注释"关联指数代码"。通过 `sql/alter/` 增量脚本，不修改 `struct/position.sql`。
2. **后端模型**：`Position` 模型新增 `index_code` 列。
3. **后端存储**：`get_positions_with_pagination` / `get_position_by_id` 返回的 dict 包含 `index_code`；`create_position` / `update_position` 接收并写入 `index_code`（`update_position` 已有 `hasattr` 通用循环，新增列自动覆盖；`create_position` 显式构造 `Position` 对象，需手动加）。
4. **后端接口**：`/api/positions` 的 POST/PUT 透传 `index_code`（Phase 2 确认 web `api_server` 是否直接转发 data dict）。
5. **前端 API**：`portfolioApi.createPosition/updatePosition` 直接传 form（含 `index_code`），无需改 API 层。
6. **前端选择器**：弹窗内新增"关联指数"`el-select`（`filterable` + `clearable`），数据源 `indexApi.getOptions()`，label 格式 `index_code - index_name`，value=`index_code`；选填。
7. **前端表格**：新增"关联指数"列，前端用已加载的指数选项做 `code -> name` 映射显示名称；未关联显示"-"。
8. **前端表单**：`onMounted` 加载指数选项（供选择器与列表映射共用）；编辑回显 `index_code`。
9. **校验**：`index_code` 选填；若填则必须是 `index_info` 中存在的 code（UI 限定选择器选项，后端可选软校验）。

## 5. 验收标准（Acceptance Criteria）

- [ ] `position` 表成功新增 `index_code` 列（alter 脚本可执行），存量行 `index_code` 为 NULL。
- [ ] 新增持仓时选择一个指数，保存后该持仓 `index_code` 正确入库；列表"关联指数"列显示对应指数名称。
- [ ] 编辑持仓时，能修改关联指数、能清空（取消关联），保存后正确更新。
- [ ] 不选择指数也能正常新增/编辑持仓（选填）。
- [ ] 存量持仓列表"关联指数"列显示"-"，无报错。
- [ ] `index_info` 无数据时，选择器为空选项、列表映射显示"-"，不报错。
- [ ] `PositionStorage` 相关单测覆盖 `index_code` 的增/改/查透传。
- [ ] `data-crawler` 全量 `pytest tests/ -q` 无回归。
- [ ] 前端 `npm run build` 通过，`dist/` 可提交。

## 6. 非目标（Non-Goals）

- 不做"基金 vs 关联指数"的走势对比/超额收益计算（属后续分析功能）。
- 不在组合看板（`PortfolioBoard`）、持仓分析（`PositionAnalysis`）页展示关联指数。
- 不存储 `index_name` 冗余字段（仅存 `index_code`，名称前端映射）。
- 不引入物理外键约束（遵循项目"无物理外键"约定）。
- 不做指数选择器远程搜索（指数数量少，本地 `filterable` 即可）。
- 不新建 `IndexSelect` 独立组件（仅一处使用，内联 `el-select`）。

## 7. 依赖（Dependencies）

- `index_info` 表与 `IndexInfoStorage.get_all_indexes()` / `/api/indexes/options` 接口（已存在）。
- `PositionStorage`、`/api/positions` CRUD 接口（已存在，需透传新字段）。
- 前端 `indexApi.getOptions()`（已存在）。
- `sql/alter/` 增量变更流程。

## 8. 时间与优先级（Timeline & Priority）

小到中等改动（SQL + 后端 + 前端三层，每层增量小），单次交付。优先级：中（增强型，非阻塞）。

## 9. 风险评估（Risk Assessment）

- **存量数据兼容**：新列可空，存量 NULL，风险低。
- **指数改名脏数据**：仅存 `index_code`，名称实时映射，无脏数据风险。
- **接口透传遗漏**：web `api_server` 若对 data 做了字段白名单，`index_code` 可能被丢。需在 Phase 2 确认 `/api/positions` 路由实现。
- **前端映射依赖选项加载**：列表 `code -> name` 依赖 `getOptions` 已返回；若接口失败需兜底显示 code 或"-"。

## 10. 无障碍（Accessibility）

沿用 Element Plus 默认无障碍特性，`el-select` 键盘可达。无额外要求。

## 11. 设计考量（Design Considerations）

- 选择器与 `FundSelect` 视觉一致：label `code - name`，`filterable` + `clearable`。
- 表格"关联指数"列宽度适中（~120px），未关联显示"-"。
- 弹窗表单项顺序：在"买入日期"附近加"关联指数"（具体位置 Phase 4 定）。

## 12. 技术考量（Technical Considerations）

- 遵循项目分层：`sql/alter` 增量脚本 -> storage 模型+方法 -> web 接口 -> 前端 api+view。
- `update_position` 的 `hasattr` 通用循环天然支持新列；`create_position` 显式构造 `Position` 对象，需手动加 `index_code`。
- 列表 dict 需手动加 `index_code` 到两处返回（分页列表 `get_positions_with_pagination` + `get_position_by_id`）。
- 前端 `form` 初始值需含 `index_code: ''`。

## 13. 成功指标（Success Metrics）

- 用户能为持仓关联指数并在列表看到。
- 无回归（pytest 全绿、前端 build 通过）。

## 14. Open Questions（Phase 3 已澄清）

- **`/api/positions` 透传方式**（已确认）：`POST/PUT /api/positions` 直接把整个 `request.get_json()` data dict 传给 `_position_storage.create_position/update_position`，**无字段白名单**。因此 web 层零改动，`index_code` 自动流入 storage。`GET /api/indexes/options` 返回 `{data:[{index_code,index_name,index_type}]}`（已存在）。
- **现有 position 测试**（已确认）：无 position CRUD 测试（仅 `test_position_analysis.py` 属快照分析）。项目测试模式 = mock storage / 抽纯函数，绝不连真实库（conftest 注释明确）。新建 `tests/test_position_index_link.py`，以 mock SQLAlchemy session 方式验证 `index_code` 透传。
- **alter 脚本命名**（已定）：`sql/alter/add_position_index_code.sql`（与 `add_fund_buyer_shares.sql`/`add_index_info_source.sql`/`add_position_unique_index.sql` 命名一致）。
- **表格"关联指数"列位置**（Phase 4 设计定）：见 `design-position-index-link.md`。
