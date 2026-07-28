# 前端设计规范：持仓分析跳转指数分析（position-to-index-analysis）

> 本规范作为 Phase 6 质量审查的对照基线。本功能是「在既有控制栏加一个跳转按钮」性质，与既有 PositionAnalysis 按钮一致，不引入新视觉。

## 1. 设计目标与原则

- **一致性优先**：「指数分析」按钮与既有「查询」按钮同排、EP 默认按钮风格。
- **状态清晰**：无关联指数 / 全部持仓时按钮置灰（disabled），用户一眼知道不可用。
- **复用路由**：`router.push` + query 传参，遵循 vue-router 既有用法。

## 2. 色彩规范

- 沿用 EP 默认主题。「查询」按钮 `type="primary"`，「指数分析」按钮 `type="success"`（与查询区分，表"跳转到另一分析"）。
- disabled 态用 EP 默认置灰样式，不自定义。

## 3. 字体规范

- 沿用 EP 默认字体栈，按钮文字与既有一致，不单独设。

## 4. 组件规范

### 4.1 「指数分析」按钮

| 项 | 值 |
|---|---|
| 位置 | 控制栏「查询」按钮之后（同一 el-form-item 或相邻） |
| 文案 | `指数分析` |
| 类型 | `el-button type="success"` |
| disabled | `!currentIndexCode`（全部持仓 / 无关联指数时置灰） |
| tooltip（可选） | disabled 时 hover 提示「该持仓未关联指数」，用 el-tooltip 包裹 |

### 4.2 交互

- `currentIndexCode` computed：从 positionOptions 找当前 positionId 匹配项的 index_code；positionId 为 'all' 或无匹配 -> null。
- 点击 `goIndexAnalysis()`：`router.push({ path:'/index/analysis', query:{ index_code: currentIndexCode }})`。
- 跳转后指数分析页读 query 初始化。

### 4.3 指数分析页接收（IndexAnalysis.vue）

- `useRoute` 读 `route.query.index_code`。
- onMounted：fetchOptions 后，若 query.index_code 存在且在 indexOptions 中 -> `indexCode.value = query.index_code`；否则维持默认。
- 无 query 时行为不变（默认 000688 / 首个）。

## 5. 测试规范（TDD）

- 后端：`tests/test_position_to_index_analysis.py`，测 `get_position_options` 返回含 index_code（mock session join）。
- 前端：既有页面加按钮 + query 接收，无独立单测，以 `npm run build` + 手动验收为门禁。

## 6. 一致性检查清单（Phase 6 对照）

- [ ] 「指数分析」按钮 type=success，置于查询按钮后
- [ ] 无关联指数 / 全部持仓时按钮 disabled 置灰
- [ ] 点击 router.push 带 query index_code，当前页跳转
- [ ] 指数分析页读 query 初始化选中指数，无 query 行为不变
- [ ] 色彩/字体沿用 EP 默认，无新色板
- [ ] `npm run build` 通过，`dist/` 提交
