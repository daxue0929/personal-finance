# PRD — Login 页添加「立即注册」入口

**Feature slug**: `login-signup-link`
**作者**: Claude（feature-dev 流程）
**日期**: 2026-08-09
**状态**: Discovery 完成，待用户批准进入实现

---

## 1. Introduction / Overview

`/signup` 是邀请码自助注册流程的入口（admin 在用户管理页生成 8 位邀请码，发给新人 → 新人访问 `/signup` 填邀请码 + 自选用户名密码 → 后端 `register_user_via_invite` 事务落库 + 标 used → 登录）。该流程后端、SQL、Signup.vue、UserManage.vue 邀请码 tab 均已实现，但 `/login` 页面**没有**任何提示告知「新人可以通过邀请码自助注册」。

当前痛点：完全不知道有邀请码机制的新用户（哪怕已经从 admin 拿到码）只能猜 URL `/signup`，或干脆问 admin「怎么注册」。`/login` 是用户访问系统的第一个页面，是最自然的引导位。

本功能在 `/login` 登录按钮下方增加一行「还没有账号？立即注册」文本链接，把新人平滑引导到已实现的 `/signup`，**不增加任何新业务逻辑**，只补齐一个入口。

---

## 2. Goals

1. **降低邀请码注册流程的发现成本**：新人从 `/login` 一眼能看到「立即注册」入口，1 次点击进入 `/signup`。
2. **保持 `/login` 视觉与交互不退化**：链接样式与 Element Plus 默认 `el-link` 一致，不破坏现有登录表单布局、提交逻辑、错误提示。
3. **零后端改动**：本功能仅前端。

---

## 3. User Stories

- **US-1** 作为一个收到邀请码的新用户，我想在登录页直接看到「立即注册」入口并点击它，**以免**我去问 admin「怎么注册」或猜测 URL。
- **US-2** 作为一个已登录用户的回头访客（session 未过期但主动点了「退出」），我在登录页看到「立即注册」链接，**不**会被它干扰主登录流程。
- **US-3** 作为一个键盘用户，我希望用 Tab 键能聚焦到「立即注册」链接，Enter 触发跳转，**以便**我不用鼠标也能完成注册引导。

---

## 4. Functional Requirements

| # | 描述 |
|---|------|
| FR-1 | 在 `/login` 页面的「登录」主按钮（`el-button type="primary"` 提交登录）**正下方**渲染一行：左侧灰色文字「还没有账号？」，右侧 Element Plus `el-link` 蓝色文字「立即注册」 |
| FR-2 | 点击「立即注册」链接后，浏览器 URL 变为 `/signup`，渲染 `Signup.vue`（已有的邀请码注册表单） |
| FR-3 | 链接使用 Vue Router 的 `router.push('/signup')` 或 `<router-link>`，保证浏览器后退按钮可回到 `/login` |
| FR-4 | 链接提供 a11y 增强：明确的 `aria-label="使用邀请码注册新账号"`（覆盖「立即注册」4 字过短的不足），并保证键盘 Tab 可达 + Enter 可触发 |
| FR-5 | 移动端（视口 ≤ 768px）下，链接与文字保持同一行不折行，触控热区 ≥ 44×44 px |
| FR-6 | 不影响 `/login` 的现有行为：未登录访问 `/login` 仍渲染登录表单；已登录访问 `/login` 仍重定向到首页 |

---

## 5. Non-Goals (Out of Scope)

- **NG-1**：不修改 `/api/signup` 后端、不修改 `invite_code` 表、不修改 `UserStorage` / `InviteCodeStorage`
- **NG-2**：不修改 `UserManage.vue` 的邀请码管理 tab（admin 端入口已完备）
- **NG-3**：不修改 `auth` 状态机、session 行为、路由守卫
- **NG-4**：不在登录页加「需邀请码」类辅助提示文字（用户决策）
- **NG-5**：不做新手引导弹窗、tooltip、动画过渡等额外 UX 元素
- **NG-6**：不改 admin 直接建用户（路径 B）的入口

---

## 6. Dependencies

| 类型 | 依赖 | 状态 |
|------|------|------|
| 前端组件 | `element-plus` 的 `el-link` 组件 | 已引入（package.json） |
| 路由 | `frontend/src/router/index.js` 中 `/signup` 公开路由 | 已配置 |
| 目标视图 | `frontend/src/views/Signup.vue` | 已实现，含邀请码 + 用户名 + 密码输入 |
| 后端 API | `POST /api/signup`（邀请码自助注册） | 已实现（`api_server.py:296`） |
| 数据库 | `invite_code` 表 | 已存在（`sql/alter/08_add_user_id_to_business_tables.sql:75`） |
| 浏览器 API | 路由跳转、键盘事件、触控热区 | 标配，无新增依赖 |

---

## 7. Timeline & Priority

- **优先级**：P2（体验补全，不阻塞任何业务）
- **工时估算**：开发 30 分钟（单文件）+ 验证 15 分钟（手动 + `npm run build`）
- **无外部 deadline**
- **交付方式**：单次 commit（`feat(frontend): 登录页添加立即注册入口`）

---

## 8. Risk Assessment

| 风险 | 等级 | 缓解 |
|------|------|------|
| 链接放在 `<el-form>` 内时，浏览器 Enter 键可能优先触发表单 submit | 低 | 用 `<router-link>`（原生 `<a>`）而非 `@click` 按钮，Enter 在 `<a>` 上不冒泡触发 form submit；或用 `@click.prevent` |
| 移动端字号过小 / 触控热区不够 | 低 | a11y 增强中显式保证触控热区 ≥ 44×44 px（FR-5） |
| el-link 默认样式与现有登录页配色冲突 | 低 | 登录页主题色为 Element Plus 默认蓝，el-link type=primary 颜色一致 |
| 改动 Login.vue 引发回归 | 低 | 改动范围仅「登录按钮下」追加一段，不触碰 `<el-form>` 的 `@submit` / model / rules |
| 公开路由 `/signup` 在已登录态下被重定向导致新人注册死循环 | 极低 | 当前路由守卫行为：已登录访问 `/login` 跳转首页；**已登录访问 `/signup` 也会跳首页**——这是预期行为，避免已登录用户误入注册流程 |

---

## 9. Accessibility Requirements

- **A11Y-1**：链接为原生 `<a>` 元素（通过 `el-link` 或 `router-link`），具有 `role="link"` 隐式语义
- **A11Y-2**：链接显式 `aria-label="使用邀请码注册新账号"`，覆盖可见「立即注册」4 字（屏幕阅读器用户得到更完整上下文）
- **A11Y-3**：键盘 Tab 可聚焦、Enter / Space 可激活（Element Plus `el-link` 默认支持）
- **A11Y-4**：聚焦时浏览器默认 focus 环可见（不强行 `outline: none`）
- **A11Y-5**：颜色对比度：文字「还没有账号？」灰色 ≥ 4.5:1，链接蓝色 ≥ 4.5:1（沿用 Element Plus 主题色，已合规）
- **A11Y-6**：移动端触控热区 ≥ 44×44 px（WCAG 2.5.5 Target Size）

---

## 10. Design Considerations

- **位置**：登录按钮正下方，与登录按钮在视觉上属于同一「操作区」，但与主按钮**视觉权重**不同（链接 vs 按钮）——避免误以为「注册」是主操作
- **样式**：沿用 Element Plus `el-link` 默认，type=primary（蓝色 + 下划线），与 admin 「管理端入口」等已有链接保持一致
- **文案**：「还没有账号？」灰色提示 + 「立即注册」蓝色链接，分两段（一段提示 + 一段动作），符合 Material Design / iOS HIG 模式
- **不引入新视觉元素**：不加分隔线、不加 icon、不加 hover 动画，保持极简
- **响应式**：移动端字号 `clamp(13px, 3.5vw, 14px)`，与登录页其他字号保持一致

---

## 11. Technical Considerations

- **实现位置**：`frontend/src/views/Login.vue`
- **实现方式**：在已有「登录」`<el-button>` 下方插入一个 `<div class="signup-hint">` 容器，内含 `<span>还没有账号？</span>` + `<el-link>` 或 `<router-link>`
- **路由跳转**：
  - 方案 A：`<router-link to="/signup" class="signup-link">立即注册</router-link>` + 样式（CSS 类）
  - 方案 B：`<el-link type="primary" @click="$router.push('/signup')">立即注册</el-link>`（事件方式）
  - **推荐方案 A**：原生 `<a>` 元素，对屏幕阅读器、右键「在新标签页打开」、SEO 链接关系更友好
- **类型定义**：无新 TS / 类型
- **状态管理**：无新 store
- **i18n**：当前 Login.vue / Signup.vue 均为中文硬编码，无 i18n 需求
- **构建**：改动后必须 `cd frontend && npm run build` 生成新 `dist/`，与源码同步提交

---

## 12. Success Metrics

- **SM-1**（功能）：从 `/login` 点击「立即注册」到达 `/signup` 耗时 ≤ 1 次点击、URL 正确
- **SM-2**（回归）：改动前后 `/login` 的登录功能、错误提示、键盘 Tab 顺序均不变化
- **SM-3**（构建）：`npm run build` 无报错、无新 warning；`dist/` 体积变化 < 1 KB
- **SM-4**（手动验证）：Chrome / Safari（macOS）、Chrome（移动端模拟）三处均通过
- **SM-5**（a11y）：键盘 Tab 顺序：用户名 → 密码 → 登录按钮 → 立即注册链接（链接在最后）

---

## 13. Open Questions

无遗留问题。所有设计决策已与用户确认：

| 问题 | 决策 |
|------|------|
| Feature slug | `login-signup-link` ✅ |
| 入口位置 | 登录按钮下、文本链接 ✅ |
| 文案 | 「还没有账号？立即注册」 ✅ |
| 是否加「需邀请码」辅助提示 | 不加 ✅ |
| 无障碍/响应式增强 | 手动加 a11y 增强（aria-label + 触控热区） ✅ |
| 链接组件选型 | **`el-link`**（非 `el-button link`，与 Signup.vue「去登录」轻度不一致；用户主动选择偏离 mirror 模式以贴合常见登录页样式，已记录） ✅ |

---

## 附录 A：UI 示意

```
+----------------------------------+
|  登录                            |
|  --------------                  |
|  用户名 [________]               |
|  密码   [________]               |
|                                  |
|         [ 登录 ]                 |
|                                  |
|  还没有账号？立即注册            |  ← 本功能新增
+----------------------------------+
```

## 附录 B：交付清单

- 改：`frontend/src/views/Login.vue`（追加约 8–12 行 template + 少量 CSS）
- 不改：后端、SQL、router、Signup.vue、UserManage.vue、auth
- 新增：无
- 删除：无
- 文档：本 PRD + 待生成 `tasks/design-login-signup-link.md` + `tasks/tasks-login-signup-link.md`
