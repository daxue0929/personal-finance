---
name: "port-manager"
description: "Manages ports for development services. Checks if a port is occupied, kills occupying processes, and reports results. Invoke when starting/restarting services to ensure clean port availability."
---

# Port Manager

## Overview

This skill provides port management capabilities for development environments. It helps ensure that services can start successfully by:

1. **Checking port occupancy** - Detects if a specified port is already in use
2. **Killing occupying processes** - Terminates processes that are using the target port
3. **Reporting results** - Provides clear feedback on what was done

## When to Invoke

**Invoke this skill when:**
- Starting a new service and wanting to ensure the port is available
- Restarting a service that may have left orphaned processes
- Getting "port already in use" errors
- Before running any command that starts a web server or similar service

## Usage

### 1. Check if a port is occupied

```bash
# Check port 5001
lsof -ti:5001
```

### 2. Kill processes on a specific port

```bash
# Kill all processes on port 5001
lsof -ti:5001 | xargs kill -9
```

### 3. Combined workflow (Recommended)

```bash
# Check and kill before starting service
lsof -ti:5001 | xargs kill -9 2>/dev/null; \
cd /path/to/project && \
source venv/bin/activate && \
python3 -m app.main --port 5001
```

## Commands Reference

| Command | Description |
|---------|-------------|
| `lsof -ti:<port>` | List process IDs using the specified port |
| `lsof -ti:<port> \| xargs kill -9` | Force kill all processes on the port |
| `netstat -tlnp \| grep <port>` | Alternative way to check port usage (Linux) |
| `ss -tlnp \| grep <port>` | Modern alternative to netstat |

## Examples

### Example 1: Starting backend service

```bash
# Step 1: Kill any processes on port 5001
lsof -ti:5001 | xargs kill -9 2>/dev/null

# Step 2: Navigate to project directory
cd /data-crawler

# Step 3: Activate virtual environment
source venv/bin/activate

# Step 4: Start the service in background mode (RECOMMENDED)
# 使用 & 后台运行，日志仍然显示在终端
python3 -m app.main --port 5001 --debug &
```

### Example 2: Starting frontend service

```bash
# Step 1: Kill any processes on port 3000
lsof -ti:3000 | xargs kill -9 2>/dev/null

# Step 2: Navigate to project directory
cd /frontend

# Step 3: Start the service in background mode (RECOMMENDED)
# 使用 & 后台运行，日志仍然显示在终端
npm run dev &
```

## Notes

- **Cross-platform**: On macOS/Linux, use `lsof`. On Windows, use `netstat` or PowerShell commands.
- **Error handling**: The `2>/dev/null` suppresses "no process found" errors when port is not occupied.
- **Root permissions**: Some systems may require `sudo` to kill certain processes.
- **Force kill**: The `-9` flag ensures immediate termination; use with caution.
- **Terminal reuse**: When restarting services, prefer reusing existing terminals instead of creating new ones:
  - First stop the running command using its command ID
  - Then restart the service in the same terminal
  - This keeps the workspace clean and organized

## Best Practices

### ⚠️ 重要警告：启动后不要检查端口

**错误做法：**
```bash
# ❌ 错误：启动服务后，又检查端口占用并杀死进程
lsof -ti:5001 | xargs kill -9 2>/dev/null
cd /data-crawler && source venv/bin/activate
python3 -m app.main --port 5001 --debug &
# ❌ 错误：启动成功后，又去检查端口占用
lsof -ti:5001 | xargs kill -9  # 这会杀死刚启动的服务！
```

**正确做法：**
```bash
# ✅ 正确：只在启动前检查和清理端口
lsof -ti:5001 | xargs kill -9 2>/dev/null  # 清理端口
cd /data-crawler && source venv/bin/activate
python3 -m app.main --port 5001 --debug &  # 启动服务
# ✅ 正确：启动后不再检查端口，服务正常运行
```

**核心原则：**
- ✅ **启动前**：检查端口占用，清理旧进程
- ❌ **启动后**：不要检查端口占用，不要杀死进程
- ✅ **验证启动**：可以通过访问服务或查看日志来验证，而不是检查端口占用

### 验证服务启动的正确方法

**不要使用端口检查来验证启动：**
```bash
# ❌ 错误：启动后检查端口占用
lsof -ti:5001  # 这会显示刚启动的进程，但容易误判
```

**推荐使用以下方法验证：**

**方法 1：访问服务**
```bash
# ✅ 正确：通过 HTTP 请求验证服务是否正常
curl http://localhost:5001/api/tasks
```

**方法 2：查看日志**
```bash
# ✅ 正确：查看终端日志输出
# 服务启动后会输出日志，如：
# "启动基金数据爬虫服务，端口 5001"
# "Cron 任务调度器已启动"
```

**方法 3：检查进程状态**
```bash
# ✅ 正确：检查进程是否在运行（但不杀死）
ps aux | grep python3 | grep app.main
```

### Terminal Management

When managing multiple services (frontend/backend), follow these guidelines:

1. **Track running terminals**: Keep track of which terminal is running which service
2. **Reuse terminals**: When restarting a service, stop the existing command first and reuse the same terminal
3. **Avoid orphan processes**: Always clean up ports before starting new services
4. **Centralized logs**: Keep related services in their dedicated terminals for easier log monitoring

### Service Restart Workflow

**正确的重启流程：**

```bash
# Step 1: 清理端口（启动前）
lsof -ti:5001 | xargs kill -9 2>/dev/null

# Step 2: 进入项目目录
cd /data-crawler

# Step 3: 激活虚拟环境
source venv/bin/activate

# Step 4: 启动服务
python3 -m app.main --port 5001 --debug &

# Step 5: 验证启动（不要检查端口）
# 方法 1：查看日志
# 方法 2：访问服务
curl http://localhost:5001/api/tasks
```

**错误的重启流程：**
```bash
# ❌ 错误：启动后又检查端口并杀死
lsof -ti:5001 | xargs kill -9 2>/dev/null
python3 -m app.main --port 5001 --debug &
lsof -ti:5001 | xargs kill -9  # ❌ 这会杀死刚启动的服务！
```

### Background Running Mode

For long-running services like web servers, use background mode to avoid blocking:

**推荐的后台运行方式：**

```bash
# 方法 1：使用 & 后台运行（推荐）
lsof -ti:5001 | xargs kill -9 2>/dev/null  # 清理端口
cd /data-crawler && source venv/bin/activate
python3 -m app.main --port 5001 --debug &  # 后台启动
# ✅ 启动后不要检查端口

# 方法 2：使用 nohup（持久运行）
lsof -ti:5001 | xargs kill -9 2>/dev/null  # 清理端口
cd /data-crawler && source venv/bin/activate
nohup python3 -m app.main --port 5001 --debug > /tmp/backend.log 2>&1 &
# ✅ 启动后不要检查端口

# 方法 3：完整流程（清理 + 启动 + 验证）
lsof -ti:5001 | xargs kill -9 2>/dev/null
cd /data-crawler && source venv/bin/activate
python3 -m app.main --port 5001 --debug &
# 验证启动（通过访问服务）
curl http://localhost:5001/api/tasks
```

**错误的后台运行方式：**
```bash
# ❌ 错误：启动后又检查端口
lsof -ti:5001 | xargs kill -9 2>/dev/null
python3 -m app.main --port 5001 --debug &
lsof -ti:5001  # ❌ 不要检查端口占用
lsof -ti:5001 | xargs kill -9  # ❌ 不要杀死刚启动的服务
```

### Example Terminal Organization

| Terminal | Service | Port |
|----------|---------|------|
| Terminal 1 | Backend API | 5001 |
| Terminal 2 | Frontend Dev | 3000 |
| Terminal 3 | Database | 3306 |

## Integration

This skill should be automatically invoked before starting any development server, web service, or process that requires a specific port. It ensures a clean state for service startup.
