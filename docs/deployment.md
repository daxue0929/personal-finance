# 部署文档

本文档记录 personal-finance 在服务器上的完整部署过程，含 Playwright 浏览器服务的部署细节与踩坑记录。

## 架构概览

Docker Compose 部署三个容器，同在 `fund-network` bridge 网络：

| 容器 | 镜像 | 端口 | 职责 |
|------|------|------|------|
| `fund-crawler-web` | `fund-crawler:latest`（本地构建） | 5000（对外） | Flask CRUD + 控制接口转发 |
| `fund-crawler-scheduler` | `fund-crawler:latest` | 5001（仅容器内） | APScheduler + 爬虫 + Playwright 抓取 + 内部控制 Flask |
| `fund-crawler-browser` | `fund-browser:latest`（本地构建） | 9222（CDP，对外+容器间） | Playwright 浏览器服务（chrome + node 代理） |

- web/scheduler 共用 `fund-crawler` 镜像（`data-crawler/Dockerfile`），仅启动命令不同。
- browser 是独立镜像（`data-crawler/Dockerfile.browser`），基于微软官方 `mcr.microsoft.com/playwright` + node 代理。
- scheduler 经 `http://browser:9222` 连 browser 容器抓取网页。

## 首次部署

### 1. 准备服务器环境

- Docker + Docker Compose
- MySQL 实例可访问（外部或同机）
- 能联网拉基础镜像（python:3.12-slim、mcr.microsoft.com/playwright）

### 2. 拉取代码

```bash
git clone <repo> personal-finance
cd personal-finance/data-crawler
```

### 3. 配置 `.env`（服务器本地，不入库）

复制 `.env.example` 为 `.env`，填实际值：

```bash
cp .env.example .env
vi .env
```

关键字段：

| 字段 | 服务器值 | 说明 |
|------|---------|------|
| `MYSQL_HOST` | 实际 MySQL 地址 | |
| `MYSQL_PASSWORD` | 实际密码 | |
| `SECRET_KEY` | 随机值 | `python -c "import secrets; print(secrets.token_urlsafe(48))"` 生成 |
| `PLAYWRIGHT_CDP_URL` | `http://browser:9222` | scheduler 在容器内，经 fund-network 用容器名访问 browser |

> **本地开发**时 `PLAYWRIGHT_CDP_URL=http://127.0.0.1:9222`（scheduler 在宿主机跑，browser 容器靠 `ports: 9222:9222` 映射）。见下文「本地开发」。

### 4. 创建 `/etc/timezone` 文件（重要，否则容器起不来）

三个容器都 bind mount `/etc/timezone`。CentOS 等系统默认**没有**这个文件，Docker 会把它当目录创建，导致挂载失败报错：

```
error mounting "/etc/timezone" ... not a directory: ... trying to mount a directory onto a file
```

服务器执行一次：

```bash
# 若 /etc/timezone 是误建的目录，先删
rm -rf /etc/timezone
# 建成文件
echo "Asia/Shanghai" > /etc/timezone
ls -l /etc/timezone   # 确认是文件（-rw-r--r--），不是目录（drwxr-xr-x）
```

### 5. 构建镜像

```bash
# 应用镜像（web/scheduler 共用）
./deploy.sh    # 会构建 fund-crawler:latest 并启动

# 或单独构建：
docker build -t fund-crawler:latest .

# browser 镜像（独立，首次必须构建）
docker build -f Dockerfile.browser -t fund-browser:latest .
```

> **架构注意**：`fund-browser` 镜像必须在**目标服务器上构建**（产出 amd64）。不要把 Mac（arm64）上构建的镜像传到 x86 服务器，会报 `platform (linux/arm64) does not match (linux/amd64)`。服务器能联网，直接在上面 build 即可。

### 6. 启动

```bash
docker compose up -d
docker compose ps    # 三个容器都 Up，browser 为 healthy
```

## 验证部署

### 容器状态

```bash
docker compose ps
# 期望：web/scheduler Up，browser Up (healthy)
```

### browser CDP 可达（从 scheduler 容器内）

```bash
docker exec fund-crawler-scheduler python3 -c 'import urllib.request as u; r=u.urlopen("http://browser:9222/json/version",timeout=5); print("status",r.status); print(r.read()[:120])'
# 期望：status 200，返回含 "Browser": "Chrome/131..."
```

### 触发 Playwright 抓取任务

`fetch_fund_detail_task` 注册在 task_registry 但**不在 task_schedule 表**（仅手动触发，不被 cron 调度）。通过 web 接口触发：

```bash
# 1. 登录拿 cookie
curl -s -c ./cookie.txt -X POST http://localhost:5000/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"你的密码"}'

# 2. 触发任务（同步接口，23 只基金约 30-40 秒返回，可加 & 后台跑）
curl -s -b ./cookie.txt -X POST http://localhost:5000/api/task/run/fetch_fund_detail_task
# 期望：{"success":true,"message":"任务 fetch_fund_detail_task 已触发"}

# 3. 看抓取日志
docker compose logs --tail 60 scheduler | grep "抓取成功\|基金详情抓取完成"
# 期望：每只基金 "抓取成功" + "基金详情抓取完成: 成功 23 只, 失败 0 只"
```

抓取日志也会写入 `system_log` 表，前端「系统日志」页面可查（按 trace_id 串联某次抓取的完整链路）。

## browser 服务的实现细节（踩坑记录）

browser 容器用自定义镜像 `fund-browser:latest`（`Dockerfile.browser` + `browser-entrypoint.sh`），不是直接用微软官方镜像。原因：chrome headless 有三个限制，导致容器间（scheduler 连 `browser:9222`）连接失败。

### 限制 1：chrome 只绑 127.0.0.1

`--remote-debugging-address=0.0.0.0` 在 chrome headless 下不生效，CDP 只监听容器内 127.0.0.1。容器外（scheduler 容器）直连不上。

**解法**：chrome 监听 127.0.0.1:9223，用 node 代理监听 0.0.0.0:9222 转发到 9223。

### 限制 2：chrome 拒绝非 localhost 的 Host 头

chrome 131 的 `/json/version` 端点有 DNS rebinding 防护，拒绝 Host 头非 localhost 的请求（返回 500）。scheduler 连 `http://browser:9222` 时 Host 是 `browser:9222`，被拒。

**解法**：node 代理转发时把 Host 头改写成 `127.0.0.1:9223`。

### 限制 3：webSocketDebuggerUrl 写死 9223

`/json/version` 返回的 `webSocketDebuggerUrl` 是 `ws://127.0.0.1:9223/...`，playwright 拿到后直连 9223（仅容器内可达），从 scheduler 连失败。

**解法**：node 代理对 `/json/version` 响应做 body 改写，把 `ws://127.0.0.1:9223/...` 换成 `ws://<请求方Host>:9222/...`，playwright 改连 9222（代理），代理转发 WebSocket 到 9223。

综上，`browser-entrypoint.sh` 用 node HTTP 反向代理同时解决三个限制。本地（arm64）与服务器（amd64）均验证 `connect_over_cdp` 抓取通过。

## 本地开发

本地开发时 scheduler/web 在宿主机命令行跑（不在容器里），browser 容器单独跑。详见 `.claude/skills/service-starter`。

| 项 | 本地开发 | 服务器部署 |
|----|---------|-----------|
| scheduler/web | 宿主机 `python -m app.scheduler` / `app.web` | 容器 |
| browser | 容器（`docker compose up -d browser`） | 容器 |
| `PLAYWRIGHT_CDP_URL` | `http://127.0.0.1:9222`（ports 映射） | `http://browser:9222`（同 network） |
| web/scheduler 端口 | 5001/5002（5000 被 AirPlay 占） | 5000/5001 |

本地 `.env` 的 `PLAYWRIGHT_CDP_URL` 设 `http://127.0.0.1:9222`；服务器 `.env` 设 `http://browser:9222`。`.env` 不入库，各环境独立维护。

## 更新部署

`./deploy.sh` 的行为:重建 web/scheduler 容器(应用镜像变了),**不重启 browser**(镜像/配置不变,保持运行不中断抓取)。

### 常规更新(改了后端代码 / 前端 dist)

```bash
cd data-crawler
git pull
./deploy.sh
# web/scheduler 重建生效；browser 保持运行不动
```

前端改动已在本地 `npm run build` 并提交 `dist/`,服务器 `git pull` 即含,`./deploy.sh` 重建 web 容器后生效。

### 何时需要单独重启 browser

browser 容器默认不随 `./deploy.sh` 重启。仅以下情况需单独操作:

```bash
# 1. 改了 Dockerfile.browser 或 browser-entrypoint.sh：需重建镜像 + 重启容器
docker build -f Dockerfile.browser -t fund-browser:latest .
docker compose up -d --force-recreate browser

# 2. browser 容器异常（chrome 崩溃 / CDP 无响应）：重启容器
docker compose restart browser

# 3. 改了 docker-compose.yml 的 browser 服务配置：重建该容器
docker compose up -d --force-recreate browser
```

> 注意:`docker compose restart browser` 会重启 chrome,正在进行的抓取会中断(任务执行记录会因后台线程异常记 FAILED,下次触发恢复)。常规部署不会触发此情况。

### 完全重建所有容器(慎用)

```bash
docker compose down       # 停止并移除所有容器（含 browser）
./deploy.sh               # 重新启动（browser 会被 no-recreate 逻辑重新拉起，因已 down）
```

`docker compose down` 会停 browser,之后 `./deploy.sh` 的 `--no-recreate browser` 检测到容器不存在会重新创建。仅在需要清理网络/卷时用。

## 常见问题

### 容器起不来：`/etc/timezone` 挂载失败
见「首次部署」第 4 步，`echo "Asia/Shanghai" > /etc/timezone` 建成文件。

### browser 镜像架构不匹配（arm64 vs amd64）
在服务器上直接 `docker build -f Dockerfile.browser`，不要传 Mac 构建的镜像。

### scheduler 连 browser 报 500 / `This does not look like a DevTools server`
browser 镜像未更新到 node 代理版。`git pull` 后重建 `fund-browser:latest` 并 `docker compose up -d browser`。

### `/api/task/run/fetch_fund_detail_task` 卡住
该接口同步执行，23 只基金约 30-40 秒返回。可加 `&` 后台触发，或直接看 `docker compose logs scheduler`。

### 抓取日志在哪看
写入 `system_log` 表，前端「系统日志」页面可查；或 `docker compose logs scheduler | grep 抓取成功`。

## 指数基础表（index-basic-table）部署

PRD: `tasks/prd-index-basic-table.md` / Design: `tasks/design-index-basic-table.md` / Tasks: `tasks/tasks-index-basic-table.md`

本特性引入 `index_basic` 元表 + 单条 `fetch_all_indexes_task` 统一抓取任务，配套 6 路由 CRUD + `IndexBasic.vue` 管理页 + 8月5日 `index_info.index_name` 丢失 bug 修复。

### 部署步骤（DBA 手动跑 SQL + 后端代码拉取）

1. **拉取新代码**（含新后端 + 新前端 dist）：

   ```bash
   cd /path/to/personal-finance
   git pull
   ```

2. **运行 SQL 脚本**（按顺序，幂等）：

   ```bash
   # a) 建 index_basic 元表 + 初始 4 条数据
   mysql -h 117.72.53.38 -u root -p personal-finance < sql/alter/06_create_index_basic.sql

   # b) 新增 fetch_all_indexes_task + 禁用 4 条老任务
   mysql -h 117.72.53.38 -u root -p personal-finance < sql/alter/07_migrate_index_tasks_to_loop.sql
   ```

3. **回填历史空 name 行**（仅 8月5/8月6 受影响，**可选**，否则这两天的 `index_info.index_name` 仍显示空 / `IndexInfo.vue` 表格显示 `—`）：

   ```sql
   UPDATE index_info a
   JOIN (
     SELECT index_code, index_name
     FROM index_info
     WHERE del_flag='1' AND index_name IS NOT NULL AND index_name <> ''
     GROUP BY index_code, index_name
     ORDER BY index_code, MAX(trade_date) DESC
   ) b ON a.index_code = b.index_code
   SET a.index_name = b.index_name
   WHERE a.del_flag='1' AND (a.index_name IS NULL OR a.index_name = '');
   ```

   兜底逻辑已让未来新抓取的行**自动**带 name（4 道兜底：入参 > index_basic > INDEX_NAME_MAP > 历史），所以回填只补 8月5/6 那 2 天历史。

4. **重建 web/scheduler 容器**（让新代码生效）：

   ```bash
   cd data-crawler
   ./deploy.sh    # 重建 fund-crawler:latest 并重启 web/scheduler
   ```

5. **手动触发一次统一抓取**（验证全链路）：

   ```bash
   # 1. 登录
   curl -s -c ./cookie.txt -X POST http://localhost:5000/api/login \
     -H "Content-Type: application/json" \
     -d '{"username":"admin","password":"你的密码"}'

   # 2. 触发 fetch_all_indexes_task
   curl -s -b ./cookie.txt -X POST http://localhost:5000/api/task/run/fetch_all_indexes_task

   # 3. 看日志
   docker compose logs --tail 60 scheduler | grep "统一指数遍历抓取"
   # 期望：成功 4/4 支

   # 4. 看 index_info 当天 name 不再空
   docker exec mysql_8 mysql -uroot -proot personal-finance -e "
     SELECT trade_date, index_code, index_name
     FROM index_info
     WHERE trade_date = CURDATE() AND del_flag='1'
     ORDER BY index_code;
   "
   # 期望：4 行全有中文名
   ```

### 部署后验证清单

```sql
-- 1. index_basic 4 行初始数据
SELECT * FROM index_basic WHERE del_flag='1';
-- 期望：4 行（000300/000688/000698/399673）

-- 2. task_schedule 状态：4 老 enabled=0, 1 新 enabled=1
SELECT task_func, COUNT(*), SUM(enabled)
  FROM task_schedule
 WHERE task_func LIKE 'fetch_index_task_%' OR task_func='fetch_all_indexes_task'
 GROUP BY task_func;
-- 期望：5 行，老 4 条 enabled=0，新 1 条 enabled=1

-- 3. fetch_all_indexes_task cron 正确
SELECT task_func, cron_expression, enabled
  FROM task_schedule WHERE task_func='fetch_all_indexes_task';
-- 期望：cron='0 9 * * 1-5', enabled=1
```

### 回滚步骤

如新方案有问题（4 道兜底异常 / ThreadPool 抓取失败 / 管理页 bug 等），一键回老 4 条任务驱动：

```sql
UPDATE task_schedule SET enabled=1, update_by='rollback', update_time=NOW()
 WHERE task_func LIKE 'fetch_index_task_%' AND del_flag='1';
UPDATE task_schedule SET enabled=0, update_by='rollback', update_time=NOW()
 WHERE task_func='fetch_all_indexes_task' AND del_flag='1';
```

回滚后**老 4 条 `INDEX_TASK_REGISTRY` wrapper 仍保留**（PRD §3 §7 + tasks §T3.4），立即可调度生效，不需重新部署。

### 注意事项

- **不要**直接 DELETE `index_basic` 行的 `del_flag` 检查：项目无外键约束，软删后 `index_info` 历史行不会自动清理（这是设计如此，符合「软删保留历史」约定）
- **不要**手动改 `fetch_all_indexes_task` 的 cron 表达式绕过 `task_schedule` 哈希比对：调度器 60s 内会自动热加载新 cron
- **新增指数**走前端 `/index/basic` 管理页（无需 DBA 改代码）：填 `index_code` + `market` + `index_name` + `enabled=1` 即可，下次 `fetch_all_indexes_task` 自动抓
