# 前端设计规范：Dashboard 首页 + 持仓分析提示（dashboard-home）

> 本规范作为 Phase 6 质量审查的对照基线。Dashboard 是新页面但**沿用既有 PositionAnalysis 图表风格**（el-card + useEChart + EP 默认），不引入新视觉；tips 是既有页面加一个问号图标。

## 1. 设计目标与原则

- **一致性优先**：Dashboard 饼图卡复用 PositionAnalysis 的 `renderPie` 结构与配色；tips 用 EP `el-tooltip` + `QuestionFilled` 图标，与既有界面融合。
- **复用既有机制**：`useEChart` composable + ECharts 饼图按需注册，不引入新依赖。
- **首版克制**：Dashboard 只放一张持仓占比饼图 + 页头，留白为后续卡片预留，不堆砌。

## 2. 色彩规范

- 沿用 EP 默认主题 + PositionAnalysis 饼图配色（ECharts 默认色板，环形 `radius:['40%','70%']`）。
- 卡片白底、`box-shadow:none`，与既有页一致。
- 问号 tips 图标 `#909399`（EP info 灰），hover `#409EFF`。

## 3. 字体规范

- 沿用 EP 默认字体栈。Dashboard 页头标题 18px（与 Layout 侧栏标题量级），卡片 header `font-weight:500`（与 PositionAnalysis 卡一致）。

## 4. 组件规范

### 4.1 Dashboard 页面（`Dashboard.vue`）

| 项 | 值 |
|---|---|
| 容器 | `padding: 20px`（与 PositionAnalysis 一致） |
| 页头 | 可选简短标题「系统面板」或直接进卡片（首版从简，直接卡片） |
| 持仓占比卡 | `el-card box-shadow:none` + header「持仓占比（实时）」 |
| 图表高度 | `360px`（饼图舒展） |
| 空状态 | 无持仓 -> `el-empty description="暂无持仓"` |
| 布局 | 首版单卡；用 `el-row/el-col` 预留栅格，后续加卡片不重排 |

### 4.2 持仓占比饼图（复用 PositionAnalysis renderPie）

- `type:'pie'`，`radius:['40%','70%']`，`center:['50%','50%']`，环形。
- `itemStyle: borderRadius 4 / borderColor #fff / borderWidth 2`。
- label `{b}\n{d}%`，legend `bottom:0 type:scroll`。
- tooltip：`{name}<br/>市值：¥{value}<br/>占比：{percent}%`。
- data：`allocation.map(x => ({name: x.fund_name, value: x.value}))`。

### 4.3 持仓分析页 tips（`PositionAnalysis.vue`）

- 位置：页面顶部控制栏区域，加一个标题「持仓分析」+ 问号图标（若当前无显式标题，则在控制卡片 header 或首行加）。
- 图标：`QuestionFilled`（@element-plus/icons-vue），`el-tooltip` 包裹。
- 文案：`本页分析基于每日持仓快照（前一交易日数据）`。
- 样式：图标 `#909399` 16px，`margin-left:4px`，`cursor:help`。

## 5. 交互

- Dashboard `onMounted` 调 `positionApi.getAllocation()` -> 渲染饼图；失败 ElMessage.error + el-empty。
- 登录后默认落 `/dashboard`（router redirect）。
- 持仓分析 tips：hover 问号显示文案，无点击行为。

## 6. 测试规范（TDD）

- 后端：`tests/test_dashboard_home.py`，测 `get_all_active_positions`（mock session，返回全量 dict 含 current_value）+ 复用 `calc_position_allocation` 已有测试。先写测试再实现。
- 前端：新页面 + tips，无独立单测，以 `npm run build` + 手动验收为门禁。

## 7. 一致性检查清单（Phase 6 对照）

- [ ] Dashboard 饼图卡复用 PositionAnalysis renderPie 配色/结构（环形/label/legend/tooltip）
- [ ] Dashboard 布局用 el-row/el-col 预留栅格
- [ ] 持仓占比卡 header「持仓占比（实时）」，空数据 el-empty
- [ ] 持仓分析 tips：QuestionFilled + el-tooltip，文案「基于前一交易日快照」
- [ ] 色彩/字体沿用 EP 默认 + PositionAnalysis 配色，无新色板
- [ ] 复用 useEChart，无新依赖
- [ ] Dashboard 进菜单第一项 + 首页 redirect + TagsView affix 同步
- [ ] `npm run build` 通过，`dist/` 提交
