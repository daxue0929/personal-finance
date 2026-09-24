# DESIGN.md：持仓分析功能前端设计规范

> 创建日期：2026-07-13
> 依据：从 `IndexAnalysis.vue`、`IndexInfo.vue`、`PortfolioBoard.vue` 提取的现有设计系统
> 适用：`PositionManage.vue`、`PositionAnalysis.vue` 两个新页面

---

## 1. 设计原则

- **视觉一致**：新页面严格沿用现有页面的卡片、配色、间距，不引入新设计语言。
- **复用优先**：优先复用 `useEChart` composable、`el-card`/`el-table`/`el-pagination`/`el-date-picker`/`el-radio-group` 等已有组件与模式。
- **A股惯例**：涨红跌绿，与 `IndexAnalysis.vue`/`PortfolioBoard.vue`/`IndexInfo.vue` 完全一致。

## 2. 色彩规范

| 用途 | 色值 | 使用场景 |
|------|------|----------|
| 涨/盈利 | `#f56c6c`（Element Plus danger） | 盈亏为正的数值、折线上升段、阳线 |
| 跌/亏损 | `#67c23a`（Element Plus success） | 盈亏为负的数值、折线下降段、阴线 |
| 主色/中性强调 | `#409EFF`（Element Plus primary） | 默认指标卡左边框、主图均线之一 |
| 次要文本 | `#909399` | 指标标签、辅助说明 |
| 正文 | `#303133` | 指标数值、主文本 |
| 弱化文本 | `#c0c4cc` | 指标副标题（如日期） |
| 卡片背景 | `#fff` | 卡片底色 |
| 搜索区背景 | `#fafafa` | 搜索区背景（参考 IndexInfo） |
| 分隔线 | `#eee` | 搜索区与表格的分隔 |

**涨跌色应用规则**：盈亏类数值同时用「颜色 + `+/-` 符号」双编码（不仅依赖颜色，满足无障碍）。

## 3. 字体规范

| 层级 | 字号 | 字重 | 用途 |
|------|------|------|------|
| 页面/卡片标题 | 16px | 500 | `el-card` header 文字 |
| 指标数值 | 24px | 600 | 概览卡片主数值（参考 IndexAnalysis `.metric-value`） |
| 指标数值-小 | 20px | 600 | 定投/分析结果卡片数值 |
| 指标标签 | 13px | 400 | 概览卡片标签（`.metric-label`） |
| 指标副标题 | 12px | 400 | 概览卡片副信息（`.metric-sub`，如日期） |
| 正文 | 14px | 400 | 表格、表单、说明文字 |

字体族沿用 Element Plus 默认（系统字体栈），不单独设置。

## 4. 组件规范

### 4.1 页面容器

- **分析页**：外层 `<div style="padding: 20px;">`，参考 `IndexAnalysis.vue`。
- **管理页**：外层 `<div style="height:100%; display:flex; flex-direction:column;">` + 单个 `el-card` 包裹（flex:1），参考 `IndexInfo.vue`。

### 4.2 卡片（el-card）

统一样式：`box-shadow: none;`，`body-style="{ padding: '16px 20px' }"`。卡片之间 `margin-bottom: 16px`。

### 4.3 概览指标卡（metric-card）

复用 `IndexAnalysis.vue` 的 `.metric-card` 样式：
```
背景 #fff；圆角 4px；左边框 3px solid <强调色>；
padding 14px 16px；margin-bottom 12px；
box-shadow 0 1px 3px rgba(0,0,0,0.04)
```
响应式网格：`el-row :gutter="16"` + `el-col :xs="12" :sm="8" :md="6"`。

### 4.4 搜索区（管理页）

参考 `IndexInfo.vue`：
- 背景 `#fafafa`，`padding: 20px`，`border-bottom: 1px solid #eee`。
- `el-form inline`，末尾「搜索」(primary) + 「重置」按钮。
- 日期选择器用 `value-format="YYYY-MM-DD"`，开始/结束互相约束 `disableStart`/`disableEnd`。

### 4.5 数据表格（管理页）

- `el-table` 全宽，`v-loading`。
- 数值列 `align="right"`，用 `fmt()` 格式化（保留2位小数，null 显示 `-`）。
- 盈亏列用涨跌色 + 符号：`{{ row.profit_loss >= 0 ? '+' : '' }}{{ fmt(row.profit_loss) }}`。
- 操作列：编辑/删除按钮（参考 PortfolioBoard 的 `el-button size="small" circle`）。

### 4.6 分页

参考 `IndexInfo.vue`：`text-align: right; margin-top: 20px;`，`layout="total, sizes, prev, pager, next, jumper"`，`page-sizes=[10,20,50,100]`，默认 `pageSize=20`。

### 4.7 控制栏（分析页）

参考 `IndexAnalysis.vue` 顶部 `el-card`：持仓下拉（`el-select` 220px）+ 快捷时间 `el-radio-group`（近1月/3月/6月/1年/全部）+ 开始/结束 `el-date-picker`（联动约束）+ 查询按钮。

### 4.8 图表

- 用 `useEChart` composable 管理 init/resize/dispose。
- 图表容器统一 `height`：主图 400px，辅助图 320px，饼图 320px。
- tooltip `trigger: 'axis'`（折线）或默认（饼图）。
- 折线图盈亏系列：盈亏为正段红、为负段绿（可用 `visualMap` 或分段着色）。

### 4.9 弹窗（管理页增删改）

`el-dialog` width 500px，`el-form label-width="100px"`，参考 `PortfolioBoard.vue` 的持仓弹窗（基金代码 select、份额、成本价、现价、买入日期）。

## 5. 菜单与图标

- 一级菜单「持仓分析」`meta.sort=15`，`isParent:true`。
- 子菜单：持仓信息管理 `sort=16`、持仓分析 `sort=17`，均带 `parentTitle:'持仓分析'`。
- `Layout.vue` 的 `iconMap` 新增映射（从 `@element-plus/icons-vue` 选取，避免与现有重复）：
  - `/position-analysis`（父）→ `PieChart`
  - `/position-analysis/manage` → `Wallet`（若已用于 /funds 则改 `Coin`）
  - `/position-analysis/analysis` → `TrendCharts`（若已用于 /funds/history 则改 `DataLine`，若 DataLine 已用于 /index/analysis 则用 `Histogram`）
  - **实现时确认图标唯一性，优先选用未被占用的图标**。

## 6. ECharts 注册

`utils/echarts.js` 需新增注册（持仓分析用饼图）：
```js
import { LineChart, BarChart, CandlestickChart, PieChart } from 'echarts/charts'
// PieChart 依赖的 TooltipComponent、LegendComponent 已注册；
// 饼图标签用 series.label 内置，无需额外 Component。
echarts.use([..., PieChart])
```

## 7. 布局结构

### 7.1 PositionManage.vue（管理页）
```
el-card (flex:1)
├ 搜索区 (#fafafa)：基金代码 | 基金名称 | 搜索 | 重置
└ 表格区 (padding:20px)
  ├ el-table：代码/名称/份额/成本价/现价/市值/盈亏/盈亏率/买入日期/操作
  └ el-pagination (右对齐)
+ el-dialog 增删改弹窗
```

### 7.2 PositionAnalysis.vue（分析页）
```
div (padding:20px)
├ 控制栏 el-card：持仓下拉 | 快捷时间 radio | 开始 | 结束 | 查询
├ 概览卡片 el-row（最新市值/最新盈亏率/区间最高市值/区间最低市值/最大回撤率/区间盈亏变化）
├ 主图 el-card：盈亏比例折线图 (400px)
├ 双图 el-row :gutter=16
│  ├ el-col :md=12：持仓金额(市值)折线图 (320px)
│  └ el-col :md=12：持仓占比饼图 (320px)  ← 固定展示全部持仓
└ 指标区 el-card：最大回撤/峰值详情（文字+数值卡片）
```

## 8. 质量门禁

- 改动 `frontend/src/` 后，`git push` 前必须在 `frontend/` 执行 `npm run build`，更新 `dist/` 并提交。
- 实现完成后对照本规范逐项检查（Phase 6 质量审查重点）。
