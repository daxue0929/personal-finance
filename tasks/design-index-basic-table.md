# Design — 指数基础管理页（index-basic-table）

> 文档版本：v1.0　|　创建日期：2026-08-06　|　状态：待实施
> 配套 PRD：`tasks/prd-index-basic-table.md`
> 落地文件：`frontend/src/views/IndexBasic.vue` + 路由/Layout 图标 + `IndexInfo.vue:64` 兜底

---

## 1. Subject grounding（先把"为谁做"钉死）

- **具体主体**：单用户内部 admin 页面，承载 4-100 行「指数元信息」（代码、市场、中文名、类型、启用状态、审计时间）。
- **受众**：用户本人（看盘型个人投资者，熟悉沪深交易所惯例，懂技术）。**不**是营销页、**不**是给陌生访客看的——所以**放弃**所有"惊艳型"视觉，押注"扫读效率 + 操作确定性"。
- **页面单一任务**：让用户**一眼看清当前抓取哪些指数**，并**3 步以内**完成"启停 / 改名 / 加新 / 弃用"。

## 2. 决策前自检（避开 3 个 AI 默认样式）

| AI 默认 | 为什么不适合本页面 | 我们的选择 |
|---------|------------------|----------|
| ① 米色背景 + 高对比衬线 + 赤陶色强调 | admin 表格 + 中文 + 高频扫读；衬线字会拖累列扫读 | 沿用项目 Element Plus 浅灰系 + 系统中文 sans |
| ② 近黑底 + 单一荧光绿/朱红 | 单用户本地工具，深色反而压视野、伤对比度 | 保持白底，仅在「启用」状态点用 Element Plus 标准绿 |
| ③ 大报版式 + 0 圆角 + 密集栏 | 表格行 4-100 条，需要 z 轴区分而不是 hairline 装饰 | 沿用 `el-table` 默认 + 1px `#eee` 分隔线（与 FundManage.vue 一致） |

**核心判断**：本页的"独特性"不在视觉装饰，而在一个**操作模型**——「行内 el-switch 即时启停」+「市场配色（沪蓝 / 深金）」。这是签名元素，承担"本页是 admin 数据表"的身份识别；其余全部走项目一致风格，**克制**。

## 3. Token 系统

### 3.1 颜色（10 个值 + 1 个语义状态色）

| Token | Hex | 用途 |
|-------|-----|------|
| `--bg-page` | `#f5f7fa` | 页面底色（项目统一） |
| `--bg-section` | `#fafafa` | 搜索/功能区底色（项目统一） |
| `--border-divider` | `#eee` | 搜索区与表格分隔线 |
| `--text-primary` | `#303133` | 主文字（项目统一） |
| `--text-secondary` | `#909399` | 副文字（disabled 状态、辅助说明） |
| `--color-primary` | `#409EFF` | 主操作按钮、新增 dialog 强调 |
| `--color-success` | `#67c23a` | 「启用」状态点（不靠 el-tag 文字，靠小圆点） |
| `--color-danger` | `#f56c6c` | 删除按钮、删除确认弹窗 |
| `--market-sh` | `#409EFF` | 沪市标签蓝（**签名色**之一） |
| `--market-sz` | `#e6a23c` | 深市标签金（**签名色**之一；沿用交易所惯例） |

**约束**：除上面 10 个 token 外，**不引入**新颜色。需要警示/警告时复用 `--color-danger` 或 `--text-secondary`。

### 3.2 字体（2 个角色，零新依赖）

| 角色 | 字体栈 | 用途 |
|------|--------|------|
| Body / 中文 | `-apple-system, "PingFang SC", "Microsoft YaHei", sans-serif` | 表头、表格内容、按钮（项目默认） |
| Data / 数字代码 | `"JetBrains Mono", "SF Mono", Menlo, Consolas, monospace` | 仅用于 `index_code` 列 + `create_time` / `update_time` 时间戳——tabular-nums 对齐方便扫读 |

**约束**：**不**引新字体。中文用系统默认，数字代码用 monospace 自带栈。

### 3.3 网格

- 页面外层：`el-card` 无边框无阴影，外 margin 20px（与 FundManage.vue 一致）
- 搜索区：内 padding 20px，1px 底边
- 功能区：内 padding 20px，1px 底边
- 数据区：内 padding 20px，flex column
- 分页：右对齐，距表 20px

## 4. 布局

### 4.1 ASCII 线框

```
┌────────────────────────────────────────────────────────────────┐
│  [搜索]  代码 [____]   类型 [全部▾]   [搜索] [重置]            │ ← 搜索区 #fafafa
├────────────────────────────────────────────────────────────────┤
│  [+ 新增指数]              显示已停用 [○━━]                    │ ← 功能区 #fafafa
├────────────────────────────────────────────────────────────────┤
│  代码    │ 名称    │ 市场│ 类型  │ 启用 │ 创建时间    │ 操作   │
│  ────────┼─────────┼────┼───────┼──────┼─────────────┼───────│
│  000300  │ 沪深300  │ 沪 │ 宽基  │ ●   │ 08-06 09:11 │ ⨀ 编辑 │
│          │         │    │       │      │             │   删除 │
│  000688  │ 科创50   │ 沪 │ 宽基  │ ●   │ 08-06 09:11 │ ⨀ 编辑 │
│          │         │    │       │      │             │   删除 │
│  000698  │ 科创100  │ 沪 │ 宽基  │ ●   │ 08-06 09:11 │ ⨀ 编辑 │
│          │         │    │       │      │             │   删除 │
│  399673  │ 创业板50 │ 深 │ 宽基  │ ●   │ 08-06 09:11 │ ⨀ 编辑 │
│          │         │    │       │      │             │   删除 │
│                                                                │
│  （空状态：0 行 + el-table 默认「暂无数据」，无插画）           │
├────────────────────────────────────────────────────────────────┤
│                                       共 4 条  [< 1 >]         │ ← 分页
└────────────────────────────────────────────────────────────────┘
```

**图例**：
- `●` = 启用（绿色 6px 圆点）
- `○` = 停用（灰色 6px 圆点）
- `⨀` = 行内 el-switch（停用时灰、启用时蓝绿）
- `沪`/`深` = 蓝/金 el-tag

### 4.2 列宽与对齐

| 列 | 宽度 | 对齐 | 备注 |
|----|------|------|------|
| `index_code` | 110 | left | monospace |
| `index_name` | 160 | left | 中文，溢出 ellipsis |
| `market` | 80 | center | el-tag 蓝/金 |
| `index_type` | 100 | center | el-tag size=small 灰底 |
| `enabled` | 80 | center | 6px 圆点 + 文字 |
| `create_time` | 170 | left | monospace，`YYYY-MM-DD HH:mm` |
| `update_time` | 170 | left | monospace，`YYYY-MM-DD HH:mm` |
| 操作 | 200（fixed=right） | center | el-switch + 编辑 + 删除 三个控件 |

**注意**：把 `enabled` 单独成列做"被动视觉"（圆点），把"主动控件"（el-switch）放到操作列——避免在两处都重复表达同一状态。

## 5. 签名元素（页面的「记住点」）

**两个签名，承担同一个身份识别**：

1. **行内 el-switch 即时启停**：操作列第一个控件，点击直接提交，0 中间态。`active-value="1"` / `inactive-value="0"`，`@change` 触发 `toggleEnabled(row)`。失败回滚 + ElMessage.error。这是 admin 数据表的「数据操作即操作」哲学。
2. **市场配色（沪蓝 / 深金）**：`market` 列用 el-tag 染色，sh→蓝、sz→金。沿用中国交易所惯例（一秒识别），不需要文字描述。

**不**做：暗色模式、动效过渡、复杂 empty state、空状态插画、引导动画。

## 6. 组件规范

### 6.1 搜索区

```vue
<el-form :model="searchForm" inline>
  <el-form-item label="代码">
    <el-input v-model="searchForm.index_code" placeholder="模糊匹配" clearable style="width: 140px;" />
  </el-form-item>
  <el-form-item label="类型">
    <el-select v-model="searchForm.index_type" clearable style="width: 140px;">
      <el-option label="全部" value="" />
      <el-option label="宽基指数" value="宽基指数" />
      <el-option label="行业指数" value="行业指数" />
      <el-option label="策略指数" value="策略指数" />
    </el-select>
  </el-form-item>
  <el-form-item>
    <el-button type="primary" @click="handleSearch">搜索</el-button>
    <el-button @click="resetSearch">重置</el-button>
  </el-form-item>
</el-form>
```

### 6.2 功能区

```vue
<div class="actions">
  <el-button type="primary" @click="showAddDialog">新增指数</el-button>
  <div class="spacer" />
  <span class="hint">显示已停用</span>
  <el-switch v-model="includeDisabled" @change="handleSearch" />
</div>
```

`includeDisabled` 切到 true 时调 `list({ includeDisabled: true })`；切回 false 调 `list({ includeDisabled: false })`。

### 6.3 表格

```vue
<el-table :data="list" v-loading="loading" style="width: 100%;" stripe>
  <el-table-column prop="index_code" label="代码" width="110" />
  <el-table-column prop="index_name" label="名称" min-width="160" show-overflow-tooltip />
  <el-table-column label="市场" width="80" align="center">
    <template #default="{ row }">
      <el-tag size="small" :type="row.market === 'sh' ? 'primary' : 'warning'" effect="light">
        {{ row.market === 'sh' ? '沪' : '深' }}
      </el-tag>
    </template>
  </el-table-column>
  <el-table-column prop="index_type" label="类型" width="100" align="center">
    <template #default="{ row }">
      <el-tag size="small" type="info" effect="plain">{{ row.index_type }}</el-tag>
    </template>
  </el-table-column>
  <el-table-column label="启用" width="80" align="center">
    <template #default="{ row }">
      <span :class="['status-dot', row.enabled === 1 ? 'on' : 'off']" />
      <span class="status-text">{{ row.enabled === 1 ? '启用' : '停用' }}</span>
    </template>
  </el-table-column>
  <el-table-column prop="create_time" label="创建时间" width="170" />
  <el-table-column prop="update_time" label="更新时间" width="170" />
  <el-table-column label="操作" width="200" fixed="right" align="center">
    <template #default="{ row }">
      <el-switch
        v-model="row.enabled"
        :active-value="1" :inactive-value="0"
        @change="(v) => toggleEnabled(row, v)"
        style="margin-right: 8px;"
      />
      <el-button link type="primary" size="small" @click="showEditDialog(row)">编辑</el-button>
      <el-button link type="danger" size="small" @click="confirmDelete(row)">删除</el-button>
    </template>
  </el-table-column>
</el-table>
```

**CSS（仅 4 个新类，作用域 scoped）**：

```vue
<style scoped>
.status-dot { display: inline-block; width: 6px; height: 6px; border-radius: 50%; margin-right: 6px; vertical-align: middle; }
.status-dot.on  { background: #67c23a; }
.status-dot.off { background: #c0c4cc; }
.status-text   { font-size: 12px; color: #909399; vertical-align: middle; }
.actions       { display: flex; align-items: center; gap: 12px; }
.actions .spacer { flex: 1; }
.actions .hint  { font-size: 13px; color: #606266; }
</style>
```

### 6.4 新增 / 编辑 dialog

```vue
<el-dialog v-model="dialogVisible" :title="editing ? '编辑指数' : '新增指数'" width="480px">
  <el-form :model="form" :rules="rules" ref="formRef" label-width="80px">
    <el-form-item label="代码" prop="index_code">
      <el-input v-model="form.index_code" :disabled="editing" maxlength="6" show-word-limit placeholder="6 位数字" />
    </el-form-item>
    <el-form-item label="市场" prop="market">
      <el-select v-model="form.market" :disabled="editing" style="width: 100%;">
        <el-option label="沪市 (sh)" value="sh" />
        <el-option label="深市 (sz)" value="sz" />
      </el-select>
    </el-form-item>
    <el-form-item label="名称" prop="index_name">
      <el-input v-model="form.index_name" maxlength="32" placeholder="如 沪深300" />
    </el-form-item>
    <el-form-item label="类型" prop="index_type">
      <el-select v-model="form.index_type" style="width: 100%;">
        <el-option label="宽基指数" value="宽基指数" />
        <el-option label="行业指数" value="行业指数" />
        <el-option label="策略指数" value="策略指数" />
      </el-select>
    </el-form-item>
    <el-form-item label="启用" prop="enabled">
      <el-switch v-model="form.enabled" :active-value="1" :inactive-value="0" />
    </el-form-item>
  </el-form>
  <template #footer>
    <el-button @click="dialogVisible = false">取消</el-button>
    <el-button type="primary" @click="submit" :loading="submitting">保存</el-button>
  </template>
</el-dialog>
```

**校验规则**：
- `index_code`: `required`, `pattern: /^\d{6}$/`, 错误提示 "请输入 6 位数字代码"
- `market`: `required`, 错误提示 "请选择市场"
- `index_name`: `required`, `min: 2`, 错误提示 "请输入 2-32 字名称"
- `index_type`: `required`
- `enabled`: 不校验，boolean 兜底

## 7. 交互规范

### 7.1 启停（行内 el-switch）

```js
function toggleEnabled(row, v) {
  const prev = row.enabled
  row.enabled = v  // 乐观更新
  indexBasicApi.toggle(row.index_code, v)
    .then(() => ElMessage.success(v === 1 ? '已启用' : '已停用'))
    .catch(err => {
      row.enabled = prev  // 回滚
      ElMessage.error(err.message || '操作失败')
    })
}
```

**注意**：与后端的最终一致**不**靠轮询；用户能看到的就两个反馈——开关瞬时翻转 + toast 提示。失败回滚到原值。

### 7.2 新增 / 编辑

- 提交时 `formRef.value.validate()` 通过 → 调 `create` 或 `update` API
- 成功 → 关闭 dialog、刷新列表、ElMessage.success
- 失败 → 表单内联错误 + ElMessage.error
- 编辑时 `index_code` 和 `market` 字段 disabled（主键语义）

### 7.3 删除

```js
ElMessageBox.confirm(
  `确定删除指数「${row.index_name}」吗？相关历史行情保留，仅从列表隐藏。`,
  '删除确认',
  { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
)
  .then(() => indexBasicApi.remove(row.index_code))
  .then(() => { ElMessage.success('已删除'); fetchList(); })
  .catch(err => err !== 'cancel' && ElMessage.error(err.message || '删除失败'))
```

**话术要点**（"写给人"）：
- 强调「仅从列表隐藏」+「历史保留」—— 消除用户对「会不会丢数据」的疑虑
- 「warning」而非「error」色——软删是温和操作
- 取消按钮用「取消」而非「关闭」——明确意图

### 7.4 搜索 / 过滤

- 搜索按钮 / 重置按钮：与 FundManage.vue 一致
- 「显示已停用」开关：默认关（用户来这页**首先**是看「在跑哪些」）
- 搜索时 `currentPage = 1`

### 7.5 空状态

`list.length === 0` 时 el-table 显示内置空态（Element Plus 默认「暂无数据」），**不**做插画 / 引导文案——本页用户是技术型，过度引导反而打扰。

## 8. 路由 / 菜单 / 图标（与 Layout 联动）

### 8.1 router/index.js

```js
{
  path: 'index',
  component: () => import('@/views/IndexInfo.vue'),  // 占位父组件
  meta: { title: '指数', icon: 'DataAnalysis', sort: 45, isParent: true },
  children: [
    { path: 'info',     component: () => import('@/views/IndexInfo.vue'),     meta: { title: '指数信息', sort: 46 } },
    { path: 'basic',    component: () => import('@/views/IndexBasic.vue'),    meta: { title: '指数基础', sort: 47 } },  // 新
    { path: 'analysis', component: () => import('@/views/IndexAnalysis.vue'), meta: { title: '指数分析', sort: 48 } },  // 47 → 48
  ]
},
```

**注意**：项目「指数」父路由是 `isParent` 折叠菜单（参 Layout.vue:88-106 探索结果）。新页作为子项，**不**开新顶级菜单。

### 8.2 Layout.vue 图标

第 75 行 `import` 列表追加：`Files`—— 选 **`Files`**，理由：「基础」= 元信息列表，Files 隐喻"目录条目"，比 Collection（"集合"）更直接对应表/行概念。

第 116-134 行 `iconMap` 增加：

```js
'/index/basic': Files,
```

## 9. 顺手改动：`IndexInfo.vue:64` 兜底

```diff
- <el-table-column prop="index_name" label="指数名称" width="120" />
+ <el-table-column label="指数名称" width="120">
+   <template #default="{ row }">
+     {{ row.index_name || '—' }}
+   </template>
+ </el-table-column>
```

**为什么不在本页写**：`IndexInfo.vue` 是「指数行情」只读页，本设计文档**只**管 `IndexBasic.vue`。这条改动在 PRD §AC-7 单独标了，diff 在此文档**仅作记录**，不在本页实现 scope 内。

## 10. 一致性检查清单

实现完后逐条对：

- [ ] 搜索/功能/数据/分页四区与 `FundManage.vue` 视觉一致（无边框无阴影 card、20px 间距、1px 分隔线、底色 `#fafafa`）
- [ ] 「市场」列用 el-tag，sh→primary 蓝、sz→warning 金
- [ ] 「启用」列用 6px 圆点（不靠 el-tag、不靠 el-switch）
- [ ] 操作列：el-switch + 编辑 + 删除，三件套顺序固定
- [ ] 删除确认弹窗话术包含「历史保留」字样
- [ ] el-switch 即时提交 + 失败回滚，不弹额外 dialog
- [ ] 编辑时 `index_code` / `market` disabled
- [ ] 顶栏「显示已停用」默认关
- [ ] 字体：数字代码列 monospace，中文系统 sans
- [ ] 路由 sort：IndexInfo=46、IndexBasic=47、IndexAnalysis=48
- [ ] Layout.vue iconMap `/index/basic` → `Files`
- [ ] `IndexInfo.vue:64` `index_name` 顺手加 `row.index_name || '—'` 兜底
- [ ] `npm run build` 通过
