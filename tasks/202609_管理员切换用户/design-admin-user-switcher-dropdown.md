# Design — admin 切换用户视角：下拉搜索框

**Feature slug**: `admin-user-switcher-dropdown`
**作者**: Claude（/frontend-design 流程）
**日期**: 2026-08-09
**配套 PRD**: `tasks/prd-admin-user-switcher-dropdown.md`

---

## 0. Subject（这一步先定 subject，避免「通用 admin 下拉」陷阱）

**Subject**: admin 顶栏的「快速换镜工具」——不是「用户浏览面板」。区别：
- 工具：用户已经知道目标是谁，只差一个跳转；浮层是 lookup，不是 browse
- 面板：用户想随便看看 / 翻一翻；浮层是数据浏览

**Audience**: 个人基金系统的 admin（即你），高频切换 context，每次只切一个。**会一周切几十次**，而不是浏览一遍就走。意味着：
- 弹出 0 思考成本（自动 focus 已是底线）
- 选 0 思考成本（候选 = 已知信息 + 视觉锚点清晰）
- 关闭 0 思考成本（按 Esc / 点外面即关 + 输入框不留残余）

**Page's single job**: 替 admin 省掉「去 /system/users 查 user_id → 抄 → 顶栏点 → 手输」这 4 步中的 3 步。

> 这个 subject 决定整个 design 是「**安静 + 高效**」的，不是「**漂亮 + 智能**」的。所有「AI 默认炫技」一律不上（无 avatar、无在线状态、无"最近切换"置顶、无智能推荐排序、无快捷键面板）。

---

## 1. Design token

### 1.1 色彩（全部沿用现有 Element Plus 主题，零新增）

| Token | Hex | 用途 | 来源 |
|-------|-----|------|------|
| `surface` | `#ffffff` | 浮层背景 | EP `--el-bg-color` |
| `border` | `#e4e7ed` | 浮层外框 + 输入框与列表之间的 hairline | EP `--el-border-color-lighter` |
| `text-key` | `#303133` | username（key 字段）| EP `--el-text-color-primary` |
| `text-desc` | `#909399` | display_name（描述字段）| EP `--el-text-color-secondary` |
| `text-sep` | `#c0c4cc` | 分隔符 `-` | EP `--el-text-color-placeholder` |
| `surface-hover` | `#f5f7fa` | 候选项 hover / 选中 | EP `--el-fill-color-light` |
| `focus-ring` | `#409eff` | 输入框 focus 边框 | EP `--el-color-primary`（不覆盖）|
| `topbar-bg` | `#545c64` | 顶栏深灰（参考上下文，浮层内不出现）| 现有 |
| `topbar-warn` | `#ffd04b` | admin 标签的 warning 黄（参考上下文）| 现有 |

> **与现有顶栏配色冲突判断**：浮层自身是白底 + EP 默认色，与顶栏深灰形成「浮起来」的对比。admin 标签的金色（`#ffd04b`）只出现在顶栏 chip 上，浮层内不出现——**避免色彩竞争**。

### 1.2 字体

| 角色 | size | weight | letter-spacing | 备注 |
|------|------|--------|----------------|------|
| username | 14px | **500** | 0 | 比 display_name 重一档——见 §6 「the risk」 |
| display_name | 14px | 400 | 0 | 次要信息 |
| 分隔符 `-` | 14px | 400 | 0 | 与 display_name 同色，但色相更弱 |
| 加载文字「正在加载用户…」 | 13px | 400 | 0 | 略小一档，明确是「状态」不是「数据」 |
| 空态文字「暂无其他用户可切换」 | 13px | 400 | 0 | 同上 |

> 字体 family 全部用 EP 默认系统字体栈（`-apple-system, BlinkMacSystemFont, 'Segoe UI', ...`）。**不引新字体、不引 monospace**（username 是人类输入串，不是 ID）。

### 1.3 间距 / 圆角 / 阴影

| Token | Value | 备注 |
|-------|-------|------|
| 浮层宽度 | `320px` | 固定（FR-16） |
| 浮层圆角 | `4px` | EP popover 默认 |
| 浮层阴影 | `0 12px 32px 4px rgba(0, 0, 0, 0.04), 0 8px 20px rgba(0, 0, 0, 0.08)` | EP popover 默认阴影（直接继承，不自定义）|
| 浮层 z-index | 9999 | EP popover 默认 |
| 浮层到触发器距离 | `top: 8px`（placement=bottom-end）| EP 默认 6px，**调大 2px**给顶栏分隔线 1px 留呼吸感 |
| 输入框高度 | `36px` | EP `el-autocomplete` 默认 |
| 候选项高度 | `36px` | EP 标准下拉项高 |
| 候选项水平 padding | `12px` | 视觉对齐输入框文字 |
| 候选项垂直 padding | `0`（由 36px 高度撑开）| 与 EP 一致 |
| 输入框 ↔ 列表 hairline | `1px solid #e4e7ed` | 见 §3.2 |

---

## 2. 布局（ASCII wireframe）

### 2.1 触发器：顶栏 admin chip

```
   ┌─────────────────────────────────────────────────────┐
   │  正在以 XXX 视角操作         张三 [管理员] [▾]      │ ← 触发器（el-dropdown 现有）
   └─────────────────────────────────────────────────────┘
                                                  │
                                                  ▼  placement: bottom-end, offset-y: 8px
```

- 触发器：现有 `<el-dropdown>` chip（第 61-78 行），**不动**
- placement: `bottom-end` —— 浮层右边缘与 chip 右边缘对齐，浮层向左下生长
  - 原因：chip 已在顶栏右端，`bottom-start` 会让浮层向左覆盖大量空白，浪费 320px 宽度
  - 在 ≤768px 视口下改为 `bottom`（见 §5.2）
- 触发器与浮层无视觉连接线（无箭头 / 无 connector）

### 2.2 浮层内部

```
                  ┌──────────────────────────┐  ← 320px 宽
                  │ [ 🔍 搜索目标用户      ] │  ← 输入框（autofocus）
                  ├──────────────────────────┤  ← 1px hairline
                  │ zhangsan  - 张三         │  ← username (500)  +  "-"  +  display_name (400)
                  │ lily     - 李莉          │  ← hover/selected
                  │ wangwu   -               │  ← display_name 为空
                  │ zhaoliu  - 赵六           │
                  │ ...                      │  ← ≤ 10 行
                  └──────────────────────────┘
```

- 输入框与列表之间是 `1px solid #e4e7ed` 横线（hairline）
  - **不加分隔线上的渐变 / 阴影 / inset**——是结构化分界，不是装饰

### 2.3 候选行内部排版

| 字段 | DOM | CSS |
|------|-----|-----|
| username | `<span class="user-key">` | `font-weight: 500; color: #303133;` |
| 分隔符 | `<span class="user-sep">` | `color: #c0c4cc; padding: 0 6px;` |
| display_name | `<span class="user-desc">` | `color: #909399;` |

- **不用真实空格字面量**，全部用 CSS `padding-inline: 6px` —— 避免 DOM 里 `zhangsan - 张三` 的空字符串在屏幕阅读器里被读成 "zhangsan dash 张三"，应该是 "zhangsan 短横线 张三"
- 候选项垂直居中：`line-height: 36px; display: flex; align-items: center;`
- 文本溢出：username 长于 240px 时 `text-overflow: ellipsis; overflow: hidden;`（display_name 也会被截断，但本项目 display_name 通常 < 20 字）
- 候选项 hover/selected：`background: #f5f7fa;`（EP hover 浅灰）

---

## 3. 状态设计

### 3.1 加载态

```
┌──────────────────────────┐
│ [ 🔍 正在加载用户    ]  │  ← 输入框右侧显示 EP 圆形 spinner
├──────────────────────────┤
│    正在加载用户…         │  ← 单行 13px secondary 文字，padding 0 12px
└──────────────────────────┘
```

- 输入框内右侧显示 `<el-icon class="is-loading"><Loading /></el-icon>`（EP spinner），与输入文字 `padding-right: 28px` 隔开
- 输入框本身可键入（不锁），但 `fetch-suggestions` 不响应
- 加载完成 → 列表替换 spinner 文字；spinner 消失
- **拉取时**用户键入 = 不响应（EP autocomplete 的 loading 属性会自动处理）

### 3.2 空列表（admin 是唯一用户）

```
┌──────────────────────────┐
│ [ 🔍 搜索目标用户      ] │
├──────────────────────────┤
│   暂无其他用户可切换     │  ← 13px secondary，padding 0 12px
└──────────────────────────┘
```

- 单行 muted 文字（13px `#909399`），垂直 padding 12px
- 不可选中、不可点击
- **不显示** 「去用户管理页新建」 链接（避免引入跳转，避免 admin 被引导去创建用户而不是切视角）

### 3.3 边界：display_name 为空

| DB 值 | 显示 |
|-------|------|
| `'测试用户'` | `lily - 测试用户` |
| `''` | `lily -`（保留 username + 短横线） |
| `NULL` | 同上（前端判 `!user.display_name` 兜底） |

- 短横线**不删除**——保留作为「这里本应有第二段」 的 ghost，避免 admin 怀疑「这是不是漏显示了」
- 短横线色用 `text-sep #c0c4cc`，与 display_name 区分

### 3.4 接口失败

- ElMessage.error 出现在屏幕底部（toast 位置），不阻塞浮层
- 但**弹层不显示**（FR-12：失败时不弹 popover）——弹了也白弹，没数据
- 用户操作路径：失败 → 弹层未出现 → admin 再次点击「切换用户视角」可重试
- 错误文案：「加载用户列表失败」

### 3.5 选中项 == admin 自己

- 理论上**不会发生**（FR-6 默认列表已排除 admin）
- 但万一（接口拉到 admin 自己）→ ElMessage.warning('不能切换到自身') + 弹层保持打开（让 admin 看到提示后继续选）
- 文案不用「请选择其他用户」（多余）——只说「不能切换到自身」就够

### 3.6 关闭后清理（FR-14）

- 浮层关闭 → `autocompleteQuery.value = ''` → 下次打开是干净状态
- 浮层关闭 → `loadingUsers.value = false`（防止上次的 spinner 残留）
- 浮层关闭 → `userList.value = []`（防止数据残留到下次会话）

---

## 4. 与现有页面的视觉一致性

### 4.1 与 Login.vue 的「立即注册」对比

| 维度 | Login.vue 立即注册 | 本浮层 |
|------|-------------------|--------|
| 入口 | 登录按钮下文本链接 | 顶栏 admin chip 下拉菜单项 |
| 主色 | 蓝（el-link primary）| 白底黑字 + 灰次要 |
| 关系 | 入口 | 工具 |

- **不**沿用蓝色（蓝是「链接」语义，本浮层是「表单」语义）
- **不**沿用 44×44 触控热区（这是桌面端密集操作，移动端不常用 admin 切换）

### 4.2 与现有 el-dropdown 风格

- 现有 el-dropdown 菜单是深灰底白字（顶栏 #545c64）
- 本浮层是白底黑字（EP popover 默认）——**形成对比**
  - 深灰 → 白：像「从顶栏拉出一张白纸」
  - 强化「这是临时弹层、不是顶栏的一部分」的认知

### 4.3 与 Layout.vue 已有的 `<el-alert>` 警告条对比

- 警告条「正在以 XXX 视角操作」：黄色 warning、靠顶栏左侧
- 本浮层：白底、靠顶栏右下方
- **不重叠**：警告条 padding 4px 10px 在顶栏内，浮层在顶栏下方
- **不冲突**：颜色不同（黄 vs 白）+ 位置不同（左 vs 右）

---

## 5. 响应式

### 5.1 桌面端（> 768px）

- placement: `bottom-end`
- 宽度 320px
- 浮层右边缘对齐 chip 右边缘

### 5.2 移动端（≤ 768px）

- placement: 改 `bottom`（让浮层居中，避免贴近屏幕右缘）
- 宽度**仍** 320px（不缩放——避免「假自适应」带来的视觉割裂）
- viewport 360px 时浮层左右各留 20px 边距，仍可点击
- 浮层外层设 `max-width: calc(100vw - 24px)` 兜底（极端窄屏如 320px 视口，浮层会被裁到只剩 16px 边距）
- 触控点击：候选项 36px 高 = 触控热区达标（iOS HIG 44px 略低，但候选行 + 间距总和接近）

### 5.3 平板（769px - 1024px）

- 同桌面端（无特殊处理）

---

## 6. The risk（故意的视觉决策）

**风险点**: username 字号与 display_name 相同（14px），但 weight 不同（500 vs 400）。

**为什么是风险**: 同行内两种字重 = 不对称。在 Material Design / Apple HIG / IBM Carbon 等主流 design system 里，**默认是同行同字重**，用色彩 / 间距 / 位置区分主次。**强行两种字重 = 视觉上"哪里怪怪的"**。

**为什么仍要做**: 浮层每行信息密度低（只有两段：username + display_name），同字重会让 admin 眼球左右跑两趟才确定哪个是「键」。半粗 username 是**视觉锚点**：admin 看到粗体就知道「这是键」。这与终端 / 命令行 UI（命令用粗体，参数用常规）一致——是个人基金系统的「admin 视角」语义。

**回滚条件**: 如果一周后 admin 觉得"怪怪的"或"看错了" → 改回统一 400 + 用色彩区分（username `#303133`、display_name `#909399` 已够区分）。

---

## 7. 自我审查：cut 掉的东西

每一条都问了一遍"这真的服务 brief 吗"：

| 候选项 | 是否加 | 理由 |
|--------|--------|------|
| avatar / 头像 | ❌ | admin 已知用户，avatar 0 信息量 |
| 角色 tag（管理员/用户）| ❌ | 默认列表已排除 admin；剩余都是普通用户，tag 100% "用户" = 噪音 |
| 在线状态绿点 | ❌ | 0 信息量，admin 切的是「能操作的人」不是「在线的人」 |
| 最后登录时间 | ❌ | 与"快速换镜"无关 |
| 已置顶 / 常用切换 | ❌ | AI 默认炫技；admin 切换模式不可预测 |
| 远程搜索 / debounce | ❌ | 10 条本地过滤 0 性能问题 |
| 排序 chip（按名字/按注册时间）| ❌ | 单一排序：按 id DESC = 按注册时间 DESC = 「最新的 10 个」已是用户原话 |
| 快捷键（Ctrl+K 唤起）| ❌ | 引入键盘事件冲突风险；admin 鼠标 1 次点击已经够快 |
| 「新建用户」入口 | ❌ | 超出范围（NG-4）|
| 浮层加载时的占位骨架 | ❌ | 单行「正在加载用户…」文字已够；骨架反而显得「重」|
| 选中后的二次确认 | ❌ | admin 主动切，知道后果 |
| 浮层动画 fade-in | ❌ | EP popover 默认无动画；加 transition 反而拖慢 admin 节奏 |
| 输入框 placeholder "搜索目标用户" | ✅ | 有用（autofocus 之前是空状态时显示）|

---

## 8. 文案

| 场景 | 文案 | 备注 |
|------|------|------|
| placeholder | "搜索目标用户" | autofocus 后即消失 |
| loading | "正在加载用户…" | 加「…」表示进行中 |
| empty | "暂无其他用户可切换" | 明确"可切换"语义，不是"没有用户" |
| error toast | "加载用户列表失败" | 简短动作失败；不说"请重试"（admin 自然会重试）|
| success toast | "已切换到 {display_name\|username} 视角" | 沿用现有（不变）|
| warning（切到自身）| "不能切换到自身" | 沿用现有（不变）|

---

## 9. 实现层约定（给 /implement-tasks 落 task 用）

### 9.0 实现踩坑记录（2026-08-09 Phase 6 验证发现）

**问题 1**：第一版 el-popover 嵌套在 el-dropdown-menu 内，el-dropdown-item 作 reference slot。点击时 el-dropdown 自动关闭（v-show=false 把整个 menu 隐藏，包括 reference）→ el-popover 拿到 reference 的 `getBoundingClientRect()` 是 0×0 → popper 定位失败 / 不显示。

**修复 1**：el-popover 移到 el-dropdown 外面，用 `virtual-ref` 指向 adminChipRef（始终可见的 admin chip span），`trigger="manual"` + `virtual-triggering`，由 `handleAdminCommand('switch-user')` 设 `switcherVisible.value = true` 打开。`el-dropdown-item` 恢复 `command="switch-user"`。focus 改用 `setTimeout(50)` 兜底 teleported popper 挂载时序。

**问题 2**：第二版用户反馈「弹框应在页面中间弹出」（2026-08-09）。el-popover 是 popper，定位在触发器附近，无法居中。改用 el-dialog 居中弹窗：
- 替换 el-popover 为 el-dialog，width 480px，align-center
- 替换 el-autocomplete 为 el-input（搜索）+ 常驻 ul 候选列表（点击/回车选中）
- 加 `filteredUsers` computed 实现本地过滤；移除 `fetchSuggestions` 和 `adminChipRef`
- **el-dialog 必须加 `v-if="isAdmin()"`**：否则夹在 `<el-dropdown v-if="isAdmin()">` 和 `<template v-else>` 中间破坏 v-else 链，编译报 `Cannot read properties of undefined (reading 'type')`

### 9.1 文件改动

- **改 1 个文件**: `frontend/src/components/Layout.vue`
  - `<template>`: `<el-dropdown>` 的 chip 加 `ref="adminChipRef"`；`<el-dropdown-item>` 恢复 `command="switch-user"`；新增 `<el-popover>` 作 el-dropdown 的兄弟节点
  - `<script setup>`: 新增 6 个 ref（含 `adminChipRef`）+ 1 个 computed + 4 个函数 + 1 个 watch
  - `<style scoped>`: 追加约 30 行 CSS（候选项 + 加载态 + 空态 + 移动端）

### 9.2 关键代码骨架（修正后）

```vue
<!-- el-dropdown 的 chip span 加 ref="adminChipRef"，作 popover 的 virtual-ref -->
<el-dropdown v-if="isAdmin()" trigger="click" @command="handleAdminCommand">
  <span ref="adminChipRef" style="...">
    {{ auth.user.display_name || auth.user.username }}
    <el-tag ...>管理员</el-tag>
  </span>
  <template #dropdown>
    <el-dropdown-menu>
      <el-dropdown-item command="profile">个人设置</el-dropdown-item>
      <el-dropdown-item v-if="auth.impersonate" command="stop-impersonate" divided>退出视角切换</el-dropdown-item>
      <el-dropdown-item v-else command="switch-user" divided>切换用户视角</el-dropdown-item>
      <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
    </el-dropdown-menu>
  </template>
</el-dropdown>

<!-- el-popover 在 el-dropdown 外面，virtual-ref 指向 adminChipRef -->
<el-popover
  v-if="isAdmin()"
  v-model:visible="switcherVisible"
  :width="320"
  placement="bottom-end"
  :show-arrow="false"
  virtual-triggering
  :virtual-ref="adminChipRef"
  trigger="manual"
  popper-class="switcher-popover"
  @close="handleSwitcherClose"
>
  <el-autocomplete
    v-model="autocompleteQuery"
    :fetch-suggestions="fetchSuggestions"
    :trigger-on-focus="true"
    :loading="loadingUsers"
    placeholder="搜索目标用户"
    aria-label="搜索目标用户"
    ref="autocompleteRef"
    clearable
    @select="handleUserSelect"
  >
    <template #prefix>
      <el-icon><Search /></el-icon>
    </template>
    <template #default="{ item }">
      <span class="user-key">{{ item.user.username }}</span>
      <span class="user-sep">-</span>
      <span class="user-desc">{{ item.user.display_name || '' }}</span>
    </template>
  </el-autocomplete>
  <div v-if="loadingUsers" class="switcher-loading" aria-live="polite">正在加载用户…</div>
  <div v-else-if="!recentUsers.length" class="switcher-empty">暂无其他用户可切换</div>
</el-popover>
```

### 9.3 状态机

| State | 触发 | 表现 |
|-------|------|------|
| `closed` | 浮层关闭 | `switcherVisible=false`，`autocompleteQuery=''`，`userList=[]` |
| `loading` | `switcherVisible=true` 且 `loadingUsers=true` | 输入框 + 「正在加载用户…」 |
| `ready-with-data` | `loadingUsers=false` 且 `userList.length>0` 且 `recentUsers.length>0` | 输入框 + 候选列表 |
| `ready-empty` | `loadingUsers=false` 且 `recentUsers.length===0` | 输入框 + 「暂无其他用户可切换」 |
| `ready-with-query` | `ready-with-data` + `autocompleteQuery!=''` | 候选列表 = 过滤后的子集 |

### 9.4 关键函数

```js
// 拉取用户列表（每次 popover 打开都重新拉，不缓存）
const fetchUsers = async () => {
  loadingUsers.value = true
  try {
    const resp = await userApi.getUsers({ page: 1, page_size: 1000 })
    userList.value = resp.data || []
  } catch (e) {
    ElMessage.error('加载用户列表失败')
    switcherVisible.value = false
  } finally {
    loadingUsers.value = false
  }
}

// 取前 10（排除 admin 自己）
const recentUsers = computed(() => {
  const adminId = auth.realUser?.id
  return [...userList.value]
    .filter(u => u.id !== adminId)
    .sort((a, b) => b.id - a.id)
    .slice(0, 10)
})

// 候选格式化：username - display_name
const formatUser = (u) => `${u.username} - ${u.display_name || ''}`

// 候选过滤
const fetchSuggestions = (queryString, cb) => {
  const q = (queryString || '').toLowerCase()
  const filtered = q
    ? recentUsers.value.filter(u =>
        u.username.toLowerCase().includes(q) ||
        (u.display_name || '').toLowerCase().includes(q)
      )
    : recentUsers.value
  cb(filtered.map(u => ({ value: formatUser(u), user: u })))
}

// 选中后
const handleUserSelect = async (item) => {
  if (!item?.user) return
  switcherVisible.value = false
  const resp = await adminApi.startImpersonate(item.user.id)
  setImpersonate(resp.target, auth.realUser)
  ElMessage.success(`已切换到 ${item.user.display_name || item.user.username} 视角`)
  router.go(0)
}

// 关闭后清理
const handleSwitcherClose = () => {
  autocompleteQuery.value = ''
  userList.value = []
}
```

### 9.5 与现有 Layout.vue 现有逻辑的边界

- **保留**：el-dropdown 整体不动；handleAdminCommand 的 cmd === 'switch-user' 改为只负责打开 popover（不再调 openSwitchUserDialog）
- **保留**：stop-impersonate / logout / profile 三个 cmd 逻辑完全不动
- **移除**：openSwitchUserDialog 整个函数（约 28 行）+ ElMessageBox import（如果整个文件不再用 ElMessageBox）
- **新增**：5 个 ref + 1 个 computed + 4 个函数

---

## 10. 不做什么（来自 PRD §5，复述避免漏）

- ❌ 不改后端 / SQL / router
- ❌ 不改 auth.js / api/index.js
- ❌ 不改 Signup.vue / Login.vue / UserManage.vue / Profile.vue
- ❌ 不加 avatar / 在线状态 / 角色 tag / 快捷键 / 排序 chip
- ❌ 不做远程搜索 / debounce / 分词 / 高亮
- ❌ 不做缓存（每次 popover 打开都重拉）
- ❌ 不加 transition / fade-in / 装饰动画
- ❌ 不动 login-signup-link（另一个 PR）
