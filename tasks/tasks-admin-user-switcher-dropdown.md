# Task List: admin 切换用户视角：下拉搜索框

**Based on PRD**: `tasks/prd-admin-user-switcher-dropdown.md`
**Based on Design**: `tasks/design-admin-user-switcher-dropdown.md`
**生成日期**: 2026-08-09

---

## Relevant Files

### Files to Modify
- `frontend/src/components/Layout.vue` — 替换 `openSwitchUserDialog` 模板 + script + 加 CSS（单文件改动）

### Files to Create
- 无

### Test Files
- 无新增（前端纯 UI 改造 + 已有 `adminApi`/`userApi`；无 vitest/jest 配置；验证走手动 + `npm run build`）

---

## Implementation Tasks

### 1. 改 Layout.vue 模板：触发器 + el-popover 浮层结构
**Effort Estimate**: Small（30 min）

#### Sub-tasks:
- [ ] 1.1 找到第 74 行 `<el-dropdown-item v-else command="switch-user" divided>切换用户视角</el-dropdown-item>`，**保留**这一行（el-dropdown-item 作为 el-popover 触发器 reference slot）
- [ ] 1.2 在第 74 行外层包 `<el-popover>`，属性：`v-model:visible="switcherVisible"` / `:width="320"` / `placement="bottom-end"` / `:show-arrow="false"` / `trigger="click"`
- [ ] 1.3 浮层内部：`<el-autocomplete>` + `v-model="autocompleteQuery"` / `:fetch-suggestions="fetchSuggestions"` / `:trigger-on-focus="true"` / `:loading="loadingUsers"` / `placeholder="搜索目标用户"` / `aria-label="搜索目标用户"` / `ref="autocompleteRef"` / `@select="handleUserSelect"` / `clearable`
- [ ] 1.4 `<template #prefix>` 加 `<el-icon><Search /></el-icon>`
- [ ] 1.5 `<el-autocomplete>` 下用 `<template #default>` 包裹三个分支（v-if / v-else-if 切换）：
  - 加载中：`switcher-loading` div
  - 空态：`switcher-empty` div
  - 列表：通过 `recentUsers` 渲染（实际由 el-autocomplete 自动渲染下拉项）
- [ ] 1.6 **改写**：el-autocomplete 的候选列表**由其内部下拉自动渲染**，需要自定义每项的 DOM 结构 → 用 `<template #default="{ item }">` slot 包裹 `user-key` / `user-sep` / `user-desc` 三个 span
- [ ] 1.7 浮层内部模板最终结构（伪代码）：
  ```vue
  <el-popover v-model:visible="switcherVisible" :width="320" placement="bottom-end" :show-arrow="false" trigger="click" @close="handleSwitcherClose" popper-class="switcher-popover">
    <template #reference>
      <el-dropdown-item v-if="!auth.impersonate" command="switch-user" divided>切换用户视角</el-dropdown-item>
    </template>
    <el-autocomplete v-model="autocompleteQuery" :fetch-suggestions="fetchSuggestions" :trigger-on-focus="true" :loading="loadingUsers" placeholder="搜索目标用户" aria-label="搜索目标用户" ref="autocompleteRef" @select="handleUserSelect" clearable>
      <template #prefix><el-icon><Search /></el-icon></template>
      <template #default="{ item }">
        <span class="user-key">{{ item.user.username }}</span>
        <span class="user-sep">-</span>
        <span class="user-desc">{{ item.user.display_name || '' }}</span>
      </template>
    </el-autocomplete>
    <div v-if="loadingUsers" class="switcher-loading">正在加载用户…</div>
    <div v-else-if="!recentUsers.length" class="switcher-empty">暂无其他用户可切换</div>
  </el-popover>
  ```
- [ ] 1.8 第 107 行 icons import 行追加 `Search`：在已有 `... } from '@element-plus/icons-vue'` 列表中加入 `Search`
- [ ] 1.9 **特别检查**：el-dropdown-item 不能再有 `@command="handleAdminCommand"` 自动传递 command（嵌套在 el-popover 内可能需要把 `@command` 移到 el-dropdown 上，或在 el-popover 显式监听）。如遇问题，el-dropdown 改为 `trigger="manual"` + 自己控制开合

### 2. 改 Layout.vue script：移除旧实现 + 加 5 ref + 1 computed + 4 函数
**Effort Estimate**: Small（30 min）

#### Sub-tasks:
- [ ] 2.1 移除第 210-237 行整个 `openSwitchUserDialog` 函数（约 28 行）
- [ ] 2.2 第 106 行 `import { ElMessage, ElMessageBox } from 'element-plus'` 改为 `import { ElMessage } from 'element-plus'`（如整个文件不再用 ElMessageBox）
- [ ] 2.3 第 104 行 `import { computed, h }` 追加 `ref`（最终 `import { computed, h, ref }`）
- [ ] 2.4 在第 113 行 `const router = useRouter()` 后、菜单项定义前，新增 ref 块：
  ```js
  // === 切换用户视角下拉 ===
  const switcherVisible = ref(false)
  const autocompleteQuery = ref('')
  const loadingUsers = ref(false)
  const userList = ref([])
  const autocompleteRef = ref(null)
  ```
- [ ] 2.5 新增 computed（在 menuItems 之后）：
  ```js
  const recentUsers = computed(() => {
    const adminId = auth.realUser?.id
    return [...userList.value]
      .filter(u => u.id !== adminId)
      .sort((a, b) => b.id - a.id)
      .slice(0, 10)
  })
  ```
- [ ] 2.6 新增 function `fetchUsers`（在 stopImpersonate 函数之后、openSwitchUserDialog 原位置）：
  ```js
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
  ```
- [ ] 2.7 新增 function `fetchSuggestions(queryString, cb)`（本地过滤）：
  ```js
  const fetchSuggestions = (queryString, cb) => {
    const q = (queryString || '').toLowerCase().trim()
    const list = q
      ? recentUsers.value.filter(u =>
          u.username.toLowerCase().includes(q) ||
          (u.display_name || '').toLowerCase().includes(q)
        )
      : recentUsers.value
    cb(list.map(u => ({ value: `${u.username}|${u.id}`, user: u })))
  }
  ```
  > **注意**：`el-autocomplete` 的 `value` 字段是输入框回填用的标识符，必须唯一。用 `username|id` 防重复 username 冲突
- [ ] 2.8 新增 function `handleUserSelect(item)`（调用 startImpersonate）：
  ```js
  const handleUserSelect = async (item) => {
    if (!item?.user) return
    if (item.user.id === auth.realUser?.id) {
      ElMessage.warning('不能切换到自身')
      return
    }
    switcherVisible.value = false
    try {
      const resp = await adminApi.startImpersonate(item.user.id)
      const target = resp.target || item.user
      setImpersonate(target, auth.realUser)
      ElMessage.success(`已切换到 ${target.display_name || target.username} 视角`)
      router.go(0)
    } catch (e) {
      // 401 已由响应拦截器处理；其他错误吞掉
    }
  }
  ```
- [ ] 2.9 新增 function `handleSwitcherClose`（关闭后清理）：
  ```js
  const handleSwitcherClose = () => {
    autocompleteQuery.value = ''
    loadingUsers.value = false
    userList.value = []
  }
  ```
- [ ] 2.10 改 `handleAdminCommand`（第 186-196 行）：`cmd === 'switch-user'` 分支改为：
  ```js
  } else if (cmd === 'switch-user') {
    switcherVisible.value = true
    fetchUsers()
  }
  ```
- [ ] 2.11 新增 watch：`switcherVisible` 从 false 变 true 时，`nextTick` 内 focus 输入框
  ```js
  import { watch, nextTick } from 'vue'
  watch(switcherVisible, async (val) => {
    if (val) {
      await nextTick()
      autocompleteRef.value?.focus?.()
    }
  })
  ```
- [ ] 2.12 检查：`userApi` / `adminApi` 已在第 108 行 import 过，无需新增 import

### 3. 配套 CSS：候选项 + 状态 + 移动端
**Effort Estimate**: Small（25 min）

#### Sub-tasks:
- [ ] 3.1 在 `<style scoped>` 段尾（line 248 之后）追加新样式块：
  ```css
  /* === 切换用户视角下拉 === */
  .user-key {
    font-weight: 500;
    color: #303133;
  }
  .user-sep {
    color: #c0c4cc;
    padding: 0 6px;
  }
  .user-desc {
    color: #909399;
  }
  ```
- [ ] 3.2 加输入框↔列表 hairline（popover 内 el-autocomplete 底部 1px 线）：
  ```css
  .switcher-popover :deep(.el-autocomplete) {
    border-bottom: 1px solid #e4e7ed;
  }
  ```
- [ ] 3.3 加 loading 文字样式：
  ```css
  .switcher-loading {
    height: 36px;
    line-height: 36px;
    padding: 0 12px;
    font-size: 13px;
    color: #909399;
  }
  ```
- [ ] 3.4 加 empty 文字样式：
  ```css
  .switcher-empty {
    padding: 12px;
    font-size: 13px;
    color: #909399;
    text-align: center;
  }
  ```
- [ ] 3.5 加 popover 外层微调（避免内边距过小）：
  ```css
  .switcher-popover {
    padding: 0 !important;
  }
  .switcher-popover :deep(.el-popper__arrow) {
    display: none;
  }
  ```
- [ ] 3.6 加移动端兜底（≤768px 浮层不溢出）：
  ```css
  @media (max-width: 768px) {
    .switcher-popover {
      max-width: calc(100vw - 24px) !important;
    }
  }
  ```
- [ ] 3.7 **不**加 hover 动画、focus 动画、过渡——沿用 EP 默认

### 4. 浏览器手动验证（PRD 16 个 FR + 9 个 A11Y + 5 个边界）
**Effort Estimate**: Small（25 min）

#### Sub-tasks:
- [ ] 4.1 **FR-1**：登录 admin 账户，访问任意页（如 /dashboard），顶栏 admin chip 下拉看到「切换用户视角」菜单项
- [ ] 4.2 **FR-2**：点击「切换用户视角」→ 弹出 320px 浮层（不是 prompt 弹窗）
- [ ] 4.3 **FR-3**：浮层内看到 el-autocomplete 输入框 + 候选列表
- [ ] 4.4 **FR-4**：浮层打开时输入框自动获得焦点（光标闪烁）
- [ ] 4.5 **FR-5**：观察拉取时（DevTools Network 限速到 Slow 3G）→ 输入框右侧显示 spinner + 下方「正在加载用户…」
- [ ] 4.6 **FR-6**：默认列表展示 10 个非 admin 用户
- [ ] 4.7 **FR-7**：候选项显示「username - display_name」（如 `testuser01 - 测试用户`），有 display_name 的用户正常显示
- [ ] 4.8 **FR-7 边界**：找一个 display_name 为空的用户，验证显示 `username -`（保留短横线）
- [ ] 4.9 **FR-8**：键入 `li` → 列表过滤到 username 或 display_name 含 `li` 的项
- [ ] 4.10 **FR-9**：清空输入框 → 列表恢复 10 个
- [ ] 4.11 **FR-10**：鼠标点击某项 → 弹层关闭 + 调 startImpersonate + ElMessage.success
- [ ] 4.12 **FR-11 边界**：手动把 admin 自己加到 `userList`（DevTools Vue 改状态）→ 选中 → 看到「不能切换到自身」warning
- [ ] 4.13 **FR-12**：DevTools Network 拦截 /api/users 返回 500 → 点击「切换用户视角」→ ElMessage.error「加载用户列表失败」+ 浮层未出现
- [ ] 4.14 **FR-13**：选中后 `router.go(0)` 刷新整个 SPA + 顶栏「正在以 XXX 视角操作」警告条正常出现 + 「切换用户视角」菜单项变为「退出视角切换」
- [ ] 4.15 **FR-14**：Esc 关闭弹层 → 重新打开 → 输入框是空的（无上次残留）
- [ ] 4.16 **FR-15**：点击「退出视角切换」→ 行为完全不变（沿用 stopImpersonate + clearImpersonate + router.go(0)）
- [ ] 4.17 **FR-16**：DevTools 切到 375×667 视口 → 点击「切换用户视角」→ 浮层 320px 居中弹出（placement=bottom），左右各留 ~20px 边距
- [ ] 4.18 **A11Y-1**：DevTools Elements 检查 el-popover 节点的 `role="dialog"`
- [ ] 4.19 **A11Y-2**：DevTools 检查 el-autocomplete 节点的 `role="combobox"`
- [ ] 4.20 **A11Y-3**：DevTools 检查 el-autocomplete 节点的 `aria-label="搜索目标用户"`
- [ ] 4.21 **A11Y-4**：弹层打开时 `document.activeElement` 是输入框
- [ ] 4.22 **A11Y-5**：键盘 ↑/↓ 在候选列表切换，Enter 触发选中，Esc 关闭弹层
- [ ] 4.23 **A11Y-6**：用 Chrome DevTools Color Picker 检查 username/display_name 对比度 ≥ 4.5:1
- [ ] 4.24 **A11Y-7**：loading 文字节点有 `aria-live="polite"`（手动加）
- [ ] 4.25 **边界：唯一用户**：用 SQL 软删所有非 admin 用户 → 重新打开浮层 → 显示「暂无其他用户可切换」+ 输入框可键入但不出候选
- [ ] 4.26 **边界：失败重试**：在断网状态下点击「切换用户视角」2 次 → 2 次都 toast error，可重试

### 5. 前端构建门禁
**Effort Estimate**: Small（10 min）

#### Sub-tasks:
- [ ] 5.1 在 `frontend/` 目录执行 `npm run build`，确认无 error（warning 可接受但需 review）
- [ ] 5.2 确认 `frontend/dist/` 目录被更新（`git status` 显示 `frontend/dist/` 下文件 modified）
- [ ] 5.3 确认 `dist/` 体积变化 < 2 KB（对比 `frontend/dist/assets/*.js` / `*.css` 前后大小）
- [ ] 5.4 如 build 报错，按错误信息修复（最可能：template 语法、el-autocomplete slot 未闭合、Search icon 引入）

### 6. 收尾
**Effort Estimate**: Small（10 min）

#### Sub-tasks:
- [ ] 6.1 对照 PRD §4 FR-1~16 全部 ✅
- [ ] 6.2 对照 PRD §9 A11Y-1~9 全部 ✅
- [ ] 6.3 对照 PRD §12 SM-1~6 全部 ✅（SM-1 操作步骤减为 1 步 / SM-2 默认 10 个非 admin / SM-3 过滤 < 50ms / SM-4 警告条正常 / SM-5 dist 体积 < 2KB / SM-6 Console 无 4xx/5xx）
- [ ] 6.4 对照 design §9.5 边界（保留 el-dropdown 不动 / 保留 stop-impersonate 等 3 个 cmd / 移除 ElMessageBox import / 移除 openSwitchUserDialog）
- [ ] 6.5 `git status` 确认变更范围：仅 `frontend/src/components/Layout.vue` + `frontend/dist/`（不含后端 / SQL / 路由 / auth.js / api/index.js / Signup.vue / Login.vue / UserManage.vue / Profile.vue）
- [ ] 6.6 检查 `tasks/prd-admin-user-switcher-dropdown.md` / `tasks/design-admin-user-switcher-dropdown.md` 内容完整
- [ ] 6.7 在本任务清单（`tasks/tasks-admin-user-switcher-dropdown.md`）把全部子任务勾选完
- [ ] 6.8 **不**自动 commit / push，等用户确认；commit 建议文案 `feat(frontend): admin 切换用户视角改为下拉搜索框 + 重新构建 dist/`

---

## Notes

### 实现顺序（TDD 适配）

项目级 TDD 规则要求「测试 → 实现 → 通过」，本改动是**前端纯 UI 改造**，无 vitest / jest 框架，TDD 的"测试"环节按以下方式适配：
- **测试用例** = §4 手动验证 26 项（FR 17 项 + A11Y 7 项 + 边界 2 项）
- **实现** = §1 + §2 + §3（template + script + CSS）
- **通过** = §4 + §5 全部勾选

### 依赖关系

- §1 依赖：无（纯 template 改动）
- §2 依赖：§1（el-autocomplete 的 `:fetch-suggestions` 等回调必须在 template 存在才有意义）
- §3 依赖：§1（CSS 类名 `.user-key` 等必须在 template 中存在才有意义）
- §4 依赖：§1 + §2 + §3 全部完成
- §5 依赖：§1 + §2 + §3（仅当代码改完才有意义构建）
- §6 依赖：§1~§5 全部完成

### 关键决策与风险缓解

| 风险 | 缓解 |
|------|------|
| el-autocomplete 的 `value` 字段是输入框回填用的 | 用 `username\|id` 复合值，避免 username 重复时回填错乱 |
| el-autocomplete 内置下拉 vs 浮层内自定义下拉 | 用 `<template #default="{ item }">` 自定义每项 DOM；el-autocomplete 自动渲染候选下拉 |
| el-dropdown-item 嵌套在 el-popover 中，`command` 事件可能不冒泡 | 在 handleAdminCommand 中用 `switcherVisible.value = true` + fetchUsers()，不用 `command="switch-user"` 触发（el-dropdown-item 仍可保留 command 属性以兼容非 popover 场景，但实际触发由 popover open 走）|
| nextTick + autocompleteRef.value?.focus 在浮层第一次打开时未挂载 | watch 监听 switcherVisible 变化 + nextTick 等待 DOM 更新 |
| el-popover 默认 placement=bottom-start 改为 bottom-end 需精确控制 | 直接在 `<el-popover>` 上写 `placement="bottom-end"` |
| 移动端 placement=bottom 需 JS 动态改 | 加 `const isMobile = ref(window.matchMedia('(max-width: 768px)').matches)` + watch window resize + computed placement |
| 「不能切换到自身」理论上不会触发 | 仍保留 check 逻辑，万一 list 含 admin 自己时兜底 |
| 候选列表受限于 10 条（用户输入找不到目标） | 用户切到「去 /system/users 查」路径（功能互补，不在本 PR）|

### 移动端 placement 动态切换（实施时可能需要）

```js
const isMobile = ref(window.matchMedia('(max-width: 768px)').matches)
const popoverPlacement = computed(() => isMobile.value ? 'bottom' : 'bottom-end')

// 加 resize 监听
onMounted(() => {
  const mq = window.matchMedia('(max-width: 768px)')
  mq.addEventListener('change', (e) => isMobile.value = e.matches)
})
onUnmounted(() => {
  // 清理 listener
})
```

> 移动端切换 placement 是「锦上添花」——如果时间紧，可保持 `bottom-end` 在小屏不切换（浮层 320px + max-width: calc(100vw - 24px) 兜底即可，只是右边缘会贴一点屏幕边）

### 不做什么

- ❌ 不改后端 / SQL / router
- ❌ 不改 auth.js / api/index.js
- ❌ 不改 Signup.vue / Login.vue / UserManage.vue / Profile.vue
- ❌ 不加 avatar / 在线状态 / 角色 tag / 快捷键 / 排序 chip
- ❌ 不做远程搜索 / debounce / 分词 / 高亮
- ❌ 不做缓存（每次 popover 打开都重拉）
- ❌ 不加 transition / fade-in / 装饰动画
- ❌ 不动 login-signup-link（另一个 PR）
- ❌ 不在浮层内加「新建用户」入口
