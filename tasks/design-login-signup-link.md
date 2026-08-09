# Design — Login 页「立即注册」入口

**Feature slug**: `login-signup-link`
**作者**: Claude（feature-dev / frontend-design 流程）
**日期**: 2026-08-09
**对应 PRD**: `tasks/prd-login-signup-link.md`

---

## 1. 设计摘要

在 `Login.vue` 的金色「登录」主按钮下方，追加一行居中文本「还没有账号？立即注册」，其中「立即注册」是 Element Plus `el-link` 组件（type=primary），点击跳到已有的 `/signup` 路由。

- 灰色提示文字 13px / `#606266`
- 蓝色 el-link 13px / `#409eff`，hover 时显示下划线并提亮 8% → `#66b1ff`
- 整行居中，与登录按钮的间距 16px
- 链接的触控热区通过 `display: inline-block + min-height: 44px + line-height: 44px` 扩到 44×44 px
- `aria-label="使用邀请码注册新账号"`

## 2. 设计 token 表

| Token | 值 | 角色 |
|-------|------|------|
| `--signup-hint-fg` | `#606266` | 「还没有账号？」灰 |
| `--signup-link-fg-default` | `#409eff` | 链接静态色（EP primary）|
| `--signup-link-fg-hover` | `#66b1ff` | 链接 hover 色（EP lighter primary 8%）|
| `--signup-link-fg-active` | `#3a8ee6` | 链接按下色（EP darker primary）|
| `--signup-hint-fs` | `13px` | 字号 |
| `--signup-hint-mt` | `16px` | 与登录按钮的纵向间距 |
| `--signup-hint-align` | `center` | 横向居中 |
| `--signup-link-touch` | `44px` | 触控热区高度（WCAG 2.5.5）|
| `--signup-link-pad-x` | `12px` | 链接左右 padding（给点击区留白）|

> **token 实现**：本设计**不**在 `:root` 下新加 CSS 变量（保持最小化编辑原则），值直接写在 `.signup-hint` / `.signup-hint .el-link` 选择器内。后续如果第 3 个页面也要同类元素，再提变量。

## 3. 组件选型与属性

```vue
<el-link
  type="primary"
  :underline="false"
  aria-label="使用邀请码注册新账号"
  @click="$router.push('/signup')"
>立即注册</el-link>
```

- `type="primary"`：蓝色（EP 默认）
- `:underline="false"`：默认行为——静态无下划线，hover 时由 Element Plus 内部加上下划线
- `@click`：跳路由（不用 `router-link`，因为 `el-link` 渲染的是 `<a>`，`@click` 已经能阻止默认行为）
- 不传 `href`：避免右键「在新标签页打开」时跳到不存在的 URL（路由跳转是 SPA 行为，不该暴露 href）

## 4. CSS 实现

```css
.signup-hint {
  margin-top: 16px;
  text-align: center;
  font-size: 13px;
  color: #606266;
}

/* 触控热区 ≥ 44×44 px：inline-block + min-height + line-height */
.signup-hint :deep(.el-link) {
  display: inline-block;
  min-height: 44px;
  line-height: 44px;
  padding: 0 12px;
  vertical-align: middle; /* 防止 line-height 撑高后与文字基线错位 */
}
```

> **作用域穿透**：Login.vue 是 `<style scoped>`，Element Plus 的 `.el-link` 类在子组件作用域内，需用 `:deep()` 才能命中。

## 5. 状态矩阵

| 状态 | 颜色 | 下划线 | 说明 |
|------|------|--------|------|
| static | `#409eff` | 无 | 链接初始 |
| hover | `#66b1ff` | 显示 | EP 默认行为；颜色淡入由 EP transition（≤0.2s）处理 |
| mousedown / active | `#3a8ee6` | 显示 | EP 默认行为 |
| focus（键盘 Tab）| `#409eff` | 无 | 浏览器默认 focus 环，不抑制 |
| visited | `#409eff` | 无 | 不做特殊处理（不存 visited 状态对注册页无意义）|
| disabled | — | — | 本链接不存在 disabled 场景 |

## 6. 模板插入位置

`Login.vue` 第 48-53 行是金色登录按钮，本链接插在第 53 行 `<el-button>` 之后、第 54 行 `</el-form>` 之前：

```vue
<el-button
  class="login-btn"
  :loading="loading"
  :disabled="!form.username || !form.password"
  @click="handleLogin"
>登 录</el-button>
<div class="signup-hint">
  还没有账号？<el-link
    type="primary"
    :underline="false"
    aria-label="使用邀请码注册新账号"
    @click="$router.push('/signup')"
  >立即注册</el-link>
</div>
</el-form>
```

## 7. 与 Signup.vue「去登录」链接的差异（已与用户确认）

| 维度 | Login.vue 本链接 | Signup.vue 现有 |
|------|-----------------|----------------|
| 组件 | `el-link` | `el-button link` |
| hover 下划线 | 显示 | 不显示 |
| 字号 | 13px | 13px |
| 颜色 | primary 蓝 | primary 蓝 |
| 触控热区 | 44px 高（手写 min-height）| 默认按钮高度（约 24px）|
| 跳转 | `@click="$router.push('/signup')"` | `@click="$router.push('/login')"` |

**有意差异**：用户主动选择不沿用 Signup.vue 的 mirror 模式，让本链接 hover 时**长出下划线**（传统网页登录页惯例），更明确表达「可点击」。

## 8. a11y 收尾

- `aria-label="使用邀请码注册新账号"`：覆盖「立即注册」4 字过短的不足，屏幕阅读器读出完整动作
- 元素是原生 `<a>`（`el-link` 渲染产物），键盘 Tab 可达、Enter 可激活
- 焦点环：浏览器默认蓝色环，**不**写 `outline: none`
- 颜色对比度：13px `#409eff` on `#fff` ≈ 4.93:1（AA 通过）
- 触控热区：44×44 px（WCAG 2.5.5 AA）
- 不在 reduced-motion 用户上做特殊处理（本设计本就无动画）

## 9. 移动端（≤768px）

- 不调整字号（13px 在 360px 视口下可读）
- 不调整 padding（现有 `.login-form-wrap` 的 `padding: 24px; padding-top: 40px` 已给足）
- 触控热区 44px 自动适用（移动端无 hover，下划线不显示；点击区域足够大即可）

## 10. 反模式（明确不做）

- ❌ 加 icon（→ / + / 钥匙）—— 用户禁止
- ❌ 加分隔线 —— 用户禁止，登录页保持极简
- ❌ 加 hover 动画（颜色淡入 / 下划线滑动）—— 用户禁止
- ❌ 加「需邀请码」副文 —— 用户禁止，/signup 页面已有
- ❌ `:underline="true"` 永久下划线 —— 默认 hover-only 已足够
- ❌ 改 el-link 字重或 letter-spacing —— 不与主按钮的 `letter-spacing: 4px` / `font-weight: 700` 竞争
- ❌ 改输入框焦点环为链接色 —— 输入框焦点环是登录页「金色时刻」，不动
- ❌ 加圆角 / 边框 —— 文本链接不是按钮
- ❌ 不动 `.login-btn` 样式 —— 与本次任务无关

## 11. 视觉自检（脑内 1:1 模拟）

```
+----------------------------------+
|  欢迎回来                        |
|  登录以继续                      |
|                                  |
|  [ 用户名                     ]  |
|  [ 密码                       ]  |
|                                  |
|         [   登   录   ]          | ← 金色 #ffd04b，letter-spacing 4px
|                                  | ← 16px 留白
|     还没有账号？立即注册         | ← 灰 #606266 + 蓝 #409eff el-link
|                                  |   hover 时蓝变 #66b1ff + 出现下划线
+----------------------------------+
```

链接行高 44px（min-height 撑开），文字 13px 在 44px 容器内**垂直居中**（line-height 44px），视觉上仍是行内文字，但触控区是 44px 高方块。

## 12. 验收对照（PRD FR / A11Y / SM）

| PRD 项 | 实现位置 |
|--------|----------|
| FR-1 登录按钮下方一行 | `<el-button>` 后追加 `<div class="signup-hint">` |
| FR-2 点击跳 /signup | `@click="$router.push('/signup')"` |
| FR-3 router.push 保证后退 | 同上 |
| FR-4 aria-label + 键盘可达 | `aria-label="使用邀请码注册新账号"` + 原生 `<a>` |
| FR-5 移动端触控 ≥ 44×44 | `min-height: 44px` + `display: inline-block` |
| FR-6 不影响 /login 既有行为 | 仅追加节点，未改 model/rules/submit |
| A11Y-1 原生 `<a>` | `el-link` 渲染产物 |
| A11Y-2 aria-label | 同 FR-4 |
| A11Y-3 键盘 Tab/Enter | `el-link` 默认支持 |
| A11Y-4 浏览器焦点环 | 不写 `outline: none` |
| A11Y-5 对比度 ≥ 4.5:1 | `#409eff` on `#fff` ≈ 4.93:1 |
| A11Y-6 触控热区 ≥ 44×44 | 同 FR-5 |
| SM-1 1 次点击到达 /signup | `@click` 单次触发 |
| SM-2 /login 既有行为不变化 | 仅追加 8 行 template + 10 行 CSS |
| SM-3 npm run build 通过 | 见 Phase 5 |
| SM-4 浏览器实测 | 见 Phase 6 |
| SM-5 Tab 顺序 | el-form 顺序：input → input → button → link |
