# 前端设计规范：持仓成本价↔指数对应图表（position-cost-index-chart）

> 本规范作为 Phase 6 质量审查的对照基线。本功能是「在既有页面加一张图表」性质，设计目标是**与既有 PositionAnalysis 图表完全一致**，不引入新视觉风格。与 `design-position-index-link.md` 同属一致性优先类。

## 1. 设计目标与原则

- **一致性优先**：新图表卡在结构、配色、交互上与 PositionAnalysis 既有 4 张图（el-card + header + `useEChart`）无感融合。
- **复用既有机制**：`useEChart` composable + ECharts 按需注册（`src/utils/echarts.js`），不引入新图表库或新依赖。
- **A股配色语义**：涨红跌绿（`#f56c6c`/`#67c23a`）仅用于涨跌语义；本图三条线是"成本/指数/转换"，非涨跌，用中性区分色，避免语义混淆。

## 2. 色彩规范

- 沿用 Element Plus 默认主题 + 既有 PositionAnalysis 配色常量（`C_PRIMARY=#409EFF`、`C_VALUE=#5470C6`、`UP=#f56c6c`、`DOWN=#67c23a`）。
- 本图三线配色（中性区分，非涨跌语义）：
  - 成本价（基金净值，左轴）：`#5470C6`（蓝，与市值图一致）
  - 实际指数（右轴）：`#FAC858`（金）
  - 成本对应指数点（右轴，步进）：`#EE6666`（红，虚线 step）--红色仅表"成本基准线"标识，不表涨跌
- 不引入渐变/阴影装饰（与既有图一致）。

## 3. 字体规范

- 沿用项目既有字体（EP 默认），卡片 header `font-weight:500`（与既有卡片一致），不单独设字号。

## 4. 组件规范（新图表卡）

### 4.1 卡片结构

| 项 | 值 |
|---|---|
| 卡片 header | `成本价与指数对应走势` |
| 卡片样式 | 复用既有 `el-card` + `:body-style="{padding:'16px 20px'}"` + `box-shadow:none` |
| 图表高度 | `320px`（与累计收益图一致） |
| 空状态 | 无快照数据 -> `el-empty description="暂无快照数据"` |
| 显示条件 | `v-if="positionId !== 'all'"`（全部持仓隐藏整张卡） |

### 4.2 双轴 ECharts 配置

- **xAxis**：`type:'category'`，data = points.date，`axisLabel.rotate:30`（与既有图一致）。
- **yAxis**（双轴）：
  - 左轴：`name:'基金净值'`，`position:'left'`，成本价用。
  - 右轴：`name:'指数点位'`，`position:'right'`，指数/转换线用。
  - 无关联指数时只显示左轴（右轴 hidden）。
- **series**：
  1. 成本价：`type:'line'`，`step:'end'`（步进），`yAxisIndex:0`，色 `#5470C6`，`symbol:'none'`。
  2. 实际指数：`type:'line'`，`yAxisIndex:1`，色 `#FAC858`，`symbol:'none'`，`smooth:true`。
  3. 成本对应指数点：`type:'line'`，`step:'end'`，`yAxisIndex:1`，色 `#EE6666`，`lineStyle.type:'dashed'`，`symbol:'none'`。
- **tooltip**：`trigger:'axis'`，显示日期 + 三线值（成本价保留 4 位、指数点位保留 2 位）。
- **legend**：顶部，`data:['成本价','实际指数','成本对应指数点']`。
- 无指数数据时（ratio 空）：只渲染 series 1（成本价），隐藏 series 2/3 与右轴。

### 4.3 放置位置

- 置于「累计收益走势」图之后（页面底部），不打乱既有 4 图布局。
- 单持仓时该卡出现在累计收益图下方；全部持仓时该卡不渲染。

## 5. 状态与交互

- 数据获取：`positionId` 变化或日期变化时，若 `positionId !== 'all'`，调 `positionAnalysisApi.getCostIndex({position_id, start_date, end_date})`。
- 与既有 `fetchAnalysis` 并行触发（不阻塞既有图）。
- `points` 存入 ref；`useEChart` 的 `setOption` 渲染。
- 无关联指数（`index_code` 空 / `ratio` 空）：只画成本价折线（左轴），右轴隐藏。
- 接口失败：`ElMessage.error('获取成本指数数据失败')`，图表区 `el-empty`。

## 6. 测试规范（TDD）

- 后端：`tests/test_position_cost_index_chart.py`，测 `compute_cost_index_series` 纯函数（ratio/cost_in_index/join/边界）。先写测试再实现。
- 前端：既有页面增量图表，无独立单测基建，以 `npm run build` + 手动验收为门禁。

## 7. 一致性检查清单（Phase 6 对照）

- [ ] 新卡片样式（el-card/header/高度 320/empty）与既有图一致
- [ ] 双轴：成本价左轴步进 + 实际指数右轴 + 成本对应指数点右轴虚线步进
- [ ] 配色中性区分（蓝/金/红虚线），未误用涨红跌绿语义
- [ ] 全部持仓时 `v-if` 隐藏整卡
- [ ] 无关联指数时只画成本价、隐藏右轴
- [ ] 复用 `useEChart`，未引入新依赖
- [ ] tooltip/legend 完整
- [ ] `npm run build` 通过，`dist/` 提交
