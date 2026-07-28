# PRD: 持仓分析跳转指数分析（position-to-index-analysis）

**Feature slug**: `position-to-index-analysis`

## 1. 概述

持仓分析页（`PositionAnalysis.vue`）查询按钮后新增「指数分析」按钮：点击后携带当前选中持仓关联的指数代码（`index_code`），跳转到指数分析页（`IndexAnalysis.vue`）并自动选中该指数。持仓未关联指数或选「全部持仓」时，按钮置灰不可点。

## 2. 功能目标

- 后端 `get_position_options` 返回项加 `index_code`（position 关联的指数）。
- 持仓分析页查询按钮后加「指数分析」按钮，`type` 区分。
- 按钮可用性：选中单持仓且有 `index_code` 时可点；「全部持仓」或无 index_code 时置灰。
- 点击 -> `router.push({ path:'/index/analysis', query:{ index_code } })`（当前页跳转）。
- 指数分析页接收 `route.query.index_code`，初始化选中该指数并触发分析。

## 3. 用户故事

- 作为用户，我在持仓分析看某只基金时，想一键跳到它对标指数的指数分析页，不用手动再选指数。

## 4. 功能需求

1. **后端 storage**（`position_daily_snapshot_storage.py`）：`get_position_options` 关联 position 表取 `index_code`，返回项加该字段（快照表无 index_code，需 join position 或按 position_id 查）。
2. **后端接口**：`/api/positions/snapshot/options` 返回项含 `index_code`（接口零改，storage 加字段即透传）。
3. **前端持仓分析**（`PositionAnalysis.vue`）：
   - 记录当前选中持仓的 `index_code`（从 positionOptions 找 position_id 匹配项）。
   - 查询按钮后加「指数分析」按钮，`:disabled="!currentIndexCode"`（全部持仓/无指数时置灰）。
   - 点击 `goIndexAnalysis()` -> `router.push({ path:'/index/analysis', query:{ index_code: currentIndexCode }})`。
4. **前端指数分析**（`IndexAnalysis.vue`）：
   - `useRoute` 读 `route.query.index_code`，若有则 `indexCode.value = query.index_code`（覆盖默认 000688）。
   - onMounted：fetchOptions 后，若 query 有 index_code 且在选项中，选中并分析。

## 5. 验收标准

- [ ] `get_position_options` 返回项含 `index_code`（关联指数，无则 null）。
- [ ] 持仓分析选单持仓（有指数）-> 「指数分析」按钮可点；选「全部持仓」或无指数持仓 -> 置灰。
- [ ] 点按钮跳转 `/index/analysis?index_code=xxx`，指数分析页自动选中该指数并展示分析。
- [ ] 指数分析页直接带 query 访问，正确初始化选中指数。
- [ ] 无 query 访问指数分析页时行为不变（默认 000688 或首个）。
- [ ] `get_position_options` 相关测试（TDD）；`pytest tests/ -q` 无回归；`npm run build` 通过、`dist/` 提交。

## 6. 非目标

- 不改指数分析页既有分析逻辑（只加 query 初始化）。
- 不做持仓与指数的对比分析（那是 cost-index 图，另论）。
- 不改快照表结构（index_code 从 position 表 join 取）。
- 全部持仓视角不做「聚合指数」跳转（无意义）。

## 7. 依赖

- `position.index_code`（position-index-link 已加）。
- `IndexAnalysis.vue` 的 indexCode + fetchOptions（已存在）。
- vue-router（query 传参）。

## 8. 风险评估

- **快照 options 取 index_code**：快照表无此字段，需 join position（按 position_id）。position 软删除后快照仍在，join 可能取不到 -> index_code null（按钮置灰，可接受）。
- **query 指数不在选项**：指数分析页 query 的 index_code 若不在 indexOptions（如指数已删），回退默认首个 + 提示或静默。
- **跳转后返回**：当前页跳转，浏览器后退可回持仓分析（TagsView 也留 tab）。

## 9. Open Questions（Phase 3 已澄清）

- **index_code 来源**：后端 `get_position_options` 加 index_code（join position）。
- **按钮可用性**：无关联指数 / 全部持仓时置灰。
- **跳转方式**：当前页 `router.push` 带 query。
- **涉及前端**：是（加按钮 + query 接收，触发 frontend-design）。
- **feature slug**：`position-to-index-analysis`。
