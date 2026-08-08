# Design — 多用户管理（multi-user）

> 文档版本：v1.0　|　创建日期：2026-08-08　|　状态：待实施
> 配套 PRD：`tasks/prd-multi-user.md`
> 落地文件：`frontend/src/views/Profile.vue` + `Signup.vue` + 改 `UserManage.vue` + `Layout.vue` + `router/index.js` + `api/index.js`

---

## 1. Subject grounding（先把"为谁做"钉死）

- **具体主体**：内部个人基金管理系统的**用户身份层**——从单 admin 扩到「admin + 多个 user」的多用户管理。
- **受众**：
  - **User**：自用，进来**管理自己的账号**（看自己的 profile / 改昵称 / 改密码）。
  - **Admin**：运维，**邀请新人** + 管理所有 user。
- **页面单一任务**：
  - `Profile.vue`：「我是谁 / 我能改什么」
  - `Signup.vue`：「用邀请码进来」
  - `UserManage.vue` 邀请码 tab：「邀请新人」+「管理已发出的码」

**核心约束**：个人工具，不是营销页——所有"惊艳型"视觉都不合适，押注**「邀请码」**作为签名元素：8 位 monospace 字符 + 醒目的展示卡片 + 倒计时语气（7 天有效）。

## 2. 决策前自检（避开 3 个 AI 默认样式）

| AI 默认 | 为什么不适合本页面 | 我们的选择 |
|---------|------------------|----------|
| ① 米色背景 + 高对比衬线 + 赤陶色强调 | admin 工具 + 中文 + 高频使用；衬线字拖累扫读 | 沿用项目 Element Plus 浅灰系 + 系统中文 sans |
| ② 近黑底 + 单一荧光绿/朱红 | 单用户本地工具，深色伤眼 | 保持白底 + 邀请码本身用 monospace 大号 |
| ③ 大报版式 + 0 圆角 + 密集栏 | 用户管理表格 + 邀请码列表需要 z 轴区分 | 沿用 `el-table` + 1px `#eee` 分隔线 |

**核心判断**：本页的独特性**全押在「邀请码展示」**——admin 生成那一刻的视觉冲击（一行 8 位大号字符 + monospace + 「7 天有效」倒计时），是页面的"记住点"；其余全部走项目一致风格，**克制**。

## 3. Token 系统

### 3.1 颜色（5 个值 + 1 个签名色）

| Token | Hex | 用途 |
|-------|-----|------|
| `--color-primary` | `#409EFF` | 主操作（Element Plus 默认） |
| `--color-success` | `#67c23a` | 邀请码"有效"状态 |
| `--color-warning` | `#e6a23c` | 邀请码"即将过期"（< 24h） |
| `--color-danger` | `#f56c6c` | 邀请码"过期/已用/禁用" |
| `--text-primary` | `#303133` | 主文字 |
| `--text-secondary` | `#909399` | 副文字（已用 by 字段等） |

**约束**：除上述 6 个 token 外，**不引入**新颜色。需要警示时复用 `--color-danger` 或 `--text-secondary`。

### 3.2 字体（2 个角色，零新依赖）

| 角色 | 字体栈 | 用途 |
|------|--------|------|
| Body / 中文 | `-apple-system, "PingFang SC", "Microsoft YaHei", sans-serif` | 所有 UI 文字（沿用项目） |
| Monospace（**签名**） | `"JetBrains Mono", "SF Mono", Menlo, Consolas, monospace` | **仅用于邀请码 8 位字符本身**（大号展示 + 等宽复制格式） |

**约束**：**不**引新字体。中文用系统默认，仅邀请码 8 位字符串用 monospace 自带栈。

### 3.3 网格

- 页面外层：`el-card` 无边框无阴影，外 margin 20px（与 `IndexBasic.vue` / `FundManage.vue` 一致）
- Profile 内部 3 段：上 1 / 中 1 / 下 1，段间 1px `#eee` 分隔线 + 20px padding
- Signup 内部：单列 form，字段间距 20px
- UserManage 邀请码 tab：表格 + 分页 + 「生成」按钮

## 4. 签名元素（页面的「记住点」）

**邀请码展示卡片**——admin 点「生成」后弹出（或行内展示）：

```
┌────────────────────────────────────────────┐
│  邀请码（新）              7 天后过期        │
│                                            │
│        A3K9 X7M2                          │ ← 32-40px monospace 醒目
│                                            │
│        [ 复制 ]                            │
│                                            │
│  给对方分享此码；对方在 /signup 输码注册。 │
└────────────────────────────────────────────┘
```

- 32-40px monospace 字符（无连字符、空格分隔）
- 醒目对比（白底 + 主色字符 / 或主色背景 + 白色字符）
- 倒计时提示（"X 天后过期" / "X 小时后过期" / "已过期" 颜色三态：绿/金/红）
- 「复制」按钮 = 调 `navigator.clipboard.writeText()` + toast「已复制」

这是 admin 与 user 之间的**唯一契约**，给视觉权重。

## 5. 布局

### 5.1 Profile.vue

```
┌────────────────────────────────────────────────────────────┐
│  [我的账号]                                                  │
├────────────────────────────────────────────────────────────┤
│  头像 / 头像                                                 │
│  用户名： admin                                  (不可改)   │
│  昵称：   系统管理员                            [可编辑]    │
│  角色：   admin                                            │
│  注册时间：2026-08-08 09:00                                 │
│  状态：   启用                                              │
├────────────────────────────────────────────────────────────┤
│  [修改昵称]                                                  │
│  昵称：   [_______________________________]                │
│                                              [ 保存修改 ]    │
├────────────────────────────────────────────────────────────┤
│  [修改密码]                                                  │
│  当前密码： [_______________________________]                │
│  新  密  码： [_______________________________] (≥8位)     │
│  确认新密码： [_______________________________]             │
│                                              [ 修改密码 ]    │
└────────────────────────────────────────────────────────────┘
```

### 5.2 Signup.vue

```
┌────────────────────────────────────────┐
│           [Logo / 系统名]              │
│           欢迎加入                      │
│                                        │
│  邀请码  [__________]   (8 位)         │
│  用户名  [__________]   (4-20 位)      │
│  昵  称  [__________]   (2-32 位)      │
│  密  码  [__________]   (≥ 8 位)       │
│  确认密码 [__________]                 │
│                                        │
│           [  注 册  ]                  │
│                                        │
│  已有账号？ 登录                        │
└────────────────────────────────────────┘
```

- 居中卡片（max-width 420px），无 el-tabs
- 邀请码自动 `value.toUpperCase()`（输入小写也接受）
- 注册成功 → 自动登录 + 跳首页

### 5.3 UserManage.vue 邀请码 tab（在已有 UserManage.vue 加 tab）

```
[ 用户列表 ] [ 邀请码 (3) ]   ← el-tabs 第二 tab

[ + 生成新邀请码 ]

┌──────────────────────────────────────────────────────────┐
│  邀请码      状态       生成时间      过期时间    操作  │
│  ─────────  ─────────  ──────────  ─────────  ──────│
│  A3K9X7M2  ● 有效    09:00 08-08  09:00 08-15 [复制][禁用]│
│  7H2PQR4X  ● 已用    昨天            -         (只读)   │
│  9KM4D5B1  ● 禁用    前天            -         (只读)   │
│  J3R8W2V6  ● 过期    上周            昨天       (只读)   │
└──────────────────────────────────────────────────────────┘

                                        共 4 条  [< 1 >]
```

- 状态圆点 + 文字（与项目 `IndexBasic.vue` 的「启用」列风格一致）
- 「复制」按钮 = `navigator.clipboard.writeText(code)` + toast
- 「禁用」= 调 `/api/invite-codes/<id>` DELETE（软删 del_flag='0'）
- 已用 / 过期 / 禁用行：操作列只显示「复制」或完全只读（避免误操作）

### 5.4 Layout.vue 顶栏（现有「用户」菜单扩展）

```vue
<!-- admin 看到 -->
<el-submenu>
  <template #title>admin</template>
  <el-menu-item @click="goProfile">个人中心</el-menu-item>
  <el-menu-item @click="goUserManage" v-if="isAdmin">用户管理</el-menu-item>
  <el-menu-item @click="handleLogout">退出</el-menu-item>
</el-submenu>

<!-- user 看到 -->
<el-submenu>
  <template #title>lily</template>
  <el-menu-item @click="goProfile">个人中心</el-menu-item>
  <el-menu-item @click="handleLogout">退出</el-menu-item>
</el-submenu>
```

## 5.5 Admin 切换 user 视图（admin-only 完整方案）

admin 在自己日常 UI 上**默认看自己数据**，但可在顶栏切换到任意 user 视角（用于代操作 / 调试）。非 admin 角色不显示此下拉。

**位置**：顶栏右侧、display_name 标签**左侧**。`v-if="isAdmin()"` 整体显隐。

**两种状态**：
- **未切换**：下拉按钮文字「以自己身份查看」（淡灰），hover 高亮；点击展开 user 列表。
- **已切换**：下拉按钮文字变主色「以 [目标 user.display_name] 身份查看」+ 角标「切换中」；列表第一项是「回到自己」。

```
  [ 顶栏 右侧 ]
  ┌────────────────────────────────────────────┐
  │ [以 lily 身份查看 ×]  [admin / 管理员]  [退出登录] │
  └────────────────────────────────────────────┘
        ↑ 角标「切换中」可关
```

```
  下拉展开（admin 当前未切换）：
  ┌──────────────────────────┐
  │ ● 回到自己（admin）       │  ← 永远在第一位
  │ ────────────────────────  │
  │   小李 (lily)             │  ← 启用 user
  │   汤姆 (tom)              │  ← 启用 user
  │   老王 (wang) [已禁用]     │  ← 灰显不可选
  └──────────────────────────┘

  下拉展开（admin 当前以 lily 身份）：
  ┌──────────────────────────┐
  │ ● 回到自己（admin）       │  ← 高亮（带 ● 标记当前选中）
  │ ────────────────────────  │
  │   小李 (lily)             │  ← 高亮（带 ● 标记当前选中）
  │   汤姆 (tom)              │
  └──────────────────────────┘
```

**机制**：
- 切换写入后端 session（`session['impersonate_user_id']`），不污染 user 表
- 切换成功后调 `GET /api/me` 重新探测 → auth.user 更新为目标 user；所有业务 API 自动以目标 user_id 过滤
- 「回到自己」调 `POST /api/admin/impersonate/stop` → 清 session → 重新探测 → auth.user 回到 admin
- 切换期间所有写操作在 storage 层仍以目标 user 写入（持仓 / 买入流水归属目标 user）；admin 退出登录时若仍在切换中，session.clear() 一并清掉
- 目标 user 被软删 / 禁用时：当前请求 401（user 重新校验），自动退回「未切换」态

**存储决策**：
- 后端 `session['impersonate_user_id']` + `session['impersonate_username']`（仅 admin 可写，session 层不信任前端）
- `require_auth` 钩子在 `g.user = user` 之后判断：若 `_is_admin(g.user) and session.get('impersonate_user_id')`，把 `g.user.id` 临时覆盖为 impersonate_user_id，并在 g.user 加 `impersonated_by_admin` 标记
- 所有业务 storage 用 `g.user.id` 过滤，**storage 层无感**（不需改任何 storage 代码）
- 前端 `auth` store 加 `auth.impersonatedByAdmin: boolean` 字段，路由守卫 / UI 据此调整（如切换时显示「你正以 X 身份操作」提示条）

**API 路由**：
- `POST /api/admin/impersonate/start`（body `{user_id}`）：admin 切换到目标 user；非 admin 返 403；目标 user 存在 / 启用 / 未软删；返回 `{success, user}`，前端用它 `setAuthUser`
- `POST /api/admin/impersonate/stop`：清 session，回到 admin 自己
- 列表数据走现有 `userApi.getUsers`（带 enabled 过滤），不新增路由

**不**做：跨 user 共享 session、admin 切换期间改 admin 自己的密码 / 改 admin 的 role。

## 6. 组件规范

### 6.1 Profile.vue

```vue
<template>
  <div class="profile-page">
    <el-card class="info-card" shadow="never">
      <h3>我的账号</h3>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="用户名">{{ guser.username }}</el-descriptions-item>
        <el-descriptions-item label="角色">
          <el-tag :type="guser.role === 'admin' ? 'danger' : 'info'" size="small">
            {{ guser.role }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="昵称">{{ guser.display_name }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="guser.enabled ? 'success' : 'info'" size="small">
            {{ guser.enabled ? '启用' : '禁用' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="注册时间" :span="2">{{ guser.create_time }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card class="form-card" shadow="never">
      <h3>修改昵称</h3>
      <el-form :model="nicknameForm" :rules="nicknameRules" ref="nicknameRef" label-width="100px">
        <el-form-item label="昵称" prop="display_name">
          <el-input v-model="nicknameForm.display_name" maxlength="32" show-word-limit />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="nicknameSubmitting" @click="submitNickname">保存修改</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="form-card" shadow="never">
      <h3>修改密码</h3>
      <el-form :model="passwordForm" :rules="passwordRules" ref="passwordRef" label-width="100px">
        <el-form-item label="当前密码" prop="old_password">
          <el-input v-model="passwordForm.old_password" type="password" show-password />
        </el-form-item>
        <el-form-item label="新密码" prop="new_password">
          <el-input v-model="passwordForm.new_password" type="password" show-password />
        </el-form-item>
        <el-form-item label="确认新密码" prop="confirm_password">
          <el-input v-model="passwordForm.confirm_password" type="password" show-password />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="passwordSubmitting" @click="submitPassword">修改密码</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>
```

**校验规则**：
- `display_name`: `required, min: 2, max: 32`
- `old_password`: `required`
- `new_password`: `required, min: 8`（**项目首次加最低长度要求**，下个版本再严格）
- `confirm_password`: 必填 + 自定义 validator 等于 `new_password`

### 6.2 Signup.vue

```vue
<template>
  <div class="signup-page">
    <el-card class="signup-card" shadow="never">
      <div class="header">
        <h2>欢迎加入</h2>
        <p class="subtitle">用邀请码注册</p>
      </div>
      <el-form :model="form" :rules="rules" ref="formRef" label-width="90px">
        <el-form-item label="邀请码" prop="invite_code">
          <el-input
            v-model="form.invite_code"
            maxlength="8"
            placeholder="8 位邀请码"
            style="text-transform: uppercase;"
          />
        </el-form-item>
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" maxlength="20" placeholder="4-20 位" />
        </el-form-item>
        <el-form-item label="昵称" prop="display_name">
          <el-input v-model="form.display_name" maxlength="32" placeholder="2-32 位" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" show-password placeholder="≥ 8 位" />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirm_password">
          <el-input v-model="form.confirm_password" type="password" show-password />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="submitting" @click="submit" style="width: 100%;">
            注 册
          </el-button>
        </el-form-item>
      </el-form>
      <div class="footer">
        已有账号？<el-link type="primary" @click="$router.push('/login')">登录</el-link>
      </div>
    </el-card>
  </div>
</template>
```

**校验规则**：
- `invite_code`: `required, pattern: /^[a-zA-Z0-9]{8}$/`
- `username`: `required, min: 4, max: 20, pattern: /^[a-zA-Z0-9_]+$/`
- `display_name`: `required, min: 2, max: 32`
- `password`: `required, min: 8`
- `confirm_password`: 必填 + 自定义 validator 等于 password

**注册成功后**：后端 `/api/signup` 自动 set session，跳 `/`（首页 / dashboard）

### 6.3 UserManage.vue 邀请码 tab

```vue
<el-tabs v-model="activeTab" @tab-change="onTabChange">
  <el-tab-pane label="用户列表" name="users">
    <!-- 现有 UserManage 内容（admin 列表 + 增删改） -->
  </el-tab-pane>

  <el-tab-pane :label="`邀请码 (${inviteCount})`" name="invites">
    <div class="actions">
      <el-button type="primary" :loading="generating" @click="generateInvite">
        + 生成新邀请码
      </el-button>
    </div>
    <el-table :data="invites" v-loading="inviteLoading">
      <el-table-column prop="code" label="邀请码" min-width="160">
        <template #default="{ row }">
          <span class="invite-code">{{ row.code }}</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="120">
        <template #default="{ row }">
          <span :class="['status-dot', statusClass(row)]" />
          <span class="status-text">{{ statusText(row) }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="生成时间" width="170" />
      <el-table-column prop="expires_at" label="过期时间" width="170" />
      <el-table-column label="操作" width="200" fixed="right" align="center">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="copyCode(row)">复制</el-button>
          <el-button
            v-if="row.status === 'active'"
            link type="danger" size="small"
            @click="disableInvite(row)"
          >禁用</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination ... />
  </el-tab-pane>
</el-tabs>
```

**CSS**：
```css
.invite-code { font-family: "JetBrains Mono", "SF Mono", Menlo, monospace; font-size: 16px; font-weight: 500; }
.status-dot { display: inline-block; width: 6px; height: 6px; border-radius: 50%; margin-right: 6px; vertical-align: middle; }
.status-dot.active { background: #67c23a; }
.status-dot.used { background: #909399; }
.status-dot.expired { background: #f56c6c; }
.status-dot.disabled { background: #e6a23c; }
.status-text { font-size: 12px; color: #909399; vertical-align: middle; }
```

## 7. 交互规范

### 7.1 生成邀请码（admin）

```js
async function generateInvite() {
  generating.value = true
  try {
    const resp = await inviteCodeApi.create()
    ElMessage.success('邀请码已生成')
    ElMessageBox.alert(
      // 显示大号 monospace 邀请码卡片
      `<div class="invite-display">
        <div class="invite-code-big">${resp.code}</div>
        <div class="invite-expire">${formatExpire(resp.expires_at)} 后过期</div>
        <el-button type="primary" @click="copyAndClose('${resp.code}')">复制并关闭</el-button>
      </div>`,
      '邀请码已生成',
      { dangerouslyUseHTMLString: true }
    )
    fetchInvites()
  } catch (e) {
    ElMessage.error(e.message || '生成失败')
  } finally {
    generating.value = false
  }
}
```

### 7.2 复制邀请码

```js
async function copyCode(row) {
  try {
    await navigator.clipboard.writeText(row.code)
    ElMessage.success(`已复制：${row.code}`)
  } catch (e) {
    // 降级：选中文本
    const input = document.createElement('input')
    input.value = row.code
    document.body.appendChild(input)
    input.select()
    document.execCommand('copy')
    document.body.removeChild(input)
    ElMessage.success(`已复制：${row.code}`)
  }
}
```

### 7.3 状态判定（前端逻辑）

```js
function inviteStatus(row) {
  const now = Date.now()
  if (row.del_flag === '0') return 'disabled'
  if (row.used_at) return 'used'
  if (new Date(row.expires_at).getTime() < now) return 'expired'
  return 'active'
}

function statusText(row) {
  return { active: '有效', used: '已用', expired: '过期', disabled: '禁用' }[inviteStatus(row)]
}

function statusClass(row) {
  return inviteStatus(row)  // className = status
}
```

### 7.4 修改密码

```js
async function submitPassword() {
  const valid = await passwordRef.value.validate().catch(() => false)
  if (!valid) return
  passwordSubmitting.value = true
  try {
    await authApi.updateMe({ old_password, new_password })
    ElMessage.success('密码已修改')
    passwordForm.value = { old_password: '', new_password: '', confirm_password: '' }
  } catch (e) {
    ElMessage.error(e.message || '修改失败')
  } finally {
    passwordSubmitting.value = false
  }
}
```

### 7.5 Signup 提交

```js
async function submit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    await authApi.signup(form.value)
    ElMessage.success('注册成功，已自动登录')
    router.push('/')
  } catch (e) {
    ElMessage.error(e.message || '注册失败')
  } finally {
    submitting.value = false
  }
}
```

## 8. 路由 / 菜单（与 Layout 联动）

### 8.1 router/index.js

```js
// 新增
{
  path: '/signup',
  name: 'Signup',
  component: Signup,
  meta: { title: '注册', requiresAuth: false }  // 公开
},
{
  path: '/profile',
  name: 'Profile',
  component: Profile,
  meta: { title: '个人中心', requiresAuth: true, sort: 100 }  // 数字大，排最后
}
```

### 8.2 Layout.vue 顶栏（现有「用户」菜单扩展）

参考 §5.4。`isAdmin()` 已有（`stores/auth.js`），直接用。

## 9. 现有文件改动清单

| 文件 | 变化 |
|------|------|
| `frontend/src/views/Profile.vue` | **新建**（§6.1） |
| `frontend/src/views/Signup.vue` | **新建**（§6.2） |
| `frontend/src/views/UserManage.vue` | 加邀请码 tab（`el-tabs`）（§6.3） |
| `frontend/src/components/Layout.vue` | 顶栏 submenu 加「个人中心」+ admin 切换 user 下拉（§5.4 / §5.5）；iconMap 补 `/profile` |
| `frontend/src/stores/auth.js` | 加 `impersonatedByAdmin` 字段 + `setImpersonation/clearImpersonation` 导出 |
| `frontend/src/router/index.js` | 加 `/signup`（public）+ `/profile`（requiresAuth）路由（§8.1） |
| `frontend/src/api/index.js` | `authApi.signup/updateMe/startImpersonate/stopImpersonate` + `inviteCodeApi.list/create/remove` + `portfolioApi.batch`；现有 `fundApi/buyerApi/sellerApi/...` 透传 `?user_id=N` |
| `frontend/src/views/UserManage.vue` | 删除 user 按钮加二次确认（说明软删） |
| `data-crawler/app/web/api_server.py` | `_PUBLIC_PATHS` 加 `/api/signup`；新增 `signup`/`me PUT`/`invite-codes GET/POST/DELETE`/`admin/impersonate/start/stop` 路由；`require_auth` 加 impersonation 注入；业务路由加 `user_id` 过滤；管理类路由加 `@admin_required` |
| `data-crawler/app/storage/user_storage.py` | 已有；不需改 |
| `data-crawler/app/storage/invite_code_storage.py` | **新建**（InviteCode ORM + Storage） |
| `data-crawler/app/storage/portfolio_storage.py` | ORM 加 `user_id` 字段；`create/get_with_pagination/get_by_id` 加 `user_id` 形参（None=admin） |
| `data-crawler/app/storage/fund_buyer_storage.py` | 同上（user_id 形参；API 层注入） |
| `data-crawler/app/storage/fund_seller_storage.py` | 同上 |
| `data-crawler/app/storage/position_storage.py` | 同上 |
| `data-crawler/app/storage/position_daily_snapshot_storage.py` | 同上 |
| `data-crawler/app/storage/fund_dip_plan_storage.py` | 同上 |
| `data-crawler/app/storage/portfolio_position_storage.py` | 关联表加 user 归属校验（双校验两端 user） |
| `data-crawler/app/storage/__init__.py` | export `InviteCodeStorage` |
| `data-crawler/app/task/register_user_via_invite.py` | **新建**（事务化注册：validate invite → create user → create default portfolio → mark invite used + rollback） |
| `sql/alter/08_add_user_id_to_business_tables.sql` | **新建**（6 张表加 user_id + 1 张新表 invite_code + 兜底 WHERE user_id IS NULL 检查） |
| `sql/struct/position_daily_snapshot.sql` | 加 `user_id` 字段（迁移脚本同步改） |
| `sql/program/买入.sql` | `sp_insert_fund_buyer_by_change` 加 `p_user_id` 入参 + INSERT user_id 字段 |
| `sql/program/持仓每日快照备份.sql` | `backup_position_daily_snapshot` SELECT 段加 `p.user_id AS user_id`（**关键**，否则快照 user_id 全 NULL 权限校验失效） |
| `data-crawler/tests/conftest.py` | 扩 client fixture：autouse mock 所有业务 storage（`_buyer_storage/_seller_storage/_portfolio_storage/...`），新增 `_make_buyer/_make_portfolio/_make_invite` 等数据构造器；`admin_user/normal_user` 沿用；新加 `impersonating_admin` fixture 测切换场景 |
| `data-crawler/tests/test_invite_code_storage.py` | **新建**（5 case，PRD AC-6） |
| `data-crawler/tests/test_register_user.py` | **新建**（4 case） |
| `data-crawler/tests/test_multi_user_api.py` | **新建**（10 case，覆盖隔离 / 鉴权 / 切换 / 软删） |

## 10. 一致性 checklist

- [ ] Profile / Signup / UserManage 邀请码 tab 全部用 `el-card shadow="never"` + 20px margin
- [ ] 邀请码 8 位字符用 monospace（`JetBrains Mono` / `SF Mono` 栈）
- [ ] 邀请码状态：active/used/expired/disabled 四态用 4 种圆点色
- [ ] 「复制」按钮 fallback 到 `document.execCommand('copy')`（老浏览器兜底）
- [ ] 修改密码：旧 / 新 / 确认三字段，新密码 ≥ 8 位
- [ ] 邀请码 8 位大写（`text-transform: uppercase`，输入小写也接受）
- [ ] Signup 公开路由（meta.requiresAuth: false）
- [ ] Profile 需登录路由
- [ ] 顶栏 admin 看到「用户管理」+「个人中心」+「退出」；user 看到「个人中心」+「退出」
- [ ] Admin 切换 user 下拉：仅 admin 可见；非 admin 整段 `v-if` 隐藏；下拉第一项永远「回到自己」
- [ ] Admin 切换期间所有写操作以目标 user_id 写入（storage 层无感，由 `g.user.id` 覆盖驱动）
- [ ] 切换功能仅在 session 持久化（不污染 user 表）
- [ ] 测试 fixture 扩 conftest.py autouse 业务 storage mock，17 case 全走 HTTP 层不污染生产 DB
- [ ] API 层在路由入口强制覆盖 `data['user_id'] = g.user.id`（不接受 body 透传 user_id）
- [ ] 业务 storage 的 `get_xxx_with_pagination` 加 `user_id=None` 形参（None=admin 跳过过滤）
- [ ] `npm run build` 通过
- [ ] 现有 `IndexBasic.vue` / `FundManage.vue` 风格保持一致（卡片、表格、按钮、状态圆点）

## 11. 实现细节决策记录（Phase 3 澄清后）

- **Admin 切换 user 视角**：**做**（顶栏下拉切换，完整方案）。后端 session 存 `impersonate_user_id`，由 `require_auth` 钩子读 session 覆盖 `g.user.id`；前端 `auth` store 加 `impersonatedByAdmin` 标记；新增 `POST /api/admin/impersonate/start` + `POST /api/admin/impersonate/stop` 两个路由。
- **测试 fixture 隔离**：**扩 conftest.py** 业务 storage mock（autouse fixture），所有业务路由调用走 mock，17 个新 case 不打真 DB。
- **user_id 强制层**：**API 层强制**。业务 storage `create_xxx(data)` 接受 `data.get('user_id')`，但 API 路由函数在入口 `data['user_id'] = g.user.id` 覆盖；storage 层不校验 user_id 缺失（admin 通过 `?impersonate_user_id` 可改写）。
