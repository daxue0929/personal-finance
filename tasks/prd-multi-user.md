# PRD — 多用户隔离（multi-user）

**Feature slug**: `multi-user`
**前置依赖**：`prd-user-login.md` 已上线（UserStorage + Login.vue + UserManage.vue + admin_required 装饰器均已就位）

---

## 1. 背景

项目已有 `user` 表 + 登录态 + admin 装饰器（`prd-user-login.md` 范围），但**业务表无 `user_id` 隔离**——`fund_buyer` / `fund_seller` / `position` / `portfolio` / `position_daily_snapshot` / `fund_dip_plan` 等表所有用户共享同一份数据。User A 买入的基金，User B 看得到、User B 删了影响 User A。

现状盘点（基于本 PRD 探索结果）：

| 子系统 | 状态 |
|--------|------|
| User 表 + Storage | ✅ 已有完整 CRUD（`UserStorage`） |
| 登录 / 会话 | ✅ Cookie + Flask session（`@app.before_request require_auth`） |
| 角色装饰器 | ✅ `admin_required` 已有，挂 `meta.adminOnly` 路由 |
| User 管理页 | ✅ `UserManage.vue` 已有（admin 列表 + 增删改） |
| 业务表 `user_id` 字段 | ❌ **全无**——核心缺陷 |
| 业务 API 鉴权过滤 | ❌ **全无**——返回全表数据 |
| 个人中心 | ❌ 缺 |
| 邀请码机制 | ❌ 缺（admin 手动加 user） |

本 PRD 目标：**彻底改造为多用户模式**——业务表加 `user_id` 隔离 + 业务 API 加鉴权过滤 + 个人中心 + 邀请码注册 + 老数据归 admin。

---

## 2. 功能目标

| # | 目标 | 衡量方式 |
|---|------|----------|
| G1 | User A / User B 数据完全隔离 | 同一 fund_code 在 A、B 持仓数不同 |
| G2 | User 登录后只能看自己 portfolios / 交易 | API `/api/buyers` 等只返当前 user 数据 |
| G3 | Admin 可看全 / 改全 user | admin 角访问 API 自动忽略 user_id 过滤 |
| G4 | 老数据归属 admin（一次性迁移） | 跑 SQL 后 `fund_buyer.user_id` 全是 admin.id |
| G5 | 邀请码注册新 user | admin 生成 8 位 code → user `/signup` 注册成功 |
| G6 | User 删 → 软删，portfolio/交易保留 | admin 删 user 后数据仍可查（只读） |
| G7 | Profile 个人中心 | user 改自己昵称/密码 |

---

## 3. 用户故事

### US-1 User 隔离（核心）
> 作为 User B，我想登录后**只看到自己的** portfolios 和交易记录，这样不会误操作 User A 的数据。

### US-2 Admin 跨用户视图
> 作为 admin，我想**看全 / 改全** 任何 user 的数据，便于客服/调试；日常 user 的 UI 上 admin 仍可看自己数据，但有"切换 user"入口（admin-only）。

### US-3 邀请码注册
> 作为 User C（新人），我想用 admin 给我的**8 位邀请码**注册账号，不必 admin 手动一个个加。

### US-4 个人中心
> 作为已注册 user，我想**改自己的昵称和密码**，不必麻烦 admin。

### US-5 User 软删 + 恢复
> 作为 admin，我想**软删**一个 user（该 user 不能再登录）但**保留其历史交易**用于审计；误删可一键恢复。

### US-6 默认 portfolio
> 作为新注册 user，我想**自动获得一个默认 portfolio**（"默认组合"），不必先建 portfolio 才能录买入流水。

### US-7 老数据迁移
> 作为 admin，我想跑**一次 SQL 脚本**把所有历史数据的 user_id 设为 admin（我自己），新 user 看到的是空白起步。

---

## 4. 功能需求

### AC-1 数据模型（SQL 变更）

新增字段（10+ 张业务表全部加 `user_id` + `portfolio_id`）：

| 表 | 新字段 | 说明 |
|----|--------|------|
| `portfolio` | + `user_id BIGINT NOT NULL` | **新增**（现 ORM 字段无 user_id；migration 加列） |
| `fund_buyer` | + `user_id BIGINT NOT NULL` | 历史流水；与 portfolio 的关联通过生成的 position.user_id 推导，不冗余 |
| `fund_seller` | + `user_id BIGINT NOT NULL` | |
| `position` | + `user_id BIGINT NOT NULL` | 持仓主表；**不加 portfolio_id**（与 portfolio 的关系在 `portfolio_position` M-N 表里，position 本身是独立实体） |
| `position_daily_snapshot` | + `user_id BIGINT NOT NULL` | 快照表；同样不加 portfolio_id |
| `portfolio_position` | （**无 schema 变化**）| M-N 关联表 portfolio↔position；user 归属通过 portfolio_id / position_id 推导（双校验两端归属即可） |
| `fund_dip_plan` | + `user_id BIGINT NOT NULL` | 定投计划 |
| `fund_nav_history` | （**不动**）| 净值历史**整表共享**（前端 `/api/funds/history` 全局可查；user_id 字段无消费场景，省列） |
| `index_basic` | （共享只读，**不动**）| 指数元表 admin 维护 |
| `index_info` | （共享只读，**不动**）| 指数行情 admin 维护 |

新增表 `invite_code`：

```sql
CREATE TABLE invite_code (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  code VARCHAR(8) NOT NULL UNIQUE COMMENT '8 位 a-z 0-9 邀请码',
  created_by BIGINT NOT NULL COMMENT '生成该码的 user_id（admin）',
  expires_at DATETIME NOT NULL COMMENT '过期时间（生成时刻 +7 天）',
  used_at DATETIME NULL COMMENT '使用时间（NULL = 未用）',
  used_by BIGINT NULL COMMENT '使用者 user_id',
  del_flag CHAR(1) DEFAULT '1' COMMENT '1 正常 / 0 软删（admin 禁用）',
  create_time DATETIME DEFAULT NULL,
  update_time DATETIME DEFAULT NULL,
  KEY idx_code (code),
  KEY idx_expires (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

迁移脚本（`sql/alter/08_add_user_id_to_business_tables.sql`）：
- 步骤 1：所有业务表 `ADD COLUMN user_id BIGINT NULL`（先 NULL）
- 步骤 2：UPDATE `xxx.user_id = (SELECT id FROM user WHERE username='admin')`
- 步骤 3：所有业务表 `MODIFY COLUMN user_id BIGINT NOT NULL`
- 步骤 4：所有业务表 `ADD INDEX idx_user_id (user_id)`
- 步骤 5：建 `invite_code` 表
- 步骤 6（**关键**）：**改 MySQL 存储过程 `backup_position_daily_snapshot`**，snapshot.user_id 从 position 携带
  - 若存储过程不更新，snapshot.user_id 全 NULL → 权限校验失效
  - 同理 `sp_insert_fund_buyer_by_change`（quick-buy 走）也需 user_id 参数

### AC-2 后端 Storage

新增 `data-crawler/app/storage/invite_code_storage.py`：
- `create(admin_id, ttl_days=7) -> str`：生成 8 位 code + INSERT，返回 code
- `validate(code) -> Optional[dict]`：验证存在 + 未过期 + 未用 + 未软删，返回 invite 记录
- `mark_used(invite_id, user_id) -> bool`：置 `used_at` + `used_by`
- `list_by_admin(admin_id, include_used=True, include_expired=False)`：admin 看自己生成的所有邀请码

修改 `data-crawler/app/storage/portfolio_storage.py`：
- `create(data)`：必传 `user_id`（从 `g.user.id` 取）
- `get_portfolios_with_pagination(name, page, page_size, user_id=None)`：加 user_id 参数（None = admin 看全，user.id = user 看自己）
- `get_portfolio_by_id(portfolio_id)`：返回 ORM 对象，user 归属校验放到 API 层
- `get_portfolio_with_positions(portfolio_id)`：同上，user 归属校验放到 API 层

修改 `data-crawler/app/storage/fund_buyer_storage.py`（及 seller / position / snapshot / dip_plan 同模式）：
- `create(data)`：`user_id` 从 `g.user.id` 强制覆盖（不接受 body 传的 user_id）
- 所有 `get_xxx_with_pagination(...)`：加 `user_id=None` 参数（None = admin 全表 / user.id = user 看自己）
- `get_xxx_by_id(id)`：返回 ORM 对象，user 归属校验放到 API 层（避免 storage 层依赖 g.user）
- `update/delete(id, ...)`：API 层先 `get` 校验 `user_id == g.user.id`（admin 跳过），再调 storage 改
- `fund_seller.update_seller` 状态机防回退（line 1625-1630）必须在 user 归属校验**之后**调

修改 `data-crawler/app/storage/portfolio_position_storage.py`（关联表，无 schema 变化）：
- `create_portfolio_position(portfolio_id, position_id, ...)`：**双校验**——`portfolio_id` 属当前 user + `position_id` 属当前 user；任一不通过返 403
- `get_portfolio_positions(portfolio_id)`：先校验 `portfolio.user_id == g.user_id`（admin 跳过），不通过返 403
- `delete_portfolio_position(relation_id)`：先查 relation 拿到 portfolio_id + position_id，分别校验 user 归属
- admin 通过 `?impersonate_user_id=N` 可在 admin 视角操作任何 user 的关联

修改 `data-crawler/app/storage/portfolio_position_storage.py`（关联表，无 schema 变化）：
- `create_portfolio_position(portfolio_id, position_id, ...)`：**双校验**——`portfolio_id` 属当前 user + `position_id` 属当前 user；任一不通过返 403
- `get_portfolio_positions(portfolio_id)`：先校验 `portfolio.user_id == g.user_id`（admin 跳过），不通过返 403
- `delete_portfolio_position(relation_id)`：先查 relation 拿到 portfolio_id + position_id，分别校验 user 归属
- admin 通过 `?impersonate_user_id=N` 可在 admin 视角操作任何 user 的关联

### AC-3 后端 Task（注册流改造）

新建 `data-crawler/app/task/register_user_via_invite.py`（**避免与 `register_task.py` 命名冲突**）：
- `register_user_via_invite(invite_code, password, display_name) -> User`：
  1. `invite_code_storage.validate(code)` → 拿到 invite 记录
  2. 哈希密码 + `user_storage.create_user(...)` 创建 user
  3. `portfolio_storage.create(name='默认组合', user_id=new_user.id)`
  4. `invite_code_storage.mark_used(invite_id, new_user.id)`
  5. 返回 user 字典
  6. 全程 try/except + rollback（任何一步失败回滚 invite / user / portfolio）

### AC-4 后端 API

新增路由（`api_server.py`）：

| 路由 | 方法 | 鉴权 | 说明 |
|------|------|------|------|
| `/api/signup` | POST | 无（公开） | body `{invite_code, username, password, display_name}` → 自动登录 + session |
| `/api/invite-codes` | GET | admin | admin 看自己生成的所有邀请码 |
| `/api/invite-codes` | POST | admin | admin 生成新邀请码，返回 `{code, expires_at}` |
| `/api/invite-codes/<id>` | DELETE | admin | 软删（禁用）某邀请码 |
| `/api/me` | GET | 任意已登录 | 当前 user 信息（self-service） |
| `/api/me` | PUT | 任意已登录 | 改昵称 / 改密码（body 区分） |
| `/api/portfolios` | GET | 任意已登录 | 列表（user 看自己 / admin 看全 + 可 query user_id） |
| `/api/portfolios` | POST | 任意已登录 | 新建 portfolio（user_id 强制 g.user.id） |
| `/api/portfolios/<id>` | PUT/DELETE | 任意已登录 | 改/删（限自己） |
| `/api/portfolios/batch` | POST | admin | 批量取组合（**admin only**；前端 Dashboard 组合视角） |
| `/api/positions/snapshot/options` | GET | 任意已登录 | 快照持仓选项（按 user 过滤） |
| `/api/positions/snapshot/analysis` | GET | 任意已登录 | 持仓分析（按 user 过滤） |
| `/api/positions/snapshot/cost-index` | GET | 任意已登录 | 持仓成本-指数（按 user 过滤） |
| `/api/positions/snapshots` | GET | 任意已登录 | 快照分页（按 user 过滤） |
| `/api/tasks` | POST/PUT/DELETE | **加 admin_required** | 任务配置管理（现任何登录可改，加 admin 限制） |
| `/api/crawl` | POST | **加 admin_required** | 触发爬取（admin only） |
| `/api/task/run/<func>` | POST | **加 admin_required** | 手动跑 task（admin only） |
| `/api/start` `/api/stop` | POST | **加 admin_required** | 启停调度器（admin only） |
| `/api/funds` | POST/PUT/DELETE | **加 admin_required** | 基金 CRUD（admin only；user 只读） |
| `/api/logs` `/api/logs/<id>` `/api/logs/clean` | * | **加 admin_required** | 系统日志（admin only） |
| `/api/portfolio-board` `/api/portfolio-overview` | — | **不存在**（已合并到 `/api/portfolios/batch` + `/api/positions/snapshot/analysis`） | — |

修改路由（所有 `/api/funds/*` / `/api/buyers/*` / `/api/sellers/*` / `/api/positions/*` / `/api/snapshots/*` / `/api/dip-plans/*` / `/api/portfolio-positions/*`）：
- 增 query param `?user_id=N`（仅 admin 可传）
- 增 query param `?portfolio_id=N`（user/admin 均可传）
- list 类 API 自动加 `WHERE user_id = g.user.id`（admin 跳过）
- create 类 API 强制覆盖 body 里的 `user_id` 为 `g.user.id`（admin 可通过 `?impersonate_user_id` 改）

**`/api/portfolio-positions/*` 特殊**（多对多关联表）：
- 现有路由：`GET ?portfolio_id=N` / `POST` / `DELETE /<relation_id>`
- `POST` 必须传 `portfolio_id` + `position_id`，双校验两端都属当前 user
- `GET` 先校验 `portfolio_id` 属当前 user
- `DELETE` 校验 relation 关联的 portfolio 和 position 都属当前 user
- 任何 user 归属校验失败返 403 + `{error: "无权操作该 portfolio/position"}`

新增 `admin_required` 已在；扩展 `require_auth` 钩子不变。

### AC-5 前端

新增 `frontend/src/views/Profile.vue`：
- 显示当前 user 信息（username / display_name / role / create_time / 最后登录）
- 改昵称：`<el-input v-model>` + 保存
- 改密码：旧密码 + 新密码 + 确认 + 保存
- 路由 `/profile` + `meta.requiresAuth: true`

新增 `frontend/src/views/Signup.vue`：
- 邀请码输入（8 位，自动 uppercase）
- 用户名 + 密码 + 确认密码 + 昵称
- 提交后自动登录 + 跳首页
- 路由 `/signup` + `meta.requiresAuth: false`（公开）

修改 `frontend/src/views/UserManage.vue`：
- 加 "邀请码" tab：列表 + 生成按钮 + 复制 + 禁用
- "删除 user" 按钮：先 `ElMessageBox.confirm` 二次确认（说明"软删"）

修改 `frontend/src/router/index.js`：
- 新增 `/signup` + `/profile` 路由
- `/profile` 加 `meta.requiresAuth: true`

修改 `frontend/src/components/Layout.vue`（顶栏）：
- "用户"菜单项下加 "个人中心"（任何 user 可见）+ "退出"
- 已有 "用户管理"（admin only）保留

修改 `frontend/src/api/index.js`：
- `authApi.signup(data)`
- `authApi.me()` / `authApi.updateMe(data)`
- `inviteCodeApi.list()` / `create()` / `remove(id)`
- `portfolioApi.list()` / `create(data)` / `update(id, data)` / `remove(id)`
- 现有 `fundApi/buyerApi/sellerApi/...` 加 `?user_id=N` + `?portfolio_id=N` 透传

### AC-6 测试

新增 `data-crawler/tests/test_invite_code_storage.py`（5 case）：
- `test_create_generates_8_char_code`
- `test_validate_expired_returns_none`
- `test_validate_used_returns_none`
- `test_mark_used_sets_timestamp_and_user`
- `test_list_by_admin_filters_other_admins`

新增 `data-crawler/tests/test_register_user.py`（4 case）：
- `test_register_user_creates_user_portfolio_invite_used`
- `test_register_user_invalid_code_raises`
- `test_register_user_duplicate_username_raises`
- `test_register_user_rollback_on_portfolio_create_fail`

新增 `data-crawler/tests/test_multi_user_api.py`（10 case）：
- `test_user_a_cannot_see_user_b_buyers`
- `test_user_a_cannot_update_user_b_position`
- `test_admin_can_list_all_users_buyers_via_query`
- `test_user_cannot_associate_other_users_portfolio_position`（user A 不能把自己的 position 关联到 user B 的 portfolio）
- `test_user_cannot_see_other_users_portfolio_positions`（GET /api/portfolio-positions?portfolio_id=user_b_portfolio 返 403）
- `test_signup_creates_user_and_default_portfolio`
- `test_signup_with_invalid_code_returns_400`
- `test_invite_code_admin_only_endpoints`
- `test_me_endpoint_returns_current_user`
- `test_delete_user_soft_del_keeps_data`

修改 `data-crawler/tests/test_fund_buyer.py` / `test_fund_seller.py` / `test_position.py` / `test_portfolio.py`：fixture 加 `user_id`（默认 admin.id = 1）。

### AC-7 全量回归

- `cd data-crawler && python3 -m pytest tests/ -q` 全量通过（含新增 17 case）
- `cd frontend && npm run build` 成功
- 部署文档追加「多用户部署」章节
- **回归确认**：跑老 `prd-fund-seller` / `prd-position-analysis` 的 curl 例子（用 admin 登录），应能正常工作

---

## 5. 非目标

- **不**做用户自助注册（必须邀请码）
- **不**做密码找回邮件（admin 重置即可）
- **不**做 2FA / 短信验证（项目单实例、家庭 / 小团队场景）
- **不**做跨 user 共享 portfolio（user 看不到彼此）
- **不**做审计日志（system_log 仍全局，不区分 user 操作）
- **不**改 `index_basic` / `index_info` 共享数据
- **不**改 `fund_info` 共享数据
- **不**改 `fund_nav_history` 共享数据（整表共享，user_id 无消费场景）
- **不**做数据导出（user 自己导自己的）
- **不**改 admin 角色的额外子角色（super admin / audit admin 等）
- **不**改密码策略（无最低长度 / 复杂度要求，下版本再说）
- **不**做 user 的定投计划自动执行（task 全表扫描以 admin 身份跑，user 计划**不会**被自动执行；user 想跑就手录或 admin 代理）
- **不**做 portfolio 共享 / 邀请查看（每个 portfolio 完全私有）

---

## 6. 依赖

- `User` 表（已有）
- `UserStorage`（已有）
- Flask session + Cookie（已有）
- `werkzeug.security` scrypt（已有）
- 已有 `require_auth` + `admin_required` 装饰器
- 已有 14 个 PRDs 的功能（不能破坏）

---

## 7. 风险

| 风险 | 影响 | 缓解 |
|------|------|------|
| 迁移 SQL 漏表 | 部分数据 user_id=NULL，后续查询漏 | 迁移脚本显式列 8 张表 + `WHERE user_id IS NULL` 兜底检查 |
| 业务 API 改造漏路径 | 某接口没加 user_id 过滤，user 看到其他 user 数据 | 测试矩阵 17 case 覆盖；grep 现有 API 路径 + review |
| 软删 user 后交易表 user_id 仍指向 | 仍可查到（admin 故意设计的） | 软删行为与 admin 显式相关，admin 可查；user 不可登 |
| 邀请码 8 位空间碰撞 | 7 天 / 几千个码时碰撞概率 0.00001% | UNIQUE 约束兜底；重试 |
| 注册时 portfolio 创建失败 | 留下 user 无 portfolio | 整个注册流程包事务 + 失败回滚 user / invite |
| `g.user.id` 为空（未登录） | API 调用报 500 | 已有 `require_auth` 钩子保护；测试覆盖 |
| admin 误用 `impersonate_user_id` | 改了其他 user 数据 | 仅 admin 装饰器放行；UI 上 admin 显式"以 user X 身份"切换 |
| 性能：`WHERE user_id=N` 在大表上 | 大数据量查询慢 | 加 `idx_user_id` 复合索引；现有 `idx_*` 不删 |
| 老 session 在迁移后失效 | 旧 cookie 找不到 user（被软删的） | 迁移不动 user.del_flag='1' 的状态；旧 session 仍有效 |
| 邀请码泄露 | 被人注册 | 8 位 + 7 天 + 一次性已防；admin 可手动禁用 |

---

## 8. Open Questions

（已与用户澄清完，无遗留）

历史决策记录（实现时如发现冲突，优先按此表）：
- 范围：多 portfolio 隔离（user + portfolio 两层）
- 老数据：归 admin
- 鉴权：全范围护
- 面板：Profile + 邀请码
- 默认 portfolio：自动创建
- 删 user：软删 + 保留
- 访问控制：user 限自己，admin 看全
- 邀请码：8位 / 7天 / 一次性
