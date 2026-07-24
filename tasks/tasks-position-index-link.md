# Task List: position-index-link

**Based on PRD**: `tasks/prd-position-index-link.md`
**Design**: `tasks/design-position-index-link.md`

## Relevant Files

### Files to Create
- `sql/alter/add_position_index_code.sql` - position 表新增 `index_code` 列的增量脚本
- `data-crawler/tests/test_position_index_link.py` - `index_code` 透传测试（TDD，mock session）

### Files to Modify
- `data-crawler/app/storage/position_storage.py` - `Position` 模型加列 + 三处 dict 返回 + `create_position` 透传
- `frontend/src/views/PositionManage.vue` - 加载指数选项 + 弹窗选择器 + 表格列 + 编辑回显

### 不改动（已确认）
- `data-crawler/app/web/api_server.py` - POST/PUT `/api/positions` 已整体透传 data dict，零改动
- `frontend/src/api/index.js` - `portfolioApi` 直接传 form、`indexApi.getOptions` 已存在，零改动

## Implementation Tasks

### 1. 数据库变更：position 表新增 index_code 列
**Effort Estimate**: Small

#### Sub-tasks:
- [x] 1.1 新建 `sql/alter/add_position_index_code.sql`：`ALTER TABLE position ADD COLUMN index_code varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '关联指数代码';`（命名与 `add_fund_buyer_shares.sql` 等一致）
- [ ] 1.2 在目标库执行 alter 脚本，确认 `position` 表新增 `index_code` 列、存量行值为 NULL（**待部署执行**：conftest 提示 .env 指生产库，未擅自对生产库执行 schema 变更；后端测试 mock 不依赖该列）

### 2. 后端存储层：Position 模型 + CRUD 透传 index_code（TDD）
**Effort Estimate**: Small

#### Sub-tasks:
- [x] 2.1 **[测试先行]** 新建 `tests/test_position_index_link.py`，mock SQLAlchemy session，写用例：① `create_position` 传入 `index_code` 时写入 Position 对象；② `index_code` 缺省时不报错；③ `get_position_by_id` 返回 dict 含 `index_code`；④ `get_positions_with_pagination` 返回 dict 含 `index_code`；⑤ `update_position` 透传 `index_code`
- [x] 2.2 跑 `python3 -m pytest tests/test_position_index_link.py -q` 确认用例失败（红）—— 5 failed（TypeError/AttributeError/KeyError）
- [x] 2.3 `Position` 模型加 `index_code = Column(String(10))`
- [x] 2.4 `get_positions_with_pagination` / `get_position_by_id` / `get_position_by_fund_code` 三处返回 dict 加 `'index_code': position.index_code`
- [x] 2.5 `create_position` 构造 `Position(...)` 加 `index_code=data.get('index_code')`
- [x] 2.6 跑 `python3 -m pytest tests/test_position_index_link.py -q` 通过（绿）—— 5 passed
- [x] 2.7 跑 `python3 -m pytest tests/ -q` 确认无回归 —— 196 passed；12 failed+2 error 均为预存在失败（`test_eastmoney_index_parser.py` 引用已搁置删除的模块、`test_fund_homepage_fetch.py` 为未跟踪 WIP 网络测试），与本改动无关

### 3. 前端持仓管理页：PositionManage.vue
**Effort Estimate**: Small

#### Sub-tasks:
- [x] 3.1 `import { indexApi }`；新增 `indexOptions` ref；`onMounted` 调 `indexApi.getOptions()` 填充，失败 `ElMessage.error` 兜底且保持空数组
- [x] 3.2 `form` 初始值加 `index_code: ''`；`showAddDialog` 重置含 `index_code`；`showEditDialog` 回显 `row.index_code`
- [x] 3.3 弹窗加「关联指数」`el-form-item` + `el-select`（`filterable` + `clearable`，`el-option` label `` `${o.index_code} - ${o.index_name}` ``、value `o.index_code`），置于「买入日期」之后
- [x] 3.4 表格加「关联指数」`el-table-column`（width 120），置于「买入日期」列之后
- [x] 3.5 `indexName(code)` 映射函数：`indexOptions` 中查 `index_code === code` 取 `index_name`，找不到回退显 `code`，无 code 显 `-`；模板调用

### 4. 前端构建门禁
**Effort Estimate**: Small

#### Sub-tasks:
- [x] 4.1 `frontend/` 执行 `npm run build` 通过 -- ✓ built in 3.62s
- [x] 4.2 更新后的 `dist/` 纳入提交（`git push` 前必须，服务器靠 `git pull` 拿 `dist/` 部署）-- dist 已重建（5 文件变更），待 git 提交时一并纳入

### 5. 质量审查与验收
**Effort Estimate**: Small

#### Sub-tasks:
- [x] 5.1 `data-crawler/` 跑 `python3 -m pytest tests/ -q` 全量回归，无失败 -- 196 passed；12 failed+2 error 均为预存在失败（与本改动无关）
- [x] 5.2 对照 `tasks/prd-position-index-link.md` 验收标准逐条核对 -- 全部达标（详见总结）
- [x] 5.3 对照 `tasks/design-position-index-link.md` 一致性检查清单核对前端 -- 8 项全符
- [x] 5.4 reviewer 自审（简洁/DRY、功能正确性、项目规范），中改主任务自审即可 -- 通过
- [x] 5.5 收尾：点一遍 prd/design/tasks 三文档状态，总结改动文件清单与后续建议

## Notes

- **依赖顺序**：1（DB）→ 2（后端 TDD）→ 3（前端）→ 4（构建）→ 5（审查）。后端测试在 2.1 先行。
- **web/api 层零改动**：`POST/PUT /api/positions` 已整体透传 data dict（已确认）。
- **update_position 无需改逻辑**：`hasattr` 通用循环天然支持新列，仅靠模型加列即可透传；2.x 测试仍覆盖以验证。
- **前端无独立单测基建**（仅 FundSelect 有 vitest），以 `npm run build` + 手动验收为门禁。
- **风险**：alter 脚本需在目标库执行；`indexOptions` 加载失败需兜底（映射回退显 code 或 `-`）。
