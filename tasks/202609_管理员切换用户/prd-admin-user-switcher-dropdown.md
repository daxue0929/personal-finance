# PRD — admin 切换用户视角：下拉搜索框

**Feature slug**: `admin-user-switcher-dropdown`
**作者**: Claude（feature-dev 流程）
**日期**: 2026-08-09
**状态**: Discovery 完成，待用户批准进入实现

---

## 1. Introduction / Overview

`Layout.vue` 顶栏 admin 下拉菜单里的「切换用户视角」当前用 `ElMessageBox.prompt` 让 admin **手输 user_id**（`frontend/src/components/Layout.vue:210-237`）。这是个糟糕的 UX：admin 切视角前必须先去「用户管理」页（`/system/users`）查到目标 user_id，回到顶栏手输数字，输错就重试。

本功能把 `ElMessageBox.prompt` 替换为 **`el-popover` + `el-autocomplete` 下拉搜索框**：admin 点击「切换用户视角」后弹出一个 320px 宽的浮层，内含搜索输入框和候选用户列表（默认展示 10 个最近注册的非 admin 用户，按 user_id DESC）。admin 可直接键入 username / display_name 过滤，鼠标点击或键盘 Enter 选中后调用现有 `adminApi.startImpersonate(userId)`，行为与现状一致。

**纯前端改动**，不动后端、不动 auth 状态机、不动其他页面。

---

## 2. Goals

1. **消除「先去用户管理查 user_id 再回来手输」**：admin 切视角的操作步骤从 4 步（去查 → 抄 → 切 → 输）减为 1 步（点选）。
2. **零后端变更**：复用现有 `GET /api/users` + `POST /api/admin/impersonate`，10 条本地数据过滤毫秒级无感。
3. **保持现有「已切到 target」行为完全不变**：选中后调 `adminApi.startImpersonate` + `setImpersonate` + `router.go(0)`，顶栏「正在以 xxx 视角操作」警告条照常显示。

---

## 3. User Stories

- **US-1**：作为 admin，我想在顶栏点击「切换用户视角」后看到一个搜索浮层，里面直接列出最近注册的用户，**以便**我不用先去用户管理页查 user_id 再回来手输。
- **US-2**：作为 admin，我想在浮层的输入框里键入 username 或 display_name 关键字，候选列表实时过滤（不区分大小写），**以便**我在用户量较多时快速定位目标。
- **US-3**：作为 admin，我选中目标用户（鼠标点击或键盘 Enter）后系统自动切到 target 视角并刷新当前页，**以便**我立即以 target 身份继续操作业务模块。
- **US-4**：作为 admin，我在浮层打开时输入框自动获得焦点，可以直接键入；浮层关闭后输入框清空，**以便**下次打开是干净状态。
- **US-5**：作为 admin，我在浮层打开时会看到「正在加载」状态（≤几百毫秒），**以便**我心里有数不是「无响应」。

---

## 4. Functional Requirements

| # | 描述 |
|---|------|
| FR-1 | 仅当 `auth.realUser.role === 'admin'` 时，admin 顶栏下拉菜单显示「切换用户视角」菜单项（沿用现有判断逻辑，不退化） |
| FR-2 | 点击「切换用户视角」菜单项后，**不**调用 `ElMessageBox.prompt`；改弹出一个 `el-popover`（trigger=click，width=320px）|
| FR-3 | `el-popover` 内含一个 `el-autocomplete` 输入框 + 候选下拉列表（Element Plus 标准 `el-autocomplete` 行为）|
| FR-4 | **弹层打开时**，自动 focus 到输入框（admin 可直接键入）|
| FR-5 | **弹层打开时**，异步请求 `GET /api/users`；请求期间显示「加载中」状态（用 `el-autocomplete` 的 `loading` 属性或 v-loading 指令），避免「空白 200ms 让用户以为无响应」|
| FR-6 | **数据返回后**，客户端按 `user_id` 倒序、排除 `auth.realUser.id`（admin 自己）、取前 10 个作为默认候选列表 |
| FR-7 | 每项显示格式：`username - display_name`（如 `testuser01 - 测试用户`）；若 `display_name` 为空，显示 `username -`（保留 username + 短横线）|
| FR-8 | **键入时**（输入框非空），客户端本地过滤：保留 `username.toLowerCase().includes(q.toLowerCase())` 或 `display_name.toLowerCase().includes(q.toLowerCase())` 为真的项；过滤在 10 条本地数据上执行，零网络请求 |
| FR-9 | **输入框清空时**（用户删完字符），候选列表恢复为默认 10 个（`el-autocomplete` 默认行为）|
| FR-10 | 鼠标点击某项或键盘 Enter 选中后，弹层自动关闭；调 `adminApi.startImpersonate(targetUserId)` |
| FR-11 | 选中项 `user_id === auth.realUser.id`（admin 自己）时，弹 `ElMessage.warning('不能切换到自身')` 并阻止请求、不关弹层（让 admin 看到提示后继续选）|
| FR-12 | 接口 `/api/users` 失败时，弹 `ElMessage.error('加载用户列表失败')` 且**不**弹 popover |
| FR-13 | 切换成功后 `ElMessage.success('已切换到 ${display_name || username} 视角')` 并 `router.go(0)` 刷新当前页（沿用现有成功流程）|
| FR-14 | **弹层关闭后**，输入框 value 清空、下次打开是干净状态（无残留）|
| FR-15 | 现有「退出视角切换」（`stop-impersonate` 菜单项 + 顶栏警告条 + `router.go(0)`）行为不变，未退化 |
| FR-16 | 移动端（≤768px）下，popover 宽度仍 320px（不溢出到屏幕外），触控点击候选列表项无延迟 |

---

## 5. Non-Goals (Out of Scope)

- **NG-1**：不改 `/api/admin/impersonate` 后端
- **NG-2**：不改 `/api/users` 后端（包括不加 `?limit=10&sort=-id` 参数）
- **NG-3**：不改 `auth.js` 状态机（`setImpersonate` / `clearImpersonate` 不动）
- **NG-4**：不改 `UserManage.vue` 的用户列表（admin 在该页搜索用户的需求保持现状）
- **NG-5**：不做「按 email / 手机号 / 真实姓名」等扩展搜索字段
- **NG-6**：不做远程搜索 / 模糊匹配 / 高亮 / 分词
- **NG-7**：不改路由 / 菜单 / 主题色
- **NG-8**：不动 `login-signup-link`（另一个 PR）
- **NG-9**：不做「上次拉取列表缓存」—— 每次 popover 打开都重新拉一次 `GET /api/users`（用户决策：避免过期数据 + 简单）
- **NG-10**：不动 `Profile.vue`、不动其他 admin 专属页面
- **NG-11**：不做键盘快捷键（如 `Ctrl+K` 唤起搜索）—— 不在范围

---

## 6. Dependencies

| 类型 | 依赖 | 状态 |
|------|------|------|
| 前端组件 | `el-popover`（Element Plus）| 已全局注册 |
| 前端组件 | `el-autocomplete`（Element Plus）| 已全局注册 |
| API | `GET /api/users`（`userApi.getUsers`）| 已存在，需确认返回全量或分页足够大 |
| API | `POST /api/admin/impersonate`（`adminApi.startImpersonate`）| 已存在，签名不变 |
| 状态 | `setImpersonate(target, admin)` from `auth.js` | 已实现 |
| 状态 | `clearImpersonate()` from `auth.js` | 已实现（仅给「退出视角切换」用，本功能不直接调）|
| 后端 | `/api/users` 必须能在 admin 视角下返回所有用户（包括 enabled=0 / 已软删的）| **待 Phase 2 确认** |

---

## 7. Timeline & Priority

- **优先级**：P1（admin 高频操作的 UX 痛点，影响多用户场景效率）
- **工时估算**：开发 30 分钟（单文件 + 小改 api 调用）+ 验证 15 分钟（手动 9 项 + `npm run build`）
- **无外部 deadline**
- **交付方式**：单次 commit `feat(frontend): admin 切换用户视角改为下拉搜索框`

---

## 8. Risk Assessment

| 风险 | 等级 | 缓解 |
|------|------|------|
| `/api/users` 默认分页（如 page_size=10）会丢老用户 | 中 | Phase 2 必查 `userApi.getUsers` + `user_storage.list_users`，确认默认 page_size；若 ≤100 则 OK；否则显式 `page_size=1000` 兜底 |
| 客户端排序假设所有用户一次性返回；用户量 > 100 时性能下降 | 低 | 10 条本地过滤 O(n) 微秒级；按用户决策「用户量 > 100 再加后端 recent endpoint」|
| 切换时 `router.go(0)` 丢 dialog / 滚动位置 | 低 | 现有行为，未退化（admin 切视角本就该全刷）|
| popover 打开时输入框被 admin 误删再输入，过滤状态不一致 | 低 | Element Plus `el-autocomplete` 标准行为；v-model 单向绑定不会出现脏数据 |
| 「不能切换到自身」前端阻止后，用户怀疑为什么列表里没自己 | 低 | 默认列表已排除 admin 自己（FR-6），用户基本不会触发此分支；如触发，ElMessage 提示清晰 |
| popover 320px 在 360px 移动端视口下可能贴近屏幕边缘 | 低 | Element Plus popover 默认带 placement=bottom-start，会从触发器左侧对齐；320px + 触发器在右上的场景下正常 |
| 接口失败时不弹 popover，admin 找不到「为什么没反应」 | 中 | ElMessage.error 提示 + 顶栏「切换用户视角」菜单项可重新点击重试 |
| 用户列表含 disabled=0 用户，admin 切过去后无法登录 | 低 | 沿用现有 `/api/admin/impersonate` 后端逻辑（无 disabled 检查），行为一致；如 admin 切到 disabled 用户，那是 admin 主动操作 |

---

## 9. Accessibility Requirements

- **A11Y-1**：el-popover 标准 ARIA 角色（`role="dialog"`），键盘可达
- **A11Y-2**：el-autocomplete 标准 ARIA 角色（`role="combobox"`），含 `aria-expanded` / `aria-controls`
- **A11Y-3**：el-autocomplete 的 `aria-label="搜索目标用户"` 显式覆盖（候选列表用 `username - display_name` 文本，屏幕阅读器友好）
- **A11Y-4**：popover 打开后自动 focus 输入框（`autofocus`），键盘用户无需 Tab
- **A11Y-5**：列表项键盘可达：↑/↓ 选中、Enter 触发、Esc 关闭（Element Plus `el-autocomplete` 默认）
- **A11Y-6**：颜色对比度：候选文字 `username`（黑/EP 主黑） + `display_name`（灰 #606266） + 分隔符 `-`（灰），白底对比度 ≥ 4.5:1
- **A11Y-7**：loading 状态用文字「加载中...」或 EP 自带 spinner，配 `aria-live="polite"` 让屏幕阅读器知道数据加载

---

## 10. Design Considerations

### 触发与展示位置
- 现有 admin 下拉菜单第 74 行「切换用户视角」**保持位置不动**
- 选中后**不**再弹 prompt；改为 popover 浮层
- popover 默认 `placement="bottom-end"`（从触发器下方右对齐，避免遮挡顶栏）

### 浮层内部结构
```
┌──────────────────────────────┐
│  搜索目标用户（autofocus）  │  ← el-autocomplete 输入框
├──────────────────────────────┤
│  testuser01 - 测试用户      │  ← 候选列表项 1
│  zhang_san - 张三            │  ← 候选列表项 2
│  lily - 小李                 │  ← 候选列表项 3
│  ...                         │
│  （最多 10 项）              │
└──────────────────────────────┘
```

### 视觉 token
- 浮层宽度：320px（固定）
- 输入框高度：36px（EP default）
- 候选项高度：每项 ~36px
- 候选项 hover：EP 默认 `#f5f7fa` 浅灰
- 候选项 selected：EP 默认 primary 蓝
- 字体：14px（与顶栏一致）
- 颜色：username EP 主黑 `#303133` / display_name `#909399` / 分隔符 `#c0c4cc`

### 加载态
- 拉取 `/api/users` 期间，候选列表显示 EP loading spinner + 「加载中...」文字
- 加载完成 → 显示列表
- 加载失败 → ElMessage.error + 不显示浮层

### 选中后行为
- 弹层自动关闭
- 「已切换到 xxx 视角」toast
- `router.go(0)` 刷新整个 SPA

### 关闭后清理
- 弹层 `@close` 事件清空 `autocompleteQuery.value = ''`
- `el-autocomplete` 的 v-model 绑定的 ref 同步置空

---

## 11. Technical Considerations

### 文件改动
- `frontend/src/components/Layout.vue`：替换 `openSwitchUserDialog` 实现 + 引入新 ref（用户列表 / loading / 输入框 v-model / popover 可见性）
- **不**改 `frontend/src/api/index.js`（`userApi.getUsers` / `adminApi.startImpersonate` 已存在）
- **不**改 `frontend/src/stores/auth.js`（`setImpersonate` / `clearImpersonate` 已存在）
- **不**改后端任何文件

### 实现方式
- 在 `<script setup>` 顶部新增 4 个 ref：
  - `userList`（拉取后的全量用户列表，数组）
  - `recentUsers`（computed，按 user_id DESC + 排除 admin 自己 + 前 10）
  - `loadingUsers`（布尔，控制 loading 状态）
  - `switcherVisible`（控制 popover 可见）
  - `autocompleteQuery`（v-model 绑输入框）
- `handleAdminCommand('switch-user')` 改为：
  1. 异步 `fetchUsers()`（失败 → ElMessage.error + return）
  2. `switcherVisible.value = true`
  3. popover 内部用 `<el-autocomplete>` 配 `:fetch-suggestions` 回调
- 回调内部：基于 `autocompleteQuery.value` 过滤 `recentUsers.value`

### Element Plus 注意事项
- `el-popover` 需 `v-model:visible` 双向绑定
- `el-autocomplete` 用 `v-model` 绑输入字符串 + `:fetch-suggestions="cb"` 回调返回候选数组 + `trigger-on-focus`（打开时主动触发一次）
- `el-autocomplete` 默认不显示空字符串时的下拉；需用 `trigger-on-focus` 在弹层打开时主动调一次 cb

### 状态机
- popover 可见性：`switcherVisible`
- 加载：`loadingUsers`
- 候选：computed `recentUsers`
- 过滤：`:fetch-suggestions` 每次输入触发

### 不需要新依赖
- Element Plus 已有全部组件
- 不引 lodash（10 条数据不用 debounce）

---

## 12. Success Metrics

- **SM-1**：admin 从「想切到 target」到「已切到 target」步骤从 4 步（去查 → 抄 → 切 → 输）减为 1 步（点选）
- **SM-2**：默认列表展示 user_id 最大的 10 个非 admin 用户（按代码逻辑验证 + 手动 9 项验收）
- **SM-3**：键入 1 个字符，过滤在 50ms 内完成（10 条本地过滤实测微秒级）
- **SM-4**：切换成功后顶栏警告条正常出现，「退出视角切换」菜单项正常出现
- **SM-5**：`npm run build` 无 error；`dist/` 体积变化 < 2 KB
- **SM-6**：DevTools Console 无 4xx/5xx 报错（除正常的 401 / 403 鉴权预期）

---

## 13. Open Questions

无遗留问题。所有设计决策已与用户确认：

| 问题 | 决策 |
|------|------|
| Feature slug | `admin-user-switcher-dropdown` ✅ |
| 范围 | 仅前端（不动后端）✅ |
| 触发方式 | `click` ✅ |
| Popover 宽度 | 固定 320px ✅ |
| 默认行为 | 自动 focus + loading 状态 + 关闭后清空输入框 ✅ |
| admin 自己 | 默认列表排除 ✅ |
| display_name 为空显示 | `username -`（保留 username + 短横线）✅ |
| 不能切换到自身 | 列表里没有，理论上不会触发；万一触发 → ElMessage.warning 阻止 ✅ |
| 接口失败 | ElMessage.error + 不弹 popover ✅ |

---

## 附录 A：UI 示意

### 浮层打开（默认 10 项）
```
┌────────────────────────────────────┐
│  [ 🔍 搜索目标用户（自动focus）]   │
├────────────────────────────────────┤
│  testuser01 - 测试用户             │  ← hover 浅灰
│  zhang_san - 张三                   │
│  lily - 小李                       │
│  wangwu -                          │  ← display_name 为空
│  ...                                │
└────────────────────────────────────┘
```

### 键入「li」后
```
┌────────────────────────────────────┐
│  [ 🔍 li                       ]   │
├────────────────────────────────────┤
│  lily - 小李                       │  ← username 匹配
└────────────────────────────────────┘
```

### 选中后
```
[toast 出现在屏幕底部] 已切换到 测试用户 视角
[整个 SPA 刷新] 顶栏出现「正在以 测试用户 视角操作」警告
[菜单项变化]「切换用户视角」变为「退出视角切换」
```

---

## 附录 B：交付清单

- 改：`frontend/src/components/Layout.vue`（替换 `openSwitchUserDialog` + 新增 4 个 ref + 新增 popover 模板）
- 不改：后端 / SQL / router / Signup.vue / Login.vue / UserManage.vue / auth.js / api/index.js
- 新增：无
- 删除：无（`ElMessageBox.prompt` 引用随之移除，但 import 仍保留供未来用，或一并删 `ElMessageBox` import——待 Phase 5 决定）
- 文档：本 PRD + 待生成 `tasks/design-admin-user-switcher-dropdown.md` + `tasks/tasks-admin-user-switcher-dropdown.md`
