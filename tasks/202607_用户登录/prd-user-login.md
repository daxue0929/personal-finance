# PRD：用户登录与用户管理

> 生成方式：遵循 `/create-prd`（Spec-to-Code）方法论。需求阶段文档，不涉及最终实现细节。

## 1. 概述

当前系统为单用户设计（无 user 表），所有 `/api/*` 接口无鉴权即可访问。本特性为系统增加用户登录能力：前端登录页 + 未登录重定向、用户表与用户管理界面、按用户配置登录态保持时长、基于浏览器 Cookie 的会话。这是 CLAUDE.md 演进方向“多用户支持”的第一步。

## 2. 目标

- 所有 `/api/*` 接口需登录后才能访问（放行 `/api/login`）。
- 支持多用户登录，数据共享（所有登录用户看到同一套基金/持仓数据）。
- 管理员可管理用户（增删改查、启停、配置登录态保持时长）。
- 登录态通过浏览器 Cookie 保持，时长按用户配置。
- 不引入新的后端依赖。

## 3. 用户故事

- 作为管理员，我想用用户名密码登录，以便访问系统。
- 作为管理员，我想为每个用户单独设置登录态保持时长（如 30 分钟、1 天），以便控制安全性。
- 作为管理员，我想增删改用户、启停用户，以便管理系统访问。
- 作为普通用户，我想登录后使用系统，但不能管理其他用户。
- 作为任何用户，我想在登录态过期时被自动引导回登录页。
- 作为管理员，我想在顶栏看到当前登录用户名并能退出登录。

## 4. 功能需求

1. **用户表 `user`**：`id`、`username`(唯一)、`password_hash`、`display_name`、`role`('admin'/'user')、`enabled`(1/0)、`session_ttl_minutes`(int，默认 60)、`del_flag`、`create_by`/`create_time`/`update_by`/`update_time`/`remark`。遵循现有 DB 约定（bigint 自增、utf8mb4、每列 COMMENT、索引含 del_flag）。
2. **登录** `POST /api/login` `{username, password}`：校验用户名密码（werkzeug `check_password_hash`，校验 `enabled=1` 且 `del_flag='1'`）→ 设置 Flask 签名 Cookie（permanent，`max_age = session_ttl_minutes×60`）→ 返回 `{success, user:{id,username,display_name,role}}`。失败返回 401 `{error}`。
3. **登出** `POST /api/logout`：清除登录 Cookie。
4. **登录态校验**：web 进程 `before_request` 对 `/api/*` 校验签名 Cookie（放行 `/api/login`）；未登录或过期返回 401 `{error:'未登录或登录已过期'}`。scheduler 进程（5001，仅内部）不校验。
5. **当前用户** `GET /api/me`：返回当前登录用户信息；未登录 401。供前端路由守卫与顶栏使用。
6. **用户管理 CRUD（仅 admin）**：
   - `GET /api/users` 分页 + 按用户名/状态搜索，返回 `{data,total,page,page_size}`。
   - `POST /api/users` 创建用户（`username`、`password` 必填；`role`、`enabled`、`session_ttl_minutes`、`display_name`、`remark` 可选）。
   - `PUT /api/users/:id` 更新（`password` 留空则不修改）。
   - `DELETE /api/users/:id` 软删（`del_flag='0'`）。
7. **权限控制**：非 admin 用户访问用户管理写接口返回 403。admin 不可删除/禁用自己（防锁死）。
8. **前端登录页** `/login`：用户名 + 密码 + 登录按钮，居中卡片式，独立全屏路由。成功后跳转首页。
9. **前端路由守卫**：`router.beforeEach`，访问需鉴权路由时若未登录重定向到 `/login`。
10. **前端 401 拦截**：axios 响应拦截器遇 401 → 清登录态 → 跳 `/login` 并提示。
11. **前端顶栏**：显示当前登录用户名 + 退出登录入口。
12. **用户管理页** `/system/users`：仿 `TaskManage.vue` 的 CRUD 模式（搜索 + 表格 + 分页 + 弹窗），含 `role`、`enabled`、`session_ttl_minutes` 字段。仅 admin 可见菜单。
13. **首个用户**：`sql/alter` 种子脚本插入默认 admin（用户名 `admin`，初始密码 `admin@123`，部署后建议修改）。
14. **Cookie 安全**：HttpOnly、SameSite=Lax、生产环境 Secure（HTTPS）。

## 5. 非目标（不做）

- 数据按用户隔离（共享数据，留作后续特性）。
- 开放注册端点。
- 记住我（remember me）。
- 登录失败锁定 / 密码强度强制。
- 邮箱、找回密码、OAuth/第三方登录。
- 移动端单独适配（沿用现有响应式）。
- 会话服务端撤销（签名 Cookie 方案不做；如需可后续演进为会话表）。

## 6. 依赖

- 后端：`werkzeug`（密码哈希）、`itsdangerous`（签名 Cookie）—— 均随 Flask 已安装，无新依赖。
- 前端：Element Plus（已有）；`@element-plus/icons-vue` 需补声明进 `package.json`。
- 数据库：新增 `user` 表（`sql/struct/`）+ 种子脚本（`sql/alter/`）。

## 7. 优先级与阶段

单一阶段交付。优先级：高（安全基线）。

## 8. 风险评估

- **首个 admin 锁死**：admin 误删/禁用自己导致无法管理。→ 禁止操作自己。
- **Cookie 泄露**：签名 Cookie 无法服务端撤销。→ HttpOnly+Secure+SameSite；`session_ttl` 可配短；后续可演进会话表。
- **SECRET_KEY 缺失**：签名 Cookie 需 `SECRET_KEY`。→ `.env` 增加 `SECRET_KEY`，不提交。
- **现有接口被锁**：加 `before_request` 后所有 `/api/*` 需登录，可能影响未带 Cookie 的旧客户端。→ 预期行为；部署时先建 admin。
- **scheduler 内部接口**：确保 5001 仅内部网络可达（已是 docker `expose` 非 `ports`）。

## 9. 无障碍

- 登录页表单 label 关联、键盘可提交（回车登录）、错误提示文本可读。
- 沿用 Element Plus 默认无障碍。

## 10. 设计考虑

- 登录页：居中卡片，品牌色，区别于主应用布局（独立全屏路由）。
- 用户管理页：与现有 `/system` 页面视觉一致。
- 详见 `design-user-login.md`（由 `/frontend-design` 产出）。

## 11. 技术考虑

- 鉴权：web 进程 `before_request` + Flask `session`；放行 `/api/login`。
- 会话：Flask 签名 Cookie，`permanent_session_lifetime` 按 `user.session_ttl_minutes` 动态设置（登录时读取）。
- 密码：`werkzeug.security.generate_password_hash`（scrypt）/ `check_password_hash`。
- 角色：`user.role` 字段；后端接口校验 admin；前端路由对 `/system/users` 限 admin。
- Storage：新增 `UserStorage`（仿 `FundBuyerStorage`），导出 `app/storage/__init__.py`，模块级实例化于 `api_server.py`。
- 前端：`/api/me` 探测登录态（HttpOnly Cookie 不可被 JS 读）；reactive 模块存当前用户。
- 双进程：鉴权只在 web；scheduler 5001 内部不鉴权。
- TDD：后端鉴权/登录/用户管理先写 pytest 测试。

## 12. 成功标准

- 未登录访问任意 `/api/*`（除 `/api/login`）返回 401，前端跳登录页。
- admin 可登录、管理用户、配置会话时长；普通用户可登录但无法管理用户。
- 登录态按用户配置时长过期。
- 既有功能（基金/持仓/任务等）登录后正常使用。
- 后端单测覆盖：登录成功/失败、鉴权、权限、CRUD、防锁死。

## 13. 待解决问题

- 默认 admin 初始密码：建议 `admin@123`，部署后强制修改。（待确认）
- `session_ttl_minutes` 合理默认：建议 60 分钟。（待确认）
