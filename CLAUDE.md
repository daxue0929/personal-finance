# CLAUDE.md

本文件为 Claude Code 提供项目上下文。Claude Code 会在每次会话自动读取。

## 项目简介

个人基金定投管理系统。自动爬取基金/指数行情 → 智能定投（按涨跌幅策略）→ 持仓盈亏追踪 → 组合管理。

## 架构

前后端分离 + 后端双进程（2026-07 服务拆分）。

```
personal-finance/
├── data-crawler/     # 后端（Python 3.12）
│   ├── app/
│   │   ├── web/        # Web API 进程入口（python -m app.web）
│   │   ├── scheduler/  # 调度器进程入口（python -m app.scheduler）
│   │   ├── parser/     # 爬虫（东方财富基金净值、腾讯财经科创指数）
│   │   ├── task/       # 5 个业务任务
│   │   ├── storage/    # 9 个 Storage 类 ↔ 9 张表
│   │   └── utils/      # db 连接池 / logger（trace_id 链路）/ config / datetime
│   ├── Dockerfile
│   └── docker-compose.yml
├── frontend/        # 前端（Vue 3.4 + Vite 5 + Element Plus + ECharts）
│   └── src/
│       ├── api/       # axios 封装，按业务模块组织
│       ├── views/     # 6 个页面（portfolio/buyers/funds/history/logs/tasks）
│       ├── router/
│       └── components/
└── sql/             # MySQL 脚本
    ├── struct/       # 8 张表结构
    ├── program/      # 2 个存储过程（含智能定投逻辑）
    └── alter/        # 变更脚本
```

## 后端双进程

服务拆分后，两个独立进程通过 HTTP 内部转发通信，故障隔离。

| 进程 | 启动命令 | 端口 | 职责 |
|------|---------|------|------|
| web | `python -m app.web --port 5000` | 5000（对外）| Flask CRUD + 控制接口转发 |
| scheduler | `python -m app.scheduler --port 5001` | 5001（仅内部）| APScheduler + 爬虫 + 内部控制 Flask |

- web 进程不持有 scheduler 实例，控制类接口（`/api/status`、`/api/start`、`/api/stop`、`/api/task/run/<func>`）通过 `app/web/scheduler_proxy.py` 转发到 scheduler 进程的 `/internal/*` 接口。
- scheduler 崩溃时，web 的 CRUD 接口仍可用，控制接口返回 502。
- 两进程各自独立数据库连接池和日志队列，写同一张 `system_log` 表无冲突。

## 常用命令

### 后端（data-crawler/）

```bash
# 本地开发（两个终端）
source venv/bin/activate
python -m app.scheduler --port 5001                                    # 终端1
SCHEDULER_INTERNAL_URL=http://localhost:5001 python -m app.web --port 5000  # 终端2

# Docker 部署（构建 + 启动两个容器）
./deploy.sh
docker-compose ps
docker-compose logs -f web
docker-compose logs -f scheduler
```

### 前端（frontend/）

```bash
npm install
npm run dev      # 开发，端口 3000，/api 代理到 localhost:5001
npm run build    # 生产构建，输出 dist/（需提交到版本库，服务器 git pull 更新）
```

### 数据库

MySQL 外部实例。表结构在 `sql/struct/`，存储过程在 `sql/program/`，变更脚本在 `sql/alter/`。

## 技术栈

- **后端**：Python 3.12、Flask 3.1、APScheduler 3.11、SQLAlchemy 2.0、PyMySQL、requests、BeautifulSoup4
- **前端**：Vue 3.4、Vite 5、Element Plus 2.5、ECharts 5.5、Vue Router 4、Axios
- **数据库**：MySQL（8 张表：fund_info / fund_nav_history / fund_buyer / position / portfolio / portfolio_position / index_info / task_schedule / system_log）

## 开发规范

### 编辑规范

请遵循"最小化编辑"原则：
- 只修改必要的行，不要重写整个文件
- 不要重新排序已有内容
- 不要主动格式化代码
- 优先使用增量添加
- 除非我明确要求重构，否则请保持现有代码结构不变。

### 工作流程

- **功能开发**：遵守 `/feature-dev` 模式。按 Discovery → 代码库探索 → 澄清问题 → 架构设计 → 实现 → 质量审查 → 总结 的流程推进，不得跳过澄清问题和用户批准环节。
- **测试先行**：遵守 TDD（测试驱动开发）。先写测试用例（明确预期行为和边界），再写实现代码，最后跑通测试。禁止"先实现后补测试"。
- 禁止未经用户确认就进入实现阶段。
- **前端构建门禁（push 前必做）**：改动过 `frontend/src/` 下任意文件后，`git push` 前必须在 `frontend/` 目录执行 `npm run build` 重新构建，并把更新后的 `dist/` 一并提交。服务器靠 `git pull` 拿 `dist/` 部署，源码与 dist 不同步会导致线上跑旧前端。纯后端 / SQL / 文档改动不受此约束。

### Feature Development 强制子流程

执行 `/feature-dev` 时，附加以下强制步骤：

1. **PRD 生成**（Discovery 阶段）：必须先调用 `/create-prd` 输出结构化需求文档，明确功能目标、用户故事、验收标准。
2. **设计规范**（Architecture Design 阶段）：若涉及前端界面，必须先调用 `/frontend-design` 输出 `tasks/design-[feature].md`（`[feature]` 取 kebab-case 功能名，如 `design-fund-seller.md`），包含色彩、字体、组件规范。
3. **质量门禁**（Quality Review 阶段）：必须重点检查实现是否符合 `tasks/design-[feature].md` 规范，不符合则返工。

可用相关技能：`/create-prd`、`/generate-tasks`、`/implement-tasks`、`/frontend-design`。

### 命名约定

- **Python**：模块/变量用 `snake_case`，类用 `PascalCase`。Storage 类命名 `XxxStorage`，Task 函数命名 `xxx_task`。
- **Vue/JS**：组件文件用 `PascalCase`（如 `FundBuyer.vue`），变量/函数用 `camelCase`。API 对象命名 `xxxApi`（如 `fundApi`）。
- **数据库**：表名/字段名用 `snake_case`。布尔语义字段用 `del_flag`（'1' 存在，'0' 删除）、`enabled`（1/0）。
- **接口路径**：RESTful 风格，复数资源名（`/api/funds`、`/api/buyers`），统一返回 JSON。

### Python 后端规范

- 日志统一用 `app.utils.logger.logger`，通过 ContextVar 注入 `trace_id` 全链路追踪。API 用 `@log_request` 装饰器，定时任务用 `run_with_trace_context` 包装。
- Storage 类继承 `StorageBase`，`__init_subclass__` 自动加日志装饰器。Storage 实例在模块级创建（如 `app/web/api_server.py` 顶部），进程内复用。
- 时间统一用北京时间（`app.utils.datetime_utils.get_beijing_now`）。
- 调度器每 60 秒检查 `task_schedule` 表，通过 hash 比对检测配置变更并热加载。
- 新增定时任务：在 `app/task/` 实现函数 → 在 `app/task/register_task.py` 注册 → 在 `task_schedule` 表配置 cron。
- 新增数据表：在 `sql/struct/` 建表脚本 → 在 `app/storage/` 新增 Storage 类 → 在 `app/storage/__init__.py` 导出。
- 数据库变更用 `sql/alter/` 下的增量脚本，不直接修改 `struct/` 中的已发布脚本。
- 配置通过 `.env` + `os.getenv`，不硬编码。`.env` 不提交敏感密码（当前是明文，待改 secrets）。

### Vue 前端规范

- API 调用集中在 `src/api/index.js`，按业务模块导出 API 对象，不直接在组件里写 axios。
- 路由配置在 `src/router/index.js`，通过 `meta.sort` 控制菜单顺序，支持父子菜单。
- 状态在各页面组件内用 `ref`/`reactive` 局部管理（未用 Pinia/Vuex）。
- UI 用 Element Plus，图标通过 `iconMap` 映射路由。
- API 请求 baseURL：开发 `/api`（Vite 代理），生产 `/prod-api`（Nginx 反代）。
- **引入新依赖**：必须先检查与项目已有依赖的兼容关系（peerDependencies、版本冲突）。不使用最新版本，原则上使用倒数第二个稳定版；用户明确指定版本的除外。

### Git 提交规范

- 提交信息用中文，简洁描述"做什么"。
- 格式：`<类型>：<简述>`，类型如 `服务拆分`、`前端bug修改`、`开发相关`，或直接描述改动。
- 一个提交聚焦一个主题，不混合无关改动。
- 前端 `dist/` 构建产物需提交到版本库（服务器 git pull 更新）。
- **不要提交**：`venv/`、`node_modules/`、`__pycache__/`。

### 错误处理与日志

- API 接口统一 try/except，异常返回 `{error: message}` + 适当 HTTP 状态码。
- 爬虫任务异常不应中断调度器，由 `run_with_trace_context` 捕获并记录。
- 日志级别：INFO 记录正常流程，ERROR 记录异常。避免在生产开 DEBUG 级别日志。
- `system_log` 表支持 trace_id 链路查询，定位问题时优先用 trace_id 串联。

## 已知不足与演进方向

- 无物理外键约束，数据一致性依赖应用层
- position 表 current_value/profit_loss 冗余字段需应用层同步
- 单用户设计（无 user 表）
- system_log 无分区/归档策略
- ECharts 已引入前端但尚未使用
- `.env` 明文密码，建议改用 secrets 管理

演进方向：多用户支持 → 策略平台化 → 回测系统。
