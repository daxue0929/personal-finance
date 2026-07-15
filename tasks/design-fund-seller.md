# DESIGN：基金卖出流水 + 持仓分析累计收益图

> 文档版本：v1.0　|　创建日期：2026-07-15　|　关联 PRD：`tasks/prd-fund-seller.md`
> 前端规范文档，覆盖色彩、字体、组件规范，指导卖出流水页与累计收益图的实现。
> 注：本文件由 `/frontend-design` 方法论产出（该命令在当前环境未注册为可调用 skill，故直接应用其规范生成）。

---

## 1. 设计总则

### 1.1 设计目标

- **一致性优先**：卖出流水页完全复用买入流水页（FundBuyer.vue）的布局与交互模式，零学习成本。
- **对称语义**：买入用 ShoppingCart 图标 + 主色按钮，卖出用 Sell 图标 + 对称布局，形成"买/卖"自然成对。
- **A股配色**：涨红跌绿，与 IndexAnalysis / PortfolioBoard / PositionAnalysis 完全统一，避免红绿混淆。
- **优雅降级**：金额/盈亏未计算时显示"-"，无图表数据时显示 el-empty。

### 1.2 参考实现

| 现有文件 | 复用内容 |
|----------|----------|
| `FundBuyer.vue` | 卖出流水页整体布局、搜索区、功能区、表格、分页、对话框、排序 localStorage |
| `PositionAnalysis.vue` | 累计收益图的 useEChart composable、分段着色、0 轴水面线、概览卡片、持仓下拉 |
| `Layout.vue` iconMap | 菜单图标映射机制 |

---

## 2. 色彩规范（Color）

### 2.1 语义色板

| 语义 | 色值 | 用途 |
|------|------|------|
| 涨/盈利 | `#f56c6c`（深）/ `#ef4444`（亮） | 正盈亏数值、上升段折线 |
| 跌/亏损 | `#67c23a`（深）/ `#10b981`（亮） | 负盈亏数值、下降段折线 |
| 主色 | `#409EFF` | 主按钮、链接、主图基色、卡片左边框 |
| 市值蓝 | `#5470C6` | 市值折线图、累计收益图辅助 |
| 中性灰阶 | `#303133` / `#606266` / `#909399` / `#c0c4cc` | 主文字 / 常规文字 / 次要文字 / 占位 |
| 边框/背景 | `#eee` / `#f5f7fa` / `#fafafa` | 分隔线 / hover / 搜索区底色 |

### 2.2 卖出流水页配色应用

- **已实现盈亏列**：`≥0` 用涨红 `#f56c6c`，`<0` 用跌绿 `#67c23a`，0 用中性 `#303133`。
- **卖出状态 el-tag**：PENDING->warning(黄)、SUCCESS->success(绿)、FAILED->danger(红)。
- **卖出类型 el-tag**：'1'手动->info(灰)、'2'止盈->success(绿)、'3'止损->danger(红)。
- **功能按钮**：新增卖出记录(primary)、刷新金额(warning)。

### 2.3 累计收益图配色

- 折线分段着色：相邻两点盈亏上升用 `#f56c6c`，下降用 `#67c23a`（与盈亏率走势图同款逻辑）。
- 数据点 symbol：首点按自身正负着色，后续按相对前点变化方向着色。
- 0 轴水面线：`#909399` 虚线，label "0 元"。
- 面积填充（可选）：正盈亏区域淡红 `rgba(245,108,108,0.15)`，负盈亏区域淡绿 `rgba(103,194,58,0.15)`。

---

## 3. 字体规范（Typography）

| 元素 | 字号 | 字重 | 颜色 |
|------|------|------|------|
| 页面标题/卡片标题 | 14px | 500 | #303133 |
| 表格表头 | 14px | 500 | #909399（Element 默认） |
| 表格正文 | 14px | 400 | #303133 |
| 数值（金额/份额） | 14px | 500 | #303133（盈亏按涨跌着色） |
| 概览卡片标签 | 13px | 400 | #909399 |
| 概览卡片数值 | 20px | 600 | #303133（盈亏按涨跌着色） |
| 概览卡片副标 | 12px | 400 | #c0c4cc |
| 次要说明 | 11-12px | 400 | #909399 |

- 数值格式：金额 `toFixed(2)` 带千分位 `toLocaleString('zh-CN')`，份额 `toFixed(4)`，盈亏率 `+x.xx%`/`-x.xx%`，盈亏金额 `+¥123.45`/`-¥123.45`（符号统一在 ¥ 前）。
- 复用 PositionAnalysis.vue 已有的 `num` / `money` / `signedMoney` / `pct` 格式化函数。

---

## 4. 组件规范（Components）

### 4.1 卖出流水页（FundSeller.vue）

#### 4.1.1 整体布局

```
┌─ el-card（flex 纵向，撑满）─────────────────────────────┐
│ 搜索区（padding 20px，背景 #fafafa，底边框 #eee）          │
│ [基金代码][基金名称][卖出类型▾][卖出状态▾][日期范围] [搜索][重置] │
├──────────────────────────────────────────────────────────┤
│ 功能区（padding 20px，flex space-between，底边框 #eee）     │
│ [新增卖出记录][刷新金额]            (右侧预留更多功能 popover) │
├──────────────────────────────────────────────────────────┤
│ 数据表格（padding 20px）                                  │
│ ID|基金代码|基金名称|卖出日期|卖出份额|卖出金额|卖出净值|     │
│ 已实现盈亏|卖出类型|卖出状态|备注|操作[编辑][删除]           │
│ ─────────────────────────────────────────────────────── │
│ 分页（右对齐）                                            │
└──────────────────────────────────────────────────────────┘
```

#### 4.1.2 搜索区

- `el-form inline`，5 个搜索条件 + 2 按钮，与 FundBuyer 完全一致。
- 卖出类型下拉：手工卖出(1)/止盈卖出(2)/止损卖出(3)。
- 卖出状态下拉：未执行(PENDING)/已成功(SUCCESS)/执行失败(FAILED)。

#### 4.1.3 功能区

- 左侧两按钮：`新增卖出记录`(primary)、`刷新金额`(warning，`:loading="refreshing"`)。
- 右侧 MoreFilled popover（预留"导出数据"，标"开发中"，与买入页对称）。

#### 4.1.4 数据表格

`el-table`，全部列 `sortable="custom"`（后端排序），默认按 time 降序。

| 列 | prop | width | 渲染 |
|----|------|-------|------|
| ID | id | 80 | 文本 |
| 基金代码 | fund_code | 120 | 文本 |
| 基金名称 | fund_name | 200 | 文本 |
| 卖出日期 | time | 120 | 文本 |
| 卖出份额 | shares | 120 | `toFixed(4)` |
| 卖出金额 | amt | 120 | 有值 `toFixed(2)`，空显示 `-` |
| 卖出净值 | nav | 120 | 有值 `toFixed(4)`，空显示 `-` |
| 已实现盈亏 | realized_profit | 140 | 有值 `signedMoney`+涨跌色，空显示 `-` |
| 卖出类型 | type | 120 | el-tag（typeMap 映射） |
| 卖出状态 | sell_status | 120 | el-tag（statusMap 映射） |
| 备注 | remark | 自适应 | 文本 |
| 操作 | - | 200, fixed=right | 编辑(small)+删除(small,danger) |

#### 4.1.5 新增/编辑对话框（el-dialog，width 600px）

| 字段 | 控件 | 说明 |
|------|------|------|
| 选择基金* | el-select filterable remote | 远程搜索，选中自动填基金名称 |
| 基金名称 | el-input disabled | 自动填充 |
| 卖出日期* | el-date-picker | 默认今天 |
| 卖出份额* | el-input | 必填 >0 |
| 卖出金额 | el-input disabled | placeholder "自动计算" |
| 卖出净值 | el-input disabled | placeholder "自动计算" |
| 已实现盈亏 | el-input disabled | placeholder "自动计算" |
| 卖出类型 | el-select | 手动卖出(1)/止盈卖出(2)/止损卖出(3)，默认1 |
| 卖出状态 | el-select | PENDING/SUCCESS/FAILED，默认 PENDING |
| 备注 | el-input textarea | 可选 |

提交校验：fund_code + time + shares(>0) 必填。

#### 4.1.6 刷新金额交互

- 点击 `刷新金额` -> `taskApi.runTask('calculate_seller_amount_task')` -> 成功提示"金额刷新已触发，请稍后刷新页面查看结果" -> 2 秒后 `fetchSellers()` 刷新表格。
- 与 FundBuyer 的 `refreshShares` 完全对称。

### 4.2 持仓分析页扩展（PositionAnalysis.vue）

#### 4.2.1 持仓下拉新增"全部持仓"选项

```
持仓▾
├ 全部持仓        ← 新增首项（value: '' 或 'all'）
├ 基金A (011613)
├ 基金B (020292)
└ 基金C (160424)
```

- 选中"全部持仓"时，所有图表/卡片切换为组合级聚合视角。
- 选中单持仓时，维持现有单持仓行为。

#### 4.2.2 布局变化（新增累计收益图）

```
┌─ 控制栏（持仓▾ 全部持仓选项 + 时间范围 + 查询）─────────┐
├─ 概览卡片行（6 张，新增"累计已实现盈亏"卡片）──────────┤
├─ 盈亏比例走势（折线图，400px）                          │
├─ 市值走势(320px) │ 持仓占比饼图(320px)                  │
├─ 累计收益走势（新增·折线图，320px）← 每日盈亏序列       │
└────────────────────────────────────────────────────────┘
```

#### 4.2.3 累计收益走势图规范

- 第 4 个 `useEChart` 实例：`const { chartRef: profitChartRef, setOption: setProfit } = useEChart()`。
- 数据源：后端 `portfolio_series`，每项含 `snapshot_date` + `profit_loss`。
- 口径：
  - 全部持仓：每日 SUM(全部持仓 profit_loss)。
  - 单持仓：该持仓每日 profit_loss。
- 渲染逻辑（镜像 `renderRate` 分段着色）：
  - 每段相邻两点一条稀疏 line series，颜色按盈亏变化方向（上升红/下降绿）。
  - 主 series 承载全部点（symbol + tooltip + 0 轴 markLine）。
  - 0 轴水面线 `{ yAxis: 0 }`，label "0 元"，`#909399` 虚线。
- tooltip：`trigger: 'axis'`，显示日期 + "累计盈亏：±¥xxx.xx"。
- 坐标轴：x=category(日期, rotate 30)，y=value(元)。
- 无数据：`el-empty`。

#### 4.2.4 概览卡片新增"累计已实现盈亏"

- 卡片标签"累计已实现盈亏"，值 = SUM(fund_seller.realized_profit where sell_status=SUCCESS)。
- 着色：≥0 涨红，<0 跌绿，左边框同色。
- 副标"历史卖出已实现"。
- 位于现有 6 张卡片之后（第 7 张），或替换布局为 7 列（响应式 :md=3）。

### 4.3 路由与菜单

- 路由：`/sellers` -> `FundSeller.vue`，`meta: { title: '基金卖出流水', sort: 25 }`，Layout 子路由（非嵌套）。
- Layout.vue iconMap 新增 `'/sellers': Sell`（从 @element-plus/icons-vue 导入 Sell）。
- 菜单顺序：持仓看板(10) > 持仓分析(15) > 基金买入流水(20) > **基金卖出流水(25)** > 基金信息管理(30) > ...。

### 4.4 API 封装（api/index.js）

新增 `sellerApi`：

```js
export const sellerApi = {
  getSellers: (params) => api.get('/sellers', { params }),
  getSeller: (id) => api.get(`/sellers/${id}`),
  createSeller: (data) => api.post('/sellers', data),
  updateSeller: (id, data) => api.put(`/sellers/${id}`, data),
  deleteSeller: (id) => api.delete(`/sellers/${id}`)
}
```

持仓分析 `getAnalysis` 响应扩展字段：`portfolio_series`（累计收益序列）、`realized_profit_total`（累计已实现盈亏）。

---

## 5. 交互细节规范

### 5.1 状态反馈

| 场景 | 反馈 |
|------|------|
| 刷新金额触发 | 按钮 loading + ElMessage.success"金额刷新已触发…" |
| 新增/编辑成功 | ElMessage.success + 关闭对话框 + 刷新列表 |
| 删除 | ElMessageBox.confirm 二次确认 -> success/取消无提示 |
| 校验失败 | ElMessage.warning 提示缺填项 |
| 请求失败 | ElMessage.error |

### 5.2 排序持久化

- 排序变化存 localStorage：`seller_sort_field` / `seller_sort_order`。
- 页面 onMounted 从 localStorage 恢复排序状态。

### 5.3 金额/份额空值处理

- 未计算（NULL）字段统一显示 `-`，不显示 0，避免与"实际为 0"混淆。
- 表格 `amt`/`nav`/`realized_profit` 三列均按此规则。

---

## 6. 质量门禁对照（实现时须符合）

- [ ] 卖出页布局与 FundBuyer.vue 一致（搜索区+功能区+表格+分页+对话框）。
- [ ] 配色严格遵循 A 股涨红跌绿，与现有页面统一。
- [ ] 累计收益图复用 useEChart，分段着色与盈亏率走势图同款逻辑。
- [ ] 持仓下拉"全部持仓"选项工作正常，视角切换正确。
- [ ] 数值格式化复用 num/money/signedMoney/pct。
- [ ] 改动 frontend/src/ 后，push 前执行 `npm run build` 并提交 dist/。
