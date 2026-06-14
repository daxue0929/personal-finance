---
name: "port-manager"
description: "Manages port cleanup and service startup for frontend and backend. Invoke when user asks to start/restart frontend (port 3000) or backend (port 5001) services."
---

# Port Manager

## Overview

This skill provides automated port management for starting/restarting development services in the personal-finance project. It ensures clean port availability before service startup and verifies successful launch.

## When to Invoke

Invoke this skill when:
- User asks to start/restart frontend service
- User asks to start/restart backend service
- User asks to start/restart any service
- Before running any command that starts a web server

## Frontend Service (Port 3000)

### Workflow

1. **Check and kill port 3000**
```bash
lsof -ti:3000 | xargs kill -9 2>/dev/null
```

2. **Start frontend service**
```bash
cd /Users/wangxuedi/open_source/personal-finance/frontend && npm run dev
```

3. **Verify startup**
- Wait 3-5 seconds
- Check terminal output for Vite dev server URL
- Or visit http://localhost:3000 in browser

## Backend Service (Port 5001)

### Workflow

1. **Check and kill port 5001**
```bash
lsof -ti:5001 | xargs kill -9 2>/dev/null
```

2. **Start backend service**
```bash
cd /Users/wangxuedi/open_source/personal-finance/data-crawler && source venv/bin/activate && python3 -m app.main --port 5001 --debug
```

3. **Verify startup** (choose one)
- Check terminal output for "服务已启动" message
- Call API: `curl http://localhost:5001/api/funds`
- Check response contains fund data

## Important Notes

- **Only clean ports BEFORE starting service**, never after
- Backend uses virtual environment: `venv/bin/activate`
- Backend entry point: `python3 -m app.main`
- If port is occupied by system service (e.g. AirPlay on macOS using 5000), use alternative port 5001
- Always verify service is running by checking logs or calling API
- Use `&` for background running if needed: add `&` at end of command

## Complete Examples

### Start Frontend
```bash
lsof -ti:3000 | xargs kill -9 2>/dev/null; cd /Users/wangxuedi/open_source/personal-finance/frontend && npm run dev
```

### Start Backend
```bash
lsof -ti:5001 | xargs kill -9 2>/dev/null; cd /Users/wangxuedi/open_source/personal-finance/data-crawler && source venv/bin/activate && python3 -m app.main --port 5001 --debug
```

### Start Both (in background)
```bash
# Terminal 1 - Backend
lsof -ti:5001 | xargs kill -9 2>/dev/null; cd /Users/wangxuedi/open_source/personal-finance/data-crawler && source venv/bin/activate && python3 -m app.main --port 5001 --debug &

# Terminal 2 - Frontend
lsof -ti:3000 | xargs kill -9 2>/dev/null; cd /Users/wangxuedi/open_source/personal-finance/frontend && npm run dev
```
