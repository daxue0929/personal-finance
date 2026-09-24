# 前端设计规范：持仓关联指数（position-index-link）

> 本规范作为 Phase 6 质量审查的对照基线。本功能是「在既有页面增量加字段」性质，设计目标是**与既有 Element Plus 界面完全一致**，不引入新视觉风格。与 `design-fund-code-search-select.md` 同属一致性优先类。

## 1. 设计目标与原则

- **一致性优先**：新增的指数选择器与「关联指数」列在视觉与交互上必须与 `PositionManage.vue` 既有控件（尤其 `FundSelect`、既有 `el-table-column`）无感融合，不突出、不另类。
- **不新建组件**：指数数量少（个位数），用内联 `el-select` + `filterable` 本地过滤即可，不新建 `IndexSelect.vue`（与 `FundSelect` 的"远程搜索"复杂度不同，此处过度抽象无收益）。
- **遵循项目约定**：`<script setup>` + `<style scoped>`；API 调用走 `@/api` 的 `indexApi`；选项加载与映射复用同一份 `indexOptions`。
- **复用既有数据源**：指数选项来自已存在的 `indexApi.getOptions()`（`GET /indexes/options`），不新增接口。

## 2. 色彩规范

- 沿用 Element Plus 默认主题，不新增色板、不改主题色。
- 选中项高亮、clearable 清除按钮、loading 图标均为 EP 默认（主色 `#409EFF` 系）。
- 不引入渐变、阴影装饰、自定义背景色。

## 3. 字体规范

- 沿用项目既有字体（Element Plus 默认字体栈），不引入新字体。
- 选项 label、placeholder、表格单元格字号与既有 `el-select`/`el-table-column` 一致（EP 默认 14px），不单独设字号。

## 4. 组件规范（内联 el-select + 表格列）

### 4.1 指数选择器（弹窗内 el-form-item）

| 项 | 值 | 说明 |
|---|---|---|
| 标签 | `关联指数` | 与既有表单项标签风格一致（label-width 100px） |
| 控件 | `el-select` | `filterable` + `clearable`，**不用 remote**（项少） |
| placeholder | `请选择指数` | |
| 选项 label | `` `${o.index_code} - ${o.index_name}` `` | 与 FundSelect 的 `code - name` 格式一致 |
| 选项 value | `o.index_code` | |
| 必填 | 否 | 选填；清空即取消关联 |
| 宽度 | `100%` | 跟随 `el-form-item`，与同弹窗其他控件一致 |

- 选项来源：`indexOptions` ref（`onMounted` 时 `indexApi.getOptions()` 拉取一次，供选择器与表格列映射共用）。
- 编辑回显：`showEditDialog` 时 `form.index_code = row.index_code`；因 `indexOptions` 已在 `onMounted` 加载，`el-select` 自动显示对应 label。
- 边界：若 `index_code` 不在 `indexOptions`（如该指数已从 `index_info` 删除），`el-select` 显示空白——属可接受边缘情况（罕见）。

### 4.2 表格「关联指数」列

| 项 | 值 |
|---|---|
| 列标题 | `关联指数` |
| 宽度 | `120` |
| 对齐 | 默认（左） |
| 内容 | 用 `indexOptions` 做 `index_code -> index_name` 映射显示名称；无关联（`index_code` 为空/null）显示 `-` |
| 位置 | 紧随「买入日期」列之后（描述性字段靠后归组，不挤占前部数值列） |

- 映射函数：`indexName(code)` -> 在 `indexOptions` 中找 `index_code === code` 取 `index_name`，找不到回退显示 `code`（兜底），无 code 显示 `-`。

### 4.3 弹窗表单项顺序（编辑/新增弹窗）

```
基金代码（必填，FundSelect）
基金名称（disabled）
持仓份额（必填）
成本价（必填）
当前净值
买入日期（必填）
关联指数（选填，el-select）      ← 新增项
```

- 「关联指数」放在「买入日期」之后（弹窗末尾），不插入数值字段之间。

## 5. 状态与交互

- `indexOptions`：`ref([])`，`onMounted` 调 `indexApi.getOptions()` 填充；接口失败时 `ElMessage.error('获取指数选项失败')` 并保持空数组（选择器空选项、表格映射回退显示 code 或 `-`）。
- `form.index_code`：初始值 `''`（新增）/ `row.index_code`（编辑）；`showAddDialog` 重置时置 `''`。
- 提交：`portfolioApi.createPosition/updatePosition` 现有调用直接传 `form`（含 `index_code`），无需改 API 层。
- 清空：`el-select` clearable，清空时 `form.index_code` 置 `''`（取消关联）。

## 6. 测试规范（TDD）

- 后端：`data-crawler/tests/test_position_index_link.py`，mock SQLAlchemy session，验证 `create_position` 写入 `index_code`、`get_position_by_id`/`get_positions_with_pagination` 返回 dict 含 `index_code`、`update_position` 透传 `index_code`。先写测试再改实现。
- 前端：本功能前端为既有页面增量改动，沿用项目"前端无独立单测基建"现状（项目前端仅 FundSelect 有 vitest 单测），以 `npm run build` 通过 + 手动验收为门禁。

## 7. 一致性检查清单（Phase 6 对照）

- [ ] 指数选择器 `filterable` + `clearable`，label `code - name`，value `index_code`
- [ ] 选择器选项与表格列映射共用同一份 `indexOptions`（`onMounted` 拉取一次）
- [ ] 表格「关联指数」列在「买入日期」之后，未关联显示 `-`
- [ ] 色彩/字体沿用 EP 默认，无新色板/新字体/装饰
- [ ] 编辑回显 `index_code` 正常
- [ ] 不选指数也能新增/编辑（选填）
- [ ] `indexApi.getOptions()` 失败有兜底（不报错、映射回退）
- [ ] `npm run build` 通过，`dist/` 提交
