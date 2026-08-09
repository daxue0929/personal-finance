# Task List: Login 页「立即注册」入口

**Based on PRD**: `tasks/prd-login-signup-link.md`
**Based on Design**: `tasks/design-login-signup-link.md`
**生成日期**: 2026-08-09

---

## Relevant Files

### Files to Modify
- `frontend/src/views/Login.vue` — 在登录按钮下方追加 8 行 template + 10 行 CSS

### Files to Create
- 无

### Test Files
- 无新增（前端纯展示 + 单 click handler；无 vitest / jest 配置；验证走手动 + `npm run build`）

---

## Implementation Tasks

### 1. 在 `Login.vue` 登录按钮下方插入「立即注册」入口
**Effort Estimate**: Small（30 min）

#### Sub-tasks:
- [ ] 1.1 确认插入点：第 53 行 `</el-button>` 之后、第 54 行 `</el-form>` 之前
- [ ] 1.2 新增 `<div class="signup-hint">` 容器，内含「还没有账号？」文字 + `<el-link>` 链接
- [ ] 1.3 `el-link` 属性：`type="primary"`、`:underline="false"`、`aria-label="使用邀请码注册新账号"`、`@click="$router.push('/signup')"`
- [ ] 1.4 链接文字为「立即注册」（4 字）
- [ ] 1.5 模板插入完毕后确认 `<style scoped>` 不被破坏

### 2. 配套 CSS：容器样式 + 触控热区
**Effort Estimate**: Small（20 min）

#### Sub-tasks:
- [ ] 2.1 新增 `.signup-hint` 样式：`margin-top: 16px; text-align: center; font-size: 13px; color: #606266;`
- [ ] 2.2 新增 `.signup-hint :deep(.el-link)` 触控热区：`display: inline-block; min-height: 44px; line-height: 44px; padding: 0 12px; vertical-align: middle;`
- [ ] 2.3 确认 `<style scoped>` 段尾（`.login-btn.is-disabled` 块后）追加，**不重排**已有样式块
- [ ] 2.4 确认未触碰 `.login-btn` / `.login-brand` / `.form-error` 等已有规则

### 3. 浏览器手动验证（5 项 PRD 验收 + 1 项 a11y 增强）
**Effort Estimate**: Small（20 min）

#### Sub-tasks:
- [ ] 3.1 **FR-1 视觉**：在 `/login` 页面登录按钮下方肉眼可见「还没有账号？立即注册」，灰字 + 蓝链接
- [ ] 3.2 **FR-2 跳转**：点击「立即注册」1 次后 URL 变为 `/signup`，渲染 `Signup.vue`
- [ ] 3.3 **FR-3 浏览器后退**：从 `/signup` 点浏览器后退回到 `/login`，可重复 3 次
- [ ] 3.4 **FR-6 回归**：已登录状态访问 `/login` 仍重定向到首页（行为未变）
- [ ] 3.5 **FR-5 / A11Y-6 移动端**：DevTools 设 375×667 视口，链接仍可见，触控热区 ≥ 44px（DevTools 中看盒模型高度）
- [ ] 3.6 **A11Y-3 / SM-5 键盘 Tab**：键盘 Tab 顺序：用户名 → 密码 → 登录按钮 → 立即注册链接
- [ ] 3.7 **A11Y-2 aria-label**：Chrome DevTools → Elements 面板检查链接的 `aria-label` 属性正确
- [ ] 3.8 **FR-5 控制台**：F12 Console 无报错、无 404、无 401
- [ ] 3.9 **FR-2 hover 微差异**：鼠标悬停链接时颜色变浅、下划线出现；移开后恢复

### 4. 前端构建门禁
**Effort Estimate**: Small（10 min）

#### Sub-tasks:
- [ ] 4.1 在 `frontend/` 目录执行 `npm run build`，确认无 error（warning 可接受但需 review）
- [ ] 4.2 确认 `frontend/dist/` 目录被更新（`git status` 显示 `frontend/dist/` 下文件 modified）
- [ ] 4.3 确认 `dist/` 体积变化 < 1 KB（对比 `frontend/dist/assets/*.js` / `*.css` 前后大小）
- [ ] 4.4 如 build 报错，按错误信息修复（最可能：template 语法、el-link 引入）

### 5. 收尾
**Effort Estimate**: Small（10 min）

#### Sub-tasks:
- [ ] 5.1 对照 PRD §4 FR-1~6、§9 A11Y-1~6、§12 SM-1~5 全部 ✅
- [ ] 5.2 `git status` 确认变更范围：仅 `frontend/src/views/Login.vue` + `frontend/dist/`（不含后端 / SQL / 路由）
- [ ] 5.3 检查 `tasks/prd-login-signup-link.md` / `tasks/design-login-signup-link.md` 内容完整
- [ ] 5.4 在本任务清单（`tasks/tasks-login-signup-link.md`）把全部子任务勾选完
- [ ] 5.5 **不**自动 commit / push，等用户确认；commit 建议文案 `feat(frontend): 登录页添加立即注册入口 + 重新构建 dist/`

---

## Notes

### 实现顺序（TDD 适配）

项目级 TDD 规则要求「测试 → 实现 → 通过」，本改动是**前端纯展示 + 单 click handler**，无 vitest / jest 框架，TDD 的"测试"环节按以下方式适配：
- **测试用例** = §3 手动验证 9 项（FR-1~6 + A11Y-2/3/6 + hover 行为）
- **实现** = §1 + §2（template + CSS）
- **通过** = §3 + §4 全部勾选

### 依赖关系

- §1 依赖：无
- §2 依赖：§1（CSS 类名 `.signup-hint` 必须在 template 中存在才有意义）
- §3 依赖：§1 + §2
- §4 依赖：§1 + §2（仅当代码改完才有意义构建）
- §5 依赖：§1~§4 全部完成

### 风险与缓解

| 风险 | 缓解 |
|------|------|
| `<style scoped>` 命中不了 `.el-link` | 已用 `:deep()` 穿透（design §4）|
| `el-link` 未在 Login.vue 局部引入 | Element Plus 是全局注册的（`main.js` 已配置），无需 `import` |
| `<el-button>` 后的 `<div>` 破坏 `<el-form>` 布局 | `<div>` 是块级元素，el-form 容器会自然撑高；与现有 `.form-error` 行为一致 |
| 移动端字号 13px 不可读 | 13px 是 Element Plus 默认小字号，360px 视口下与 `.form-sub` 一致；不做移动端额外调整（已与用户确认）|
| hover 下划线与现有 `a` 链接冲突 | `el-link` 默认 `:underline="false"`，仅 hover 时显示，行为符合 Element Plus 标准 |

### 不做什么

- ❌ 不动 `Signup.vue`（其 `el-button link` 与本设计的有意差异已记录）
- ❌ 不动后端（`/api/signup` / invite_code 表）
- ❌ 不动 `frontend/src/router/index.js`
- ❌ 不加 i18n（项目目前全部中文硬编码）
- ❌ 不在登录页加「需邀请码」副文（用户决策）
- ❌ 不加 icon / 分隔线 / hover 动画
