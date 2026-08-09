---
name: "service-starter"
description: "Manages project startup workflow including environment detection, dependency checking, port cleanup, and service launch for frontend and backend."
---
# Service Starter

## Overview

This skill provides a complete project startup workflow for the personal-finance project. It handles environment detection, dependency checking, port management, and service verification.

> 本项目后端是**双进程架构**（web + scheduler），不是单进程。技能按真实架构编写，启动时需起 3 个服务：scheduler、web、frontend。

## Constants

| Item | Value |
|------|-------|
| Project Root | `/Users/wangxuedi/open_source/personal-finance` |
| Frontend Directory | `${PROJECT_ROOT}/frontend` |
| Backend Directory | `${PROJECT_ROOT}/data-crawler` |
| Frontend Port | `3000` |
| Web Port (local dev) | `5001` |
| Scheduler Port (local dev) | `5002` |
| Venv Python Path | `${BACKEND_DIR}/venv/bin/python3`（Python 3.12） |
| Venv Activate | `source ${BACKEND_DIR}/venv/bin/activate` |
| Conda Env Name | `personal-finance` |
| Conda Python Path | `/opt/anaconda3/envs/personal-finance/bin/python3` |
| Required Node Version | `>= 20.0.0` |

> 后端 Python 环境支持 **venv** 与 **Conda** 两种，按本机实际选择（见 Environment Detection）。不同开发机可能用不同环境，二者均完整支持。

## Architecture（双进程）

服务拆分后，两个独立后端进程通过 HTTP 内部转发通信，故障隔离。

| 进程 | 启动命令 | 本地端口 | 职责 |
|------|---------|---------|------|
| web | `python -m app.web --port 5001` | 5001（对外，契合 Vite 代理）| Flask CRUD + 控制接口转发 |
| scheduler | `python -m app.scheduler --port 5002` | 5002（仅内部）| APScheduler + 爬虫 + 内部控制 Flask |
| frontend | `npm run dev` | 3000 | Vue 3 + Vite，`/api` 代理到 localhost:5001 |

- web 进程不持有 scheduler 实例，控制类接口（`/api/status`、`/api/start`、`/api/stop`、`/api/task/run/<func>`）通过 `app/web/scheduler_proxy.py` 转发到 scheduler 进程的 `/internal/*` 接口。
- web 转发目标由环境变量 `SCHEDULER_INTERNAL_URL` 决定（默认 `http://scheduler:5001`，本地开发需设为 `http://localhost:5002`）。
- scheduler 崩溃时，web 的 CRUD 接口仍可用，控制接口返回 502。
- **鉴权**：所有 `/api/*` 接口需登录（`@app.before_request` 校验 session），仅 `/api/login` 与非 `/api` 路径（如 `/health`）放行。

### 为什么本地 web 用 5001、scheduler 用 5002

- **5000 被 macOS AirPlay Receiver（ControlCenter）占用**，web 起不来。
- **Vite 代理硬编码 `/api -> localhost:5001`**（`frontend/vite.config.js` 的 `devApiBaseUrl`）。若 web 不在 5001，前端调 `/api` 全部 404。
- 因此本地 web 必须 5001（契合 Vite 代理），scheduler 让出 5001 改用 5002，web 通过 `SCHEDULER_INTERNAL_URL=http://localhost:5002` 转发。
- 生产部署不受影响：Docker 内 web 5000 / scheduler 5001，Nginx 反代 `/prod-api -> web:5000`。
- **回归规范端口选项**：关掉「系统设置 -> 通用 -> 隔空播放接收器」释放 5000，并把 `vite.config.js` 的 `devApiBaseUrl` 改成 `http://localhost:5000`，即可让 web 用 5000、scheduler 用 5001。

## When to Invoke

Invoke this skill when:
- User asks to start the project
- User asks to start/restart frontend service
- User asks to start/restart backend service
- User asks to start/restart any service
- Setting up the project on a new machine
- Before running any command that starts a web server

## Startup Workflow

### Step 1: Environment Detection

#### Frontend - Node Version Check
```bash
source ~/.nvm/nvm.sh

echo "Available Node versions:"
nvm list

CURRENT_NODE=$(node --version | cut -d'v' -f2)
REQUIRED_MAJOR=20
CURRENT_MAJOR=$(echo $CURRENT_NODE | cut -d'.' -f1)

if [ "$CURRENT_MAJOR" -lt "$REQUIRED_MAJOR" ]; then
    echo "Current Node version v$CURRENT_NODE is below required v$REQUIRED_MAJOR.x"
    echo "Trying to find and switch to a compatible version..."
    
    COMPATIBLE_VERSION=$(nvm list | grep -E "v2[0-9]" | tail -1 | tr -d ' ->')
    if [ -n "$COMPATIBLE_VERSION" ]; then
        nvm use $COMPATIBLE_VERSION
    else
        echo "No compatible Node version found. Please install Node >= 20."
        exit 1
    fi
else
    echo "Node version v$CURRENT_NODE is compatible (>= v$REQUIRED_MAJOR.x)"
fi
```

#### Backend - Python Environment Detection（venv 或 Conda，谁存在用谁）
```bash
cd ${BACKEND_DIR}

if [ -f "${BACKEND_DIR}/venv/bin/python3" ]; then
    echo "Using venv environment: ${BACKEND_DIR}/venv"
    PYTHON_PATH="${BACKEND_DIR}/venv/bin/python3"
elif conda env list 2>/dev/null | grep -q "personal-finance"; then
    echo "Using Conda environment: personal-finance"
    PYTHON_PATH="/opt/anaconda3/envs/personal-finance/bin/python3"
else
    echo "No Python environment found. Please set up the environment first (see First Time Setup)."
    exit 1
fi
```

> 不同机器可能用不同环境：venv（本机 `data-crawler/venv`）或 Conda（环境名 `personal-finance`）。检测脚本自动选用存在的那个。

### Step 2: Dependency Checking

#### Frontend Dependencies
```bash
cd ${FRONTEND_DIR}

if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install --no-audit
else
    echo "Frontend dependencies already installed"
fi
```

#### Backend Dependencies
```bash
cd ${BACKEND_DIR}

${PYTHON_PATH} -c "import requests; import pandas; import sqlalchemy; import pymysql; import bs4; import flask; import apscheduler; import dotenv; print('All backend dependencies OK')" 2>&1 || {
    echo "Installing backend dependencies..."
    if [[ "$PYTHON_PATH" == *"venv"* ]]; then
        source ${BACKEND_DIR}/venv/bin/activate && pip install -r requirements.txt
    else
        conda run -n personal-finance pip install -r requirements.txt
    fi
}
```

### Step 3: Port Cleanup（启动前清理）

```bash
echo "Cleaning up ports..."
lsof -ti:3000 | xargs kill -9 2>/dev/null
lsof -ti:5001 | xargs kill -9 2>/dev/null
lsof -ti:5002 | xargs kill -9 2>/dev/null
sleep 1
```

> **注意**：不要清理 5000--它被 macOS AirPlay 占用，kill 掉会影响系统功能。本地 web 用 5001 规避。

### Step 4: Start Services（按顺序：scheduler -> web -> frontend）

三个进程默认前台阻塞，需后台运行（`run_in_background` / 末尾加 `&` / 各开一个终端）。

#### 4.1 启动 scheduler 进程（先起，web 的控制接口依赖它）
```bash
cd ${BACKEND_DIR} && ${PYTHON_PATH} -m app.scheduler --port 5002
```

#### 4.2 启动 web 进程（设 SCHEDULER_INTERNAL_URL 指向 scheduler）
```bash
cd ${BACKEND_DIR} && SCHEDULER_INTERNAL_URL=http://localhost:5002 ${PYTHON_PATH} -m app.web --port 5001
```

#### 4.3 启动前端
```bash
cd ${FRONTEND_DIR} && npm run dev
```

> **scheduler 进程会按 `task_schedule` 表跑爬虫任务**（基金净值更新 `*/30 * * * *`、科创50/100 指数抓取 `* 9-15 * * mon-fri` 等）。**默认连本地库**（`.env` 的 `MYSQL_HOST`，本仓库 `.env` 已配 `127.0.0.1`）。若不想触发爬虫只想调试前端/CRUD，可**只起 web + frontend**（跳过 4.1），登录与 CRUD 不依赖 scheduler，仅控制类接口会 502。

### Step 5: Verify Startup

等待 5-8 秒后逐项检查：

#### 前端
- 终端输出 Vite dev server URL
- `curl -s -o /dev/null -w "HTTP %{http_code}" http://localhost:3000/` -> `HTTP 200`
- 浏览器访问 http://localhost:3000

#### scheduler 进程（5002）
- `curl -s -o /dev/null -w "HTTP %{http_code}" http://localhost:5002/` -> `HTTP 404`（**正常**：只暴露 `/internal/*`，根路径 404 说明控制服务在线）
- 终端日志出现「调度器内部控制服务已启动，等待 web 进程连接」与各任务 cron 注册记录

#### web 进程（5001）
- `curl -s http://localhost:5001/health` -> `{"service":"fund-crawler","status":"ok2"}`（`/health` 非 `/api` 路径，不需登录）
- `curl -s -o /dev/null -w "HTTP %{http_code}" http://localhost:5001/api/funds` -> `HTTP 401`（**正常**：`/api/*` 需登录，未登录返回 401 `{"error":"未登录或登录已过期"}` 说明鉴权生效，不是故障）
- 端到端验证 web->scheduler 转发：需先登录（UI 登录或 POST `/api/login` 拿 session cookie），再调 `/api/status`

## First Time Setup

### Prerequisites
- nvm（Node.js 版本管理）
- Python 3.12（后端）
- MySQL 实例可访问（配置在 `${BACKEND_DIR}/.env`）

### Frontend Setup
```bash
source ~/.nvm/nvm.sh
nvm install 22
nvm alias default 22
cd ${FRONTEND_DIR} && npm install --no-audit
```

### Backend Setup

二选一，按团队/机器习惯选用。两台机器可用不同环境，不影响启动（检测脚本自动识别）。

#### Option A: venv
```bash
cd ${BACKEND_DIR} && python3 -m venv venv
source ${BACKEND_DIR}/venv/bin/activate && pip install -r requirements.txt
```

#### Option B: Conda
```bash
conda create -n personal-finance python=3.12 -y
conda run -n personal-finance pip install -r ${BACKEND_DIR}/requirements.txt
```

### Database
MySQL 外部实例。表结构在 `sql/struct/`，存储过程在 `sql/program/`，变更脚本在 `sql/alter/`。连接配置在 `${BACKEND_DIR}/.env`。

## Production Deploy（Docker）

```bash
cd ${BACKEND_DIR} && ./deploy.sh
docker compose ps
docker compose logs -f web
docker compose logs -f scheduler
```

生产端口：web 5000（对外映射）、scheduler 5001（仅容器内网络，不对外映射）。Nginx 反代 `/prod-api -> web:5000`。

## Notes

- **Only clean ports BEFORE starting service**, never after
- 后端双入口：`python -m app.web`（web 进程）、`python -m app.scheduler`（scheduler 进程），**无 `app.main`**
- web 进程支持 `--debug`（默认关闭）；scheduler 进程支持 `--check-interval`（任务配置检查间隔，默认 10s），无 `--debug`
- 后端 Python 环境：venv 与 Conda 均完整支持，检测脚本谁存在用谁（venv 优先），不同机器可不同
- Required dependencies：`requests`、`pandas`、`sqlalchemy`、`pymysql`、`beautifulsoup4`、`flask`、`apscheduler`、`python-dotenv`（见 `requirements.txt`）
- 5000 被 macOS AirPlay 占用 -> 本地 web 用 5001、scheduler 用 5002
- 数据库配置读自 `${BACKEND_DIR}/.env`
- 启动顺序：scheduler -> web（带 `SCHEDULER_INTERNAL_URL`）-> frontend

## Troubleshooting

### nvm Not Found in Subshell
**Symptom**: `command not found: nvm`  
**Fix**:
```bash
source ~/.nvm/nvm.sh
```

### Node Version Too Low
**Symptom**: `vite: command not found` 或 npm install 失败  
**Fix**:
```bash
source ~/.nvm/nvm.sh
nvm use 22
```

### Port Already in Use（3000/5001/5002）
**Fix**:
```bash
lsof -ti:<port> | xargs kill -9 2>/dev/null
```
> 不要 kill 5000（AirPlay 占用）。若必须用 5000，关掉「系统设置 -> 通用 -> 隔空播放接收器」。

### /api/* 返回 401「未登录或登录已过期」
**这是正常的**：auth 中间件保护所有 `/api/*`（仅 `/api/login` 放行）。未登录调 `/api/funds`、`/api/status` 等返回 401 说明鉴权生效，不是服务故障。验证 `/health`（不需登录）或先登录。

### 控制接口返回 502
**Symptom**: `/api/status`、`/api/start` 等 502  
**Cause**: web 进程的 `SCHEDULER_INTERNAL_URL` 指不到 scheduler，或 scheduler 未启动。  
**Fix**:
1. 确认 scheduler 已起且监听 5002：`lsof -nP -iTCP:5002 -sTCP:LISTEN`
2. 启动 web 时设 `SCHEDULER_INTERNAL_URL=http://localhost:5002`

### Conda Activate Not Working in Subshell
**Symptom**: `CondaError: Run 'conda init' before 'conda activate'`  
**Fix**: 用绝对 Python 路径，不用 `conda activate`：
```bash
/opt/anaconda3/envs/personal-finance/bin/python3 -m app.web --port 5001
```

### Conda Cache Corruption
**Symptom**: `CondaVerificationError` 创建环境时  
**Fix**:
```bash
conda clean --all -y
```

### Dependencies Missing
**Fix**:
```bash
# Frontend
cd ${FRONTEND_DIR} && npm install --no-audit

# Backend (venv)
source ${BACKEND_DIR}/venv/bin/activate && pip install -r requirements.txt

# Backend (Conda)
conda run -n personal-finance pip install -r requirements.txt
```

### Database Connection Failed
**Check**: `${BACKEND_DIR}/.env` 的 `MYSQL_HOST` / `MYSQL_USER` / `MYSQL_PASSWORD` 是否正确。  
**注意**：本仓库 `.env` 默认 `MYSQL_HOST=127.0.0.1`（本地库）。若要连生产库需自行改为 `117.72.53.38` 并提供生产密码——**不推荐本地开发直连生产**。

### scheduler 本地爬虫跑在本地库
**Symptom**: 不想触发爬虫却被 scheduler 跑了任务  
**Fix**: 只起 web + frontend（跳过 scheduler）。登录/用户管理/CRUD 不依赖 scheduler。
