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

## 编码约定

- 后端日志用 `app.utils.logger`，通过 ContextVar 注入 `trace_id` 实现全链路追踪。API 用 `@log_request` 装饰器，定时任务用 `run_with_trace_context` 包装。
- Storage 类继承 `StorageBase`，`__init_subclass__` 自动给公共方法加日志装饰器。
- 调度器每 60 秒检查 `task_schedule` 表，通过 hash 比对检测配置变更并热加载。
- 软删除统一用 `del_flag='1'`（'1' 存在，'0' 已删除）。
- 时间统一用北京时间（`app.utils.datetime_utils.get_beijing_now`）。
- 前端 API 集中在 `src/api/index.js`，按业务模块导出（taskApi / fundApi / buyerApi / fundNavApi / logApi / portfolioApi）。

## 已知不足与演进方向

- 无物理外键约束，数据一致性依赖应用层
- position 表 current_value/profit_loss 冗余字段需应用层同步
- 单用户设计（无 user 表）
- system_log 无分区/归档策略
- ECharts 已引入前端但尚未使用
- `.env` 明文密码，建议改用 secrets 管理

演进方向：多用户支持 → 策略平台化 → 回测系统。
