---
name: "service-starter"
description: "Manages project startup workflow including environment detection, dependency checking, port cleanup, and service launch for frontend and backend."
---

# Service Starter

## Overview

This skill provides a complete project startup workflow for the personal-finance project. It handles environment detection, dependency checking, port management, and service verification.

## Constants

| Item | Value |
|------|-------|
| Project Root | `/Users/wangxuedi/open_source/personal-finance` |
| Frontend Directory | `${PROJECT_ROOT}/frontend` |
| Backend Directory | `${PROJECT_ROOT}/data-crawler` |
| Frontend Port | `3000` |
| Backend Port | `5001` |
| Conda Env Name | `personal-finance` |
| Conda Python Path | `/opt/anaconda3/envs/personal-finance/bin/python3` |
| Venv Path | `${BACKEND_DIR}/venv/bin/activate` |
| Required Node Version | `>= 20.0.0` |

## Environment Options

### Python Environment

| Option | Type | Python Path | Activation |
|--------|------|-------------|------------|
| A (Recommended) | Conda | `/opt/anaconda3/envs/personal-finance/bin/python3` | `conda run -n personal-finance` |
| B | venv | `${BACKEND_DIR}/venv/bin/python3` | `source ${BACKEND_DIR}/venv/bin/activate` |

### Node Environment
- **Recommended**: Node.js >= 20.0.0
- **Tool**: nvm (Node Version Manager)

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

#### Backend - Python Environment Detection
```bash
cd ${BACKEND_DIR}

if conda env list | grep -q "personal-finance"; then
    echo "Using Conda environment: personal-finance"
    PYTHON_PATH=${CONDA_PYTHON_PATH}
elif [ -f "${VENV_PATH}" ]; then
    echo "Using venv environment: ${VENV_PATH}"
    PYTHON_PATH="${BACKEND_DIR}/venv/bin/python3"
else
    echo "No Python environment found. Please set up the environment first."
    exit 1
fi
```

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
    if [[ "$PYTHON_PATH" == *"anaconda3"* ]]; then
        conda run -n personal-finance pip install -r requirements.txt
    else
        source ${VENV_PATH} && pip install -r requirements.txt
    fi
}
```

### Step 3: Port Cleanup

```bash
echo "Cleaning up ports..."
lsof -ti:3000 | xargs kill -9 2>/dev/null
lsof -ti:5001 | xargs kill -9 2>/dev/null
sleep 1
```

### Step 4: Start Services

#### Start Frontend
```bash
cd ${FRONTEND_DIR} && npm run dev
```

#### Start Backend
```bash
cd ${BACKEND_DIR} && ${PYTHON_PATH} -m app.main --port 5001 --debug
```

### Step 5: Verify Startup

#### Frontend Verification
- Wait 3-5 seconds
- Check terminal output for Vite dev server URL
- Visit http://localhost:3000 in browser

#### Backend Verification (choose one)
- Check terminal output for "服务已启动" message
- Call API: `curl http://localhost:5001/health` - expected: `{"service": "fund-crawler", "status": "ok2"}`
- Call API: `curl http://localhost:5001/api/funds` - expected: JSON response with fund data

## Setup (First Time Only)

### Prerequisites
- nvm installed for Node.js management
- Conda or Python 3.10+ installed for backend

### Frontend Setup
```bash
source ~/.nvm/nvm.sh
nvm install 22
nvm alias default 22
cd ${FRONTEND_DIR} && npm install --no-audit
```

### Backend Setup

#### Option A: Conda Environment (Recommended)
```bash
conda create -n personal-finance python=3.10 -y
conda run -n personal-finance pip install -r ${BACKEND_DIR}/requirements.txt
```

#### Option B: Virtual Environment (venv)
```bash
cd ${BACKEND_DIR} && python3 -m venv venv
source ${BACKEND_DIR}/venv/bin/activate && pip install -r requirements.txt
```

## Notes

- **Only clean ports BEFORE starting service**, never after
- Backend entry point: `python3 -m app.main`
- Required dependencies: `requests`, `pandas`, `sqlalchemy`, `pymysql`, `beautifulsoup4`, `flask`, `apscheduler`, `python-dotenv`
- If port is occupied by system service (e.g. AirPlay on macOS using 5000), use alternative port 5001
- Use `&` for background running if needed: add `&` at end of command
- Database configuration is read from `.env` file in the data-crawler directory

## Troubleshooting

### nvm Not Found in Subshell
**Symptom**: `command not found: nvm`  
**Fix**: Source nvm before using:
```bash
source ~/.nvm/nvm.sh
```

### Node Version Too Low
**Symptom**: `vite: command not found` or npm install fails  
**Fix**: Switch to Node >= 20:
```bash
source ~/.nvm/nvm.sh
nvm use 22
```

### Conda Cache Corruption
**Symptom**: `CondaVerificationError` when creating environment  
**Fix**:
```bash
conda clean --all -y
```

### Conda Activate Not Working in Subshell
**Symptom**: `CondaError: Run 'conda init' before 'conda activate'`  
**Fix**: Use absolute Python path instead of `conda activate`:
```bash
/opt/anaconda3/envs/personal-finance/bin/python3 -m app.main --port 5001 --debug
```

### Port Already in Use
**Fix**: Kill the process occupying the port:
```bash
lsof -ti:<port> | xargs kill -9 2>/dev/null
```

### Dependencies Missing
**Fix**: Reinstall dependencies:
```bash
# Frontend
cd ${FRONTEND_DIR} && npm install --no-audit

# Backend (Conda)
conda run -n personal-finance pip install -r requirements.txt

# Backend (venv)
source venv/bin/activate && pip install -r requirements.txt
```

### Database Connection Failed
**Check**: Verify `.env` file has correct database credentials  
**File**: `${BACKEND_DIR}/.env`
