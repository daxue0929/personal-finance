# DESIGN.md：基金列表页定投计划入口改造

> 关联 PRD：`tasks/prd-fund-list-dip-entry.md`
> 适用页面：`frontend/src/views/FundManage.vue`（基金信息管理）

---

## 1. 设计定位

本次是**现有内部管理后台的功能性改造**，不引入新视觉语言。延续项目既有设计基线：

- **组件库**：Element Plus 默认主题（`element-plus/dist/index.css`），无自定义 CSS 变量文件，样式以组件 props + 行内 style 为主。
- **金融语义色**：A 股涨红跌绿（红 `#f56c6c`、绿 `#67c23a`），用于盈亏着色（与 IndexAnalysis/PositionAnalysis/PortfolioBoard 一致）。本次改造不涉及盈亏，不使用红绿。
- **主色**：Element Plus Primary `#409EFF`（蓝），用于可交互链接、主按钮、激活态。
- **中性色**：`#303133`（主文字）、`#606266`（常规文字）、`#909399`（次要/标签）、`#c0c4cc`（占位/禁用）、`#e4e7ed`（边框）、`#fafafa`（区块背景）。

**改造范围**：搜索区合并 + 表格增列 + 定投管理弹窗。全部复用上述既有色板与 Element Plus 组件，不新增色值、不新增字体。

---

## 2. 布局规范

### 2.1 搜索区（改造前 → 后）

```
改造前（三个 form-item 横排）：
[基金代码: 输入框] [基金名称: 输入框] [基金类型: 下拉] [搜索][重置]

改造后（两个 form-item 横排，更紧凑）：
[基金: 下拉搜索框 width:280px] [基金类型: 下拉 width:120px] [搜索][重置]
```

- 下拉搜索框 `el-select`：`filterable` + `remote` + `clearable`，`placeholder="输入代码或名称搜索"`，`width: 280px`。
- 选项 label：`{基金代码} - {基金名称}`，value：`基金代码`。
- 选中后触发列表查询（按 fund_code 精确过滤）。

### 2.2 表格新增列位置

```
... 备注 | 定投计划 | 操作(fixed right)
```

- 「定投计划」列位于「备注」与「操作」之间，`min-width: 160`。
- 单元格内容垂直居中，可点击（`cursor: pointer`）。

### 2.3 定投管理弹窗

- `el-dialog`，`width: 560px`，标题 `定投计划 - {基金代码} {基金名称}`。
- 内部结构（复用上一轮编辑弹窗内定投区块样式）：
  - 顶部：定投计划表格（size="small"），列：频率 / 金额(元) / 启用(switch) / 操作(删除 link)。
  - 中部：新增计划行（`v-if`，背景 `#fafafa`，圆角 4px，padding 12px），inline form。
  - 底部：`+ 添加定投计划` 按钮（plain primary，small）。

---

## 3. 组件规范

### 3.1 定投概要单元格（表格列）

| 状态 | 文案 | 样式 |
|------|------|------|
| 无计划（或全停用） | `无` | 灰色 `#c0c4cc`，不可点击感（但仍可点打开弹窗新增） |
| 有计划 | `3条：每日/每周三/等2条` | 主色 `#409EFF`，`el-button link` 样式，hover 加深 |

- 概要格式：`{启用条数}条：{前2条频率摘要}/{等N条}`，超过2条截断显示「等N条」。
- 频率摘要文案：每日→`每日`、weekly→`每周X`、monthly→`每月X号`。
- `tooltip`：「点击管理定投计划」。
- 点击：打开该基金定投管理弹窗。

### 3.2 下拉搜索框交互状态

| 状态 | 表现 |
|------|------|
| 默认 | placeholder「输入代码或名称搜索」 |
| 输入中 | remote 触发，loading 时下拉显示 `el-select` 默认 loading |
| 无匹配 | 下拉空提示「无匹配基金」 |
| 已选中 | 显示「代码 - 名称」，右侧 clearable × 清除 |
| 清除 | 列表回到无 fund_code 过滤（显示全部，受类型筛选） |

- 最小输入 1 字符触发搜索；remote 自带防抖。

### 3.3 定投管理弹窗 CRUD 元素

| 操作 | 组件 | 交互 |
|------|------|------|
| 启停 | `el-switch`（active-value="1" inactive-value="0"） | 切换即调 PUT，失败回滚 |
| 删除 | `el-button link danger small`「删除」 | ElMessageBox 二次确认 |
| 新增 | inline form：频率 select + 条件日期 select + 金额 input-number + 保存/取消 | 保存调 POST，成功刷新列表 |
| 金额 | `el-input-number`（:min="1" :precision="2" width:120px） | 必填 >0 |

---

## 4. 色彩与字体

不新增。沿用：

- 文字：主 `#303133`、次要 `#909399`、占位/无数据 `#c0c4cc`。
- 交互：链接/激活 `#409EFF`、删除 danger `#f56c6c`。
- 背景：区块 `#fafafa`、卡片白 `#fff`、边框 `#eee`/`#e4e7ed`。
- 字体：系统默认（Element Plus 继承），无自定义字体族。字号跟随 Element Plus 默认（表格 small、弹窗标题默认）。

---

## 5. 质量门禁（对应 CLAUDE.md）

- 改动 `frontend/src/` 后，`git push` 前必须在 `frontend/` 执行 `npm run build` 并提交更新后的 `dist/`。
- 响应式：搜索区/弹窗在窄屏下 Element Plus form inline 自动换行，无需额外处理。
- 键盘可达：el-select/el-dialog/el-switch 均为 Element Plus 原生，支持键盘操作。
- 空状态：定投弹窗表格无数据 `empty-text="暂无定投计划"`；下拉无匹配显示「无匹配基金」。

---

## 6. 与 PRD 的对应

- FR-1（搜索区合并）→ 2.1
- FR-3（定投列）→ 2.2 + 3.1
- FR-4（独立弹窗 CRUD）→ 2.3 + 3.3
- FR-5（移除编辑弹窗区块）→ 实现阶段清理，不影响设计
- FR-6（概要数据）→ 3.1 概要文案规则
