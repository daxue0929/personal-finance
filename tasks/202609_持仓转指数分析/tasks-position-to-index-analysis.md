# Task List: position-to-index-analysis

**Based on PRD**: `tasks/prd-position-to-index-analysis.md`
**Design**: `tasks/design-position-to-index-analysis.md`

## Relevant Files

### Files to Create
- `data-crawler/tests/test_position_to_index_analysis.py` - `get_position_options` 含 index_code 测试（TDD）

### Files to Modify
- `data-crawler/app/storage/position_daily_snapshot_storage.py` - `get_position_options` join position 补 index_code
- `frontend/src/views/PositionAnalysis.vue` - currentIndexCode + 「指数分析」按钮 + 跳转
- `frontend/src/views/IndexAnalysis.vue` - 读 route.query.index_code 初始化

### 不改动
- 指数分析既有分析逻辑、快照表结构、options 接口签名

## Implementation Tasks

### 1. 后端 options 加 index_code（TDD）
**Effort Estimate**: Small

#### Sub-tasks:
- [ ] 1.1 **[测试先行]** 新建 `tests/test_position_to_index_analysis.py`，测 `get_position_options`（mock session）：① 返回项含 index_code；② 无关联指数 -> index_code None；③ 保留 position_id/fund_code/fund_name
- [ ] 1.2 跑测试确认失败（红）
- [ ] 1.3 `get_position_options` 关联 Position 表补 index_code（distinct 快照 position_id，按 position_id 取 Position.index_code；outerjoin 或子查询）
- [ ] 1.4 跑测试通过（绿）

### 2. 前端持仓分析按钮
**Effort Estimate**: Small

#### Sub-tasks:
- [ ] 2.1 `PositionAnalysis.vue`：`useRouter`；`currentIndexCode` computed（positionOptions 找 positionId 匹配项 index_code，'all'/无匹配 -> null）
- [ ] 2.2 查询按钮后加「指数分析」`el-button type="success"`，`:disabled="!currentIndexCode"`
- [ ] 2.3 `goIndexAnalysis()` -> `router.push({ path:'/index/analysis', query:{ index_code: currentIndexCode }})`
- [ ] 2.4（可选）disabled 时 el-tooltip 提示「该持仓未关联指数」

### 3. 前端指数分析接收 query
**Effort Estimate**: Small

#### Sub-tasks:
- [ ] 3.1 `IndexAnalysis.vue`：`useRoute`；onMounted fetchOptions 后，若 `route.query.index_code` 存在且在 indexOptions 中 -> `indexCode.value = query.index_code`
- [ ] 3.2 无 query 时行为不变（默认 000688 / 首个）；query 指数不在选项时回退默认

### 4. 构建门禁 + 收尾
**Effort Estimate**: Small

#### Sub-tasks:
- [ ] 4.1 `pytest tests/ -q` 全量回归，无新增失败
- [ ] 4.2 `npm run build` 通过
- [ ] 4.3 `dist/` 纳入提交
- [ ] 4.4 对照 PRD 验收标准 + design 一致性清单逐条核对
- [ ] 4.5 reviewer 自审
- [ ] 4.6 总结：点文档状态，改动文件清单，后续建议

## Notes

- **依赖顺序**：1（后端 TDD）-> 2（持仓分析按钮）-> 3（指数分析接收）-> 4（构建+审查）。
- **index_code 来源**：`get_position_options` join Position 表（按 position_id）；软删除持仓 join 不到 -> null（按钮置灰，可接受）。
- **当前页跳转**：router.push 带 query，TagsView 保留 tab，可后退。
- **query 降级**：指数分析页 query 指数不在选项时回退默认，不报错。
