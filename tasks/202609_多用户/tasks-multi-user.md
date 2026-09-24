# Task List: 多用户隔离（multi-user）

**基于 PRD**: `tasks/prd-multi-user.md`
**配套设计**: `tasks/design-multi-user.md`
**Feature slug**: `multi-user`

> 本任务清单按 TDD 节奏推进：每个子任务先写测试（明确预期/边界）→ 再写实现 → 在 `data-crawler/` 下 `python3 -m pytest tests/<file>.py -q` 跑通 → 勾选。所有改动遵循「最小化编辑」原则。

---

## Relevant Files

### Files to Create

#### 后端
- `data-crawler/app/storage/invite_code_storage.py` — 邀请码 ORM + Storage（create/validate/mark_used/list_by_admin）
- `data-crawler/app/task/register_user_via_invite.py` — 事务化注册流（validate → create user → create portfolio → mark invite + rollback）
- `data-crawler/tests/test_invite_code_storage.py` — 5 case（创建/过期/已用/mark_used/admin 隔离）
- `data-crawler/tests/test_register_user.py` — 4 case（成功流/无效码/重名/失败回滚）
- `data-crawler/tests/test_multi_user_api.py` — 10 case（隔离/越权/admin query/signup/invite/me/软删）

#### 前端
- `frontend/src/views/Profile.vue` — 个人中心（账号信息 + 改昵称 + 改密码）
- `frontend/src/views/Signup.vue` — 邀请码注册（公开路由）

#### SQL
- `sql/alter/08_add_user_id_to_business_tables.sql` — 6 表加 user_id + invite_code 新表 + 兜底检查

#### 文档
- `docs/deployment.md` — 追加「多用户部署」章节

### Files to Modify

#### 后端
- `data-crawler/app/web/api_server.py` — 大改核心（signup/me PUT/invite-codes/admin impersonate + 业务路由 user_id 过滤 + 管理类 admin_required + 存储过程调用加 user_id）
- `data-crawler/app/storage/portfolio_storage.py` — ORM 加 user_id；create / get_with_pagination / get_by_id 加 user_id 形参
- `data-crawler/app/storage/fund_buyer_storage.py` — 同上
- `data-crawler/app/storage/fund_seller_storage.py` — 同上
- `data-crawler/app/storage/position_storage.py` — 同上
- `data-crawler/app/storage/position_daily_snapshot_storage.py` — 同上
- `data-crawler/app/storage/fund_dip_plan_storage.py` — 同上
- `data-crawler/app/storage/portfolio_position_storage.py` — 关联表双校验（两端 user 归属）
- `data-crawler/app/storage/__init__.py` — export `InviteCodeStorage`
- `data-crawler/tests/conftest.py` — 扩 autouse 业务 storage mock + 字典构造器 + impersonating_admin fixture

#### 前端
- `frontend/src/api/index.js` — `authApi.signup/updateMe/startImpersonate/stopImpersonate` + `inviteCodeApi.list/create/remove` + `portfolioApi.batch`；现有 fundApi/... 透传 `?user_id=N` + `?portfolio_id=N`
- `frontend/src/router/index.js` — 加 `/signup`（public）+ `/profile`（requiresAuth）
- `frontend/src/stores/auth.js` — 加 `impersonatedByAdmin` 字段 + `setImpersonation/clearImpersonation`
- `frontend/src/components/Layout.vue` — 顶栏 submenu 改 `el-dropdown` + admin 切换下拉（§5.5）+ iconMap 补 `/profile`
- `frontend/src/views/UserManage.vue` — 加 `el-tabs`「用户列表」+「邀请码」；删除 user 二次确认

#### SQL
- `sql/struct/position_daily_snapshot.sql` — 加 `user_id` 字段
- `sql/program/买入.sql` — `sp_insert_fund_buyer_by_change` 加 `p_user_id` 入参 + INSERT user_id 字段
- `sql/program/持仓每日快照备份.sql` — SELECT 段加 `p.user_id AS user_id`

### Test Files
- `data-crawler/tests/test_invite_code_storage.py`（新建）
- `data-crawler/tests/test_register_user.py`（新建）
- `data-crawler/tests/test_multi_user_api.py`（新建）
- `data-crawler/tests/test_fund_buyer.py` / `test_fund_seller.py` / `test_position.py` / `test_portfolio.py`（fixture 加 user_id；走 mock 不污染）

---

## Implementation Tasks

### 1. 测试基础设施（conftest 业务 storage mock）

**Effort Estimate**: Small

**目标**: 17 个新测试 case 全走 HTTP 层 + mock 业务 storage，不打真 DB（项目 .env 指向生产库）。

#### Sub-tasks:
- [ ] 1.1 **先写测试**: 在 `test_auth.py` 加一个 `test_client_uses_mock_user_storage` 烟雾测试，验证现有 mock 仍生效
- [ ] 1.2 改 `conftest.py`：`_make_user` 已有；新增 `_make_buyer(_id, fund_code, ...)` / `_make_portfolio(_id, name, user_id, ...)` / `_make_invite(_id, code, ...)` / `_make_position(_id, fund_code, user_id, ...)` 字典构造器
- [ ] 1.3 改 `conftest.py`：`client` fixture 扩为 autouse，把 `_buyer_storage/_seller_storage/_portfolio_storage/_position_storage/_portfolio_position_storage/_log_storage/_run_record_storage/_task_storage/_fund_storage/_nav_storage/_index_storage/_index_basic_storage/_position_snapshot_storage/_dip_plan_storage` 全部 MagicMock 替换（与现有 `_user_storage` mock 风格一致）
- [ ] 1.4 改 `conftest.py`：新增 `impersonating_admin` fixture（admin 已切到 user B 视角：`session['impersonate_user_id'] = normal_user['id']`）
- [ ] 1.5 跑 `cd data-crawler && python3 -m pytest tests/test_auth.py tests/test_auth_extra.py -q` 确认现有测试仍过（无回归）
- [ ] 1.6 **验收**: conftest 改动后所有现有 27 个 test_*.py 跑通，**零回归**

---

### 2. SQL 迁移 + 存储过程

**Effort Estimate**: Medium

**目标**: 6 张业务表加 user_id + 新表 invite_code + 改 2 个存储过程。Schema 是其他一切的前提。

#### Sub-tasks:
- [ ] 2.1 **先写 SQL 验收脚本**: `data-crawler/tests/test_sql_migration.py`（开发 DB 跑过迁移后用）—— 验证 6 表都有 user_id 字段 + invite_code 表存在 + sp 入参含 p_user_id；不跑过则测试 fail
- [ ] 2.2 新建 `sql/alter/08_add_user_id_to_business_tables.sql`，分步骤（PRD AC-1）：
  - 步骤 1: 6 张表 `ADD COLUMN user_id BIGINT NULL`（portfolio / fund_buyer / fund_seller / position / position_daily_snapshot / fund_dip_plan）
  - 步骤 2: `UPDATE xxx.user_id = (SELECT id FROM user WHERE username='admin')`
  - 步骤 3: 6 张表 `MODIFY COLUMN user_id BIGINT NOT NULL`
  - 步骤 4: 6 张表 `ADD INDEX idx_user_id (user_id)`
  - 步骤 5: `CREATE TABLE invite_code`（8 字段 + 2 索引，PRD AC-1 表）
  - 步骤 6: 兜底 `SELECT COUNT(*) FROM xxx WHERE user_id IS NULL` 应为 0
- [ ] 2.3 改 `sql/program/买入.sql`：`sp_insert_fund_buyer_by_change` 加 `IN p_user_id BIGINT` 入参；INSERT 段加 `user_id` 字段
- [ ] 2.4 改 `sql/program/持仓每日快照备份.sql`：SELECT 段加 `p.user_id AS user_id`，INSERT 列加 `user_id`
- [ ] 2.5 改 `sql/struct/position_daily_snapshot.sql`：加 `user_id BIGINT NOT NULL DEFAULT 1 COMMENT '所属 user'` 字段
- [ ] 2.6 改 `data-crawler/app/web/api_server.py:1393-1396`：`session.execute(text("CALL sp_insert_fund_buyer_by_change(:user_id, :fund_code, :change_pct)"))` 同步加 `:user_id` 参数
- [ ] 2.7 **真 DB 跑迁移**（开发环境）：`mysql < 08_add_user_id_to_business_tables.sql` → 跑 `WHERE user_id IS NULL` 兜底检查
- [ ] 2.8 跑 `pytest tests/test_sql_migration.py -q` 通过

---

### 3. 后端 Storage 层 + Task（事务注册）

**Effort Estimate**: Large

**目标**: 6 个业务 storage + 1 个新 InviteCodeStorage + 1 个新 register_user_via_invite task。

#### Sub-tasks:
- [ ] 3.1 **先写测试**: `test_invite_code_storage.py` 5 case（PRD AC-6）：
  - `test_create_generates_8_char_code`（断言 `len(code) == 8` + `set(code).issubset(string.ascii_letters + string.digits)`）
  - `test_validate_expired_returns_none`（构造 expires_at < now 记录 → 返 None）
  - `test_validate_used_returns_none`（构造 used_at 非空 → 返 None）
  - `test_mark_used_sets_timestamp_and_user`（调 mark_used → 再 validate 返 None）
  - `test_list_by_admin_filters_other_admins`（admin A 看不到 admin B 生成的码）
- [ ] 3.2 新建 `data-crawler/app/storage/invite_code_storage.py`：
  - `InviteCode(Base)` ORM 8 字段（id/code/created_by/expires_at/used_at/used_by/del_flag/create_time/update_time）+ 2 索引
  - `_to_dict` 转对外字典（含 `expires_at` ISO 字符串 + `used_at` 同）
  - `InviteCodeStorage(StorageBase)`：`create(admin_id, ttl_days=7) -> str`（生成 8 位 a-z0-9 + UNIQUE 约束兜底重试）/ `validate(code) -> Optional[dict]`（存在 + 未过期 + 未用 + del_flag='1'）/ `mark_used(invite_id, user_id) -> bool` / `list_by_admin(admin_id, include_used=True)`（分页）
- [ ] 3.3 改 `data-crawler/app/storage/__init__.py`：export `InviteCodeStorage`
- [ ] 3.4 跑 `pytest tests/test_invite_code_storage.py -q` 5 case 全过
- [ ] 3.5 **先写测试**: `test_register_user.py` 4 case（PRD AC-6）：
  - `test_register_user_creates_user_portfolio_invite_used`（调 `register_user_via_invite("ABC12345", "pw", "nick")` → 断言 user 字典 / portfolio "默认组合" / invite.used_at 非空 / invite.used_by=user.id）
  - `test_register_user_invalid_code_raises`（无效码 → ValueError）
  - `test_register_user_duplicate_username_raises`（码有效但 username 已存在 → ValueError）
  - `test_register_user_rollback_on_portfolio_create_fail`（mock portfolio.create 抛异常 → 断言 user 和 invite 都回滚到调用前状态）
- [ ] 3.6 新建 `data-crawler/app/task/register_user_via_invite.py`：
  - `register_user_via_invite(invite_code, password, display_name) -> Dict`：
    - 步骤 1: `invite_code_storage.validate(code)` → 拿 invite 记录（None 抛 ValueError("邀请码无效")）
    - 步骤 2: `user_storage.create_user(...)`（username=invite 关联的待注册名？此处需传入新 username——扩展：函数改签名 `register_user_via_invite(invite_code, username, password, display_name)`）
    - 步骤 3: `portfolio_storage.create(name='默认组合', user_id=new_user.id)`
    - 步骤 4: `invite_code_storage.mark_used(invite_id, new_user.id)`
    - 步骤 5: 全程 try/except + 手动 rollback：失败时回滚 user（del_flag='0'）+ invite（清 used_at/used_by）
- [ ] 3.7 跑 `pytest tests/test_register_user.py -q` 4 case 全过
- [ ] 3.8 改 6 个业务 storage ORM 加 `user_id` 字段（Column 位置在 fund_code/name 之后，COMMENT 写「所属 user」）；不改 `fund_nav_history`（PRD 整表共享）
- [ ] 3.9 改 6 个业务 storage `create_xxx(data)`：接受 `data.get('user_id')`（不改 storage 行为；API 层负责注入；与现有 `fund_buyer_storage.create_buyer` 风格一致）
- [ ] 3.10 改 6 个业务 storage `get_xxx_with_pagination(...)`：在最后位置加 `user_id=None` 形参；None=admin 跳过过滤；非 None 则 `query.filter(XXX.user_id == user_id)`
- [ ] 3.11 改 `portfolio_position_storage.create_portfolio_position(portfolio_id, position_id, ...)`：函数体内**双校验**——查 portfolio 拿 user_id + 查 position 拿 user_id；任一与传入的 user_id 不符返 `None` 或抛 `PermissionError`；admin 跳过（user_id 传 None）
- [ ] 3.12 改 `portfolio_position_storage.get_portfolio_positions(portfolio_id, user_id=None)`：user_id 非 None 时校验 portfolio.user_id == user_id；不通过返空列表
- [ ] 3.13 改 `portfolio_position_storage.delete_portfolio_position(relation_id, user_id=None)`：先查 relation 拿 portfolio_id + position_id，分别校验两端 user 归属；user_id 非 None 时不通过返 False
- [ ] 3.14 跑 `pytest tests/ -q` 全量通过（现有 27 case 无回归 + 新 9 case 通过）

---

### 4. 后端 API（api_server.py 大改）

**Effort Estimate**: Large

**目标**: 17 个新 API 路由 + 业务路由 user_id 过滤 + 管理类 admin_required + admin 切换下拉。

#### Sub-tasks:
- [ ] 4.1 **先写测试**: `test_multi_user_api.py` 10 case（PRD AC-6）：
  - `test_user_a_cannot_see_user_b_buyers`（user A 登录 → 调 `/api/buyers` → 断言只返 user A 的；mock `_buyer_storage.get_buyers_with_pagination.assert_called_with(..., user_id=2)`）
  - `test_user_a_cannot_update_user_b_position`（user A 调 PUT /api/positions/<b_id> → 403；mock 验 `position_storage.update_position` 未被调）
  - `test_admin_can_list_all_users_buyers_via_query`（admin 调 `/api/buyers?user_id=2` → 200，验 mock 收到 user_id=2 但**不**强加 g.user.id 过滤）
  - `test_user_cannot_associate_other_users_portfolio_position`（user A 用 user B 的 position_id 调 POST /api/portfolio-positions → 403）
  - `test_user_cannot_see_other_users_portfolio_positions`（user A 调 GET /api/portfolio-positions?portfolio_id=<b_id> → 403）
  - `test_signup_creates_user_and_default_portfolio`（POST /api/signup 有效码 → 200 + session 注入 user_id）
  - `test_signup_with_invalid_code_returns_400`（POST /api/signup 无效码 → 400）
  - `test_invite_code_admin_only_endpoints`（user 调 GET /api/invite-codes → 403；admin 调 → 200）
  - `test_me_endpoint_returns_current_user`（GET /api/me → 200 返 g.user；PUT /api/me 改昵称 → 200）
  - `test_delete_user_soft_del_keeps_data`（admin 删 user A → user A 再调 /api/me → 401；但 user A 的 buyers 仍可在 DB 查到）
  - **附加 case**（admin 切换）：
  - `test_admin_can_impersonate_user`（admin 调 POST /api/admin/impersonate/start {user_id: 2} → 200；后续业务路由 g.user.id 临时 = 2）
  - `test_non_admin_cannot_impersonate`（user 调 POST /api/admin/impersonate/start → 403）
- [ ] 4.2 改 `require_auth` 钩子（:154-181）：在 `g.user = user` 之后加 impersonation 注入：
  ```python
  if _is_admin(g.user) and session.get('impersonate_user_id'):
      target_id = session.get('impersonate_user_id')
      target = _user_storage.get_user_by_id(target_id)
      if target and target.get('enabled'):
          g.user = {**target, '_impersonated_by_admin_id': user['id']}
      else:
          session.pop('impersonate_user_id', None)  # target 被删/禁用 → 清掉
  ```
- [ ] 4.3 `_PUBLIC_PATHS`（:136）加 `'/api/signup'`
- [ ] 4.4 新增 `POST /api/signup`（:184 附近）：仿 login 路由结构；调 `register_user_via_invite` → set session；返 `{'success': True, 'user': user_dict}`
- [ ] 4.5 新增 `PUT /api/me`（:222 之后）：body 区分 password / display_name；调 `user_storage.update_user(g.user.id, data)`；返 `{'success': True}`
- [ ] 4.6 新增 `GET/POST/DELETE /api/invite-codes`（admin_required）：
  - GET：调 `_invite_code_storage.list_by_admin(g.user.id, ...)`；返 list
  - POST：调 `_invite_code_storage.create(g.user.id)`；返 `{'code', 'expires_at'}`
  - DELETE `/api/invite-codes/<id>`：调 `_invite_code_storage.delete(id)`（软删 del_flag='0'）
- [ ] 4.7 新增 `POST /api/admin/impersonate/start`（admin_required）：body `{user_id}`；set session `impersonate_user_id` + `impersonate_username`；返 `{'success': True, 'user': target_user_dict}`
- [ ] 4.8 新增 `POST /api/admin/impersonate/stop`（admin_required）：清 session；返 `{'success': True}`
- [ ] 4.9 业务路由（buyers/sellers/positions/snapshots/portfolio-positions/dip-plans/portfolios）入参加 user_id 过滤：在每个 list 类路由函数顶部 `_filter_user_id = g.user.id if not _is_admin(g.user) else None`（admin 跳过）；调 storage 时传 `user_id=_filter_user_id`
- [ ] 4.10 业务路由 create 类：API 层在路由入口强制 `data['user_id'] = g.user.id`（admin 通过 `?impersonate_user_id=N` 已被 `require_auth` 钩子覆盖 `g.user.id`，无需 body 透传）
- [ ] 4.11 业务路由 update/delete：先 `storage.get_by_id(id)` 拿对象；assert 对象.user_id == g.user.id（admin 跳过）；不通过返 403
- [ ] 4.12 `/api/portfolio-positions` POST 路由：调 storage 前确保 storage 内已双校验（3.11）
- [ ] 4.13 `/api/portfolio-positions?portfolio_id=X` GET 路由：传 `user_id=g.user.id` 给 storage
- [ ] 4.14 管理类路由加 `@admin_required`：`/api/tasks` POST/PUT/DELETE、`/api/crawl` POST、`/api/task/run/<func>` POST、`/api/start` POST、`/api/stop` POST、`/api/funds` POST/PUT/DELETE、`/api/logs*` 全系列（按 PRD AC-4 列表 17 条逐条加）
- [ ] 4.15 跑 `pytest tests/ -q` 全量通过（含新 12 case）

---

### 5. 前端基础设施（api / router / auth store / Layout 顶栏）

**Effort Estimate**: Medium

**目标**: 前端 API 扩方法 + 路由加 2 个 + auth store 加字段 + Layout 顶栏 admin 切换下拉。

#### Sub-tasks:
- [ ] 5.1 改 `frontend/src/api/index.js`：`authApi` 扩 4 方法：`signup(data)` / `updateMe(data)` / `startImpersonate(data)` / `stopImpersonate()`（signup + me 已有，前两个 + 后两个都是新增）
- [ ] 5.2 改 `frontend/src/api/index.js`：新增 `inviteCodeApi = { list: (params) => api.get('/invite-codes', {params}), create: () => api.post('/invite-codes'), remove: (id) => api.delete(`/invite-codes/${id}`) }`
- [ ] 5.3 改 `frontend/src/api/index.js`：`portfolioApi` 扩 `batch(data)` 方法；现有 `fundApi/buyerApi/sellerApi/...` 在调用处透传 `?user_id=N` + `?portfolio_id=N`（不改这些 API 对象本身——透传在组件层）
- [ ] 5.4 改 `frontend/src/router/index.js`（:27 后）：加 `/signup` 路由（`meta: { public: true, title: '注册' }`）
- [ ] 5.5 改 `frontend/src/router/index.js`（Layout children 末尾）：加 `/profile` 路由（`meta: { title: '个人中心', requiresAuth: true, sort: 100 }`）
- [ ] 5.6 改 `frontend/src/stores/auth.js`：加 `impersonatedByAdmin: boolean` 字段；加 `setImpersonation(targetUser)` / `clearImpersonation()` 导出
- [ ] 5.7 改 `frontend/src/components/Layout.vue`：顶栏 submenu（:49-55）改 `el-dropdown`：
  - admin 看到：display_name + 角色 tag + 「以自己身份查看」下拉（v-if isAdmin）+ 退出登录
  - user 看到：display_name + 角色 tag + 个人中心（跳 /profile）+ 退出登录
  - 下拉项：「回到自己（admin）」+ 启用 user 列表（v-for 来自 userApi.getUsers）
- [ ] 5.8 改 `frontend/src/components/Layout.vue` iconMap（:116-135）：加 `'/profile': User`
- [ ] 5.9 **手动 smoke**: 跑 `npm run dev`，登录 admin → 顶栏看到「以自己身份查看」下拉 → 选 user B → 顶栏变「以 lily 身份查看」+ 切回自己

---

### 6. 前端视图（Profile / Signup / UserManage 邀请码 tab）

**Effort Estimate**: Medium

**目标**: 2 个新视图 + UserManage.vue 加 tab。

#### Sub-tasks:
- [ ] 6.1 新建 `frontend/src/views/Profile.vue`（design §6.1）：
  - 3 段 el-card：账号信息（el-descriptions）/ 改昵称 / 改密码
  - 表单用 `reactive` + `ref(loading)` + `try/catch/finally`（参考 Login.vue:24-97 模式）
  - 改昵称：调 `authApi.updateMe({display_name})` → 成功 `setAuthUser({...auth.user, display_name: new})`
  - 改密码：调 `authApi.updateMe({old_password, new_password})` → 清表单
  - 校验：display_name 2-32 / new_password ≥ 8 / confirm_password == new_password
- [ ] 6.2 新建 `frontend/src/views/Signup.vue`（design §6.2）：
  - 居中卡片 `max-width: 420px`（**不**照抄 Login.vue 金库门视觉）
  - 邀请码 input `style="text-transform: uppercase;"` + `maxlength=8`
  - 提交调 `authApi.signup({invite_code, username, display_name, password})` → `setAuthUser(res.user)` → `router.push('/')`
  - 校验：invite_code `/^[a-zA-Z0-9]{8}$/` / username 4-20 / display_name 2-32 / password ≥ 8 / confirm == password
- [ ] 6.3 改 `frontend/src/views/UserManage.vue`：用 `<el-tabs v-model="activeTab">` 包现有内容；现有内容进 `<el-tab-pane name="users" label="用户列表">`
- [ ] 6.4 改 `frontend/src/views/UserManage.vue`：加 `<el-tab-pane name="invites" :label="`邀请码 (${inviteCount})`">`：
  - 表格：邀请码（monospace 样式）+ 状态（active/used/expired/disabled 4 圆点色，design §6.3 CSS）+ 生成时间 + 过期时间 + 操作（复制 / 禁用）
  - 「+ 生成新邀请码」按钮：调 `inviteCodeApi.create()` → `ElMessageBox.alert` 大号 monospace 卡片（design §7.1）+ 刷新列表
  - 复制：先 `navigator.clipboard.writeText(row.code)`，catch fallback `document.execCommand('copy')` + `ElMessage.success('已复制')`
  - 禁用：`ElMessageBox.confirm` 二次确认 → 调 `inviteCodeApi.remove(id)`
  - 状态判定函数 `inviteStatus(row)`（design §7.3）：del_flag==='0' → 'disabled' / used_at → 'used' / expires_at<now → 'expired' / else 'active'
- [ ] 6.5 改 `frontend/src/views/UserManage.vue`：删除 user 按钮加 `ElMessageBox.confirm` 二次确认（说明「软删」语义 + 数据保留）
- [ ] 6.6 **手动 smoke**（npm run dev）：
  - 登出 admin → 访问 `/signup` → 输邀请码 + 新 user 信息 → 注册成功跳首页
  - admin 登录 → `/profile` → 改昵称 → 顶栏 display_name 同步刷新
  - admin 登录 → `/system/users` → 邀请码 tab → 生成新码 → 复制 → 列表出现 active 状态
  - admin 切到 user B 视角 → 访问 `/portfolio` → 只看到 user B 持仓
  - 切回自己 → 切回 admin 视角

---

### 7. 全量回归 + 文档

**Effort Estimate**: Small

**目标**: 零回归 + 文档更新 + 部署产物。

#### Sub-tasks:
- [ ] 7.1 跑 `cd data-crawler && python3 -m pytest tests/ -q` 全量通过（30+ 现有 + 19 新 case = 50+ case）
- [ ] 7.2 跑 `cd frontend && npm run build` 通过；产物含新视图（dist/assets/ 下有 Profile / Signup / UserManage chunk）
- [ ] 7.3 跑老 admin 登录回归：
  - `prd-fund-seller` 的 curl 例子 → 仍能成功卖出（admin 看全表）
  - `prd-position-analysis` 的 admin 调用 → 仍能查分析数据
- [ ] 7.4 改 `docs/deployment.md`：追加「多用户部署」章节，含：
  - 迁移脚本执行步骤（先停 web → 跑 08_add_user_id_to_business_tables.sql → 启 web）
  - admin 首次生成邀请码的操作流程
  - 软删 user 数据保留说明
- [ ] 7.5 提交 `frontend/dist/` 到版本库（CLAUDE.md 前端构建门禁）；commit message 含 `frontend` + `dist` 双标签
- [ ] 7.6 **最终验收**:
  - `tasks/prd-multi-user.md` AC-1 到 AC-7 逐条 ✓
  - `tasks/design-multi-user.md` 一致性 checklist 10/10 ✓
  - 本任务清单 7 个父任务 + 所有子任务勾选 ✓

---

## Notes

### 依赖顺序（强制）
1. **Task 1 必须先做**：conftest 业务 storage mock 是 Task 3/4 测试可跑的前提
2. **Task 2 在 Task 3 之前**：SQL 迁移是 storage 改字段的前提
3. **Task 3 在 Task 4 之前**：storage 改字段是 API 路由调用的前提
4. **Task 5 + 6 可并行**：前端基础设施 + 视图可分别由前端开发者并行
5. **Task 7 最后**：所有前 6 个完成后做全量回归

### TDD 节奏（每子任务执行顺序）
1. 写测试用例（明确预期 + 边界）
2. 写实现代码
3. 跑 `python3 -m pytest tests/<file>.py -q` 通过
4. 勾选该子任务

### 风险与缓解
- **DDL 不可中断**：Task 2.7 真 DB 跑迁移必须在开发环境；生产部署步骤写进 docs/deployment.md
- **admin 切换下拉需要后端 session 配合**：Task 4.2（require_auth 钩子改）必须在 Task 5.7（前端下拉 UI）之前完成
- **sp_insert_fund_buyer_by_change 加 p_user_id 是 breaking change**：所有调用方（仅 api_server.py:1393）必须同步改
- **backup_position_daily_snapshot 改 SELECT 段是 critical**：不改正向迁移完所有 snapshot.user_id 都是 NULL → 后续按 user 过滤快照全漏
- **新 storage `__init__.py` export 漏**：Task 3.3 单独成子任务；否则 `from ..storage import InviteCodeStorage` 报 ImportError
- **conftest 业务 storage mock 不全**：Task 1.3 列了 14 个 storage，漏一个就一个测试炸——验收时跑全量 50+ case 是兜底

### 不在本任务范围（PRD 第 5 节非目标）
- 用户自助注册（必须邀请码）— Task 6.2 实现的是邀请码注册，符合 PRD
- 密码找回邮件
- 2FA / 短信验证
- 跨 user 共享 portfolio
- 审计日志（system_log 仍全局，不区分 user 操作）
- 数据导出
- 密码策略（无最低长度 / 复杂度要求，下版本再说）— Task 6.1 给了 ≥ 8 位是给 client 看的，存储 hash 无要求
- portfolio 共享 / 邀请查看
- 多 portfolio 隔离（仅单 portfolio 隔离，user 多 portfolio 通过现有 portfolio 表 user_id 字段支持）
