# 前端设计规范：买入流水补录（buyer-backfill）

> 本规范作为 Phase 6 质量审查的对照基线。本功能是「在既有页面加一个按钮+弹窗」性质，设计目标是**与既有 FundBuyer.vue 按钮/弹窗完全一致**，不引入新视觉风格。

## 1. 设计目标与原则

- **一致性优先**：补录按钮与既有「新增买入记录/快捷买入/刷新份额」同排同风格；补录弹窗复用既有新增弹窗结构与 EP 默认样式。
- **复用既有组件**：`FundSelect` 选基金、`el-date-picker` 选日期、`el-input` 金额，不引入新组件。
- **区别于新增**：补录是"一步到位"（建记录+算份额+更新持仓），用 `type="info"` 与新增(primary)区分；弹窗更精简（无份额/状态/策略字段，份额由后端算后提示）。

## 2. 色彩规范

- 沿用 EP 默认主题，不新增色板。
- 补录按钮 `type="info"`（与新增 primary、快捷 success、刷新 warning 区分）。
- 弹窗、表单、提示沿用 EP 默认（ElMessage success/warning/error）。

## 3. 字体规范

- 沿用 EP 默认字体栈，按钮/表单字号与既有新增弹窗一致，不单独设字号。

## 4. 组件规范

### 4.1 补录按钮

| 项 | 值 |
|---|---|
| 位置 | 功能栏，「刷新份额」之后、更多功能 popover 之前 |
| 文案 | `补录买入` |
| 类型 | `el-button type="info"` |
| 图标 | `Clock`（@element-plus/icons-vue，表"过去/补"语义） |

### 4.2 补录弹窗

| 项 | 值 |
|---|---|
| 标题 | `补录买入记录` |
| 宽度 | `500px`（字段少，比新增 600 略窄） |
| 表单 | `el-form label-width="100px"` |

字段（精简，无份额/状态/策略）：
- 选择基金（FundSelect，必填）
- 基金名称（disabled，选基金自动填）
- 买入日期（el-date-picker，默认今天，**可选过去日期**，必填）
- 买入金额（el-input，必填，>0）
- 买入类型（el-select，默认"手工买入"）
- 备注（el-input textarea）

### 4.3 提交结果提示

按后端 `position_updated` 分级提示（ElMessage）：
- `position_updated:true` -> `success`："补录成功，份额 {shares}，持仓已更新"。
- `position_updated:false` -> `warning`："补录成功，份额 {shares}，但该基金无持仓，未更新（请先建持仓）"。
- 净值缺失/异常 -> `error`（后端 error 文案）。
- 成功后关闭弹窗 + 刷新列表。

## 5. 交互

- 点「补录买入」-> 打开弹窗，默认今天、手工买入。
- 选基金 -> 自动填基金名称（FundSelect @select）。
- 提交校验：基金/日期/金额(>0)必填。
- 提交 -> `buyerApi.backfill(form)` -> 按结果提示 + 刷新。
- 买入日期允许过去（补录核心）。

## 6. 测试规范（TDD）

- 后端：`tests/test_buyer_backfill.py`，测纯函数 `compute_buyer_shares(amt, nav)`（正常/精度/nav<=0）。先写测试再实现。
- 前端：既有页面增量按钮+弹窗，无独立单测，以 `npm run build` + 手动验收为门禁。

## 7. 一致性检查清单（Phase 6 对照）

- [ ] 补录按钮 type=info + Clock 图标，与既有按钮同排
- [ ] 弹窗复用新增弹窗结构（el-dialog/el-form/FundSelect/el-date-picker）
- [ ] 字段精简（无份额/状态/策略），份额由后端算后提示
- [ ] 买入日期可选过去
- [ ] 结果提示按 position_updated 分 success/warning/error
- [ ] 色彩/字体沿用 EP 默认，无新色板
- [ ] `npm run build` 通过，`dist/` 提交
