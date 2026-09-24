# Design: Playwright 网页抓取解析器(fund-web-scraper)

**Feature slug**: `fund-web-scraper`

> 架构设计文档。配套 PRD 见 `tasks/prd-fund-web-scraper.md`。本次交付范围:架构 + 可运行骨架(仅基本概况跑通)。

## 1. 设计约束(已与用户锁定)

- 独立 Docker 浏览器服务:微软官方 `mcr.microsoft.com/playwright` 镜像 + CDP server 模式。
- 连接:长连复用,browser 常驻单例 + page 临时(用完关),按 Playwright 官方推荐。
- 环境:mac 本地不装浏览器,开发与部署统一连远程 Docker 浏览器服务,配置仅差地址。
- 与现有 parser 并行:不动 `fund_parser.py`、`kc_index_parser.py`。
- 触发:仅手动触发,复用现有 `POST /api/task/run/<task_func>`;**注册 task_registry 但不插 task_schedule**(不被 cron 调度)。
- 依赖版本:`playwright==1.49.x`(倒数第二稳定版思路),与镜像 tag 对齐。

## 2. 选定方案:方案 A - 薄客户端 + 官方镜像 CDP server

应用进程(scheduler)仅装 playwright 驱动包,浏览器全在独立容器。`PlaywrightClient` 单例管理长连 browser,page 用完即关。`FundWebParser` 沿用现有 parser 的 `fetch`+`_parse` 两层范式。

(方案 B browserless 镜像、方案 C 应用内嵌浏览器已排除,分别因违背"官方镜像"与"独立服务"决策。)

## 3. 整体架构

```
┌─────────────────────────────────────────────────────────┐
│  fund-crawler 镜像(scheduler 进程)                      │
│  [仅加 playwright pip 包,不加浏览器二进制]               │
│                                                          │
│  app/utils/playwright_client.py  (新)                   │
│    PlaywrightClient 单例(参照 DatabaseManager)          │
│    - 惰性 init:connect_over_cdp(PLAYWRIGHT_CDP_URL)     │
│    - browser 常驻 / page 临时(with 上下文)              │
│    - get_browser() / new_page() 便捷访问器               │
│                                                          │
│  app/parser/fund_web_parser.py  (新)                    │
│    FundWebParser                                         │
│    - fetch(fund_code): 取 HTML(走 PlaywrightClient)     │
│    - _parse(html): 纯函数,BeautifulSoup 解析            │
│                                                          │
│  app/task/fetch_fund_detail_task.py  (新)               │
│    编排 parser -> storage -> DB(手动触发)               │
└───────────────────────┬─────────────────────────────────┘
                        │ CDP / WebSocket (9222)
┌───────────────────────▼─────────────────────────────────┐
│  browser 服务(独立容器)                                 │
│  image: mcr.microsoft.com/playwright:v1.49.0-noble      │
│  command: npx playwright run-server --port 9222         │
│  expose 9222 / 接入 fund-network / healthcheck          │
└─────────────────────────────────────────────────────────┘
```

## 4. 目录结构(新增/改动)

```
data-crawler/
├── app/
│   ├── parser/
│   │   ├── __init__.py              [改] 导出 FundWebParser
│   │   ├── fund_parser.py           [不动]
│   │   ├── kc_index_parser.py       [不动]
│   │   └── fund_web_parser.py       [新] FundWebParser + FundWebData
│   ├── utils/
│   │   ├── playwright_client.py     [新] 单例 browser 管理(参照 db.py)
│   │   └── ...(db.py/logger.py 不动)
│   └── task/
│       ├── register_task.py         [改] 注册 fetch_fund_detail_task
│       └── fetch_fund_detail_task.py[新] 编排 task
├── tests/
│   ├── test_fund_web_parser.py      [新] TDD:_parse 纯函数 + mock client
│   └── fixtures/
│       └── fundf10_basic.html       [新] 录制的 fundf10 基本概况 HTML
├── requirements.txt                 [改] +playwright==1.49.x
├── .env / .env.example              [改] +PLAYWRIGHT_CDP_URL
└── docker-compose.yml               [改] +browser 服务
```

## 5. 核心组件设计

### 5.1 PlaywrightClient 单例(app/utils/playwright_client.py)

参照 `app/utils/db.py` 的 `DatabaseManager`(L20-134:`__new__` 单例 + 惰性 init + `os.getenv` + 模块级实例 + 便捷 accessor)。

```python
class PlaywrightClient:
    _instance = None
    def __new__(cls): ...                 # 单例
    def __init__(self):
        if self._initialized: return
        self._playwright = None
        self._browser = None
    def _ensure_connected(self):          # 惰性 init,连接断开时重连
        # playwright.start(); connect_over_cdp(os.getenv('PLAYWRIGHT_CDP_URL'))
    def new_page(self):                   # 上下文管理,page 临时用完关
        ...
    def close(self): ...

playwright_client = PlaywrightClient()    # 模块级实例,进程内复用
def get_browser(): return playwright_client
```

- **生命周期**:browser 常驻(随进程);page 每次 `new_page()` 创建、`with` 退出关闭。
- **容错**:`_ensure_connected` 检测连接状态,断开则重连;异常捕获记录日志,不中断主流程(参照 `run_with_trace_context` 思想)。
- **CDP 地址**:`os.getenv('PLAYWRIGHT_CDP_URL', '')`,空则报错提示未配置。

### 5.2 FundWebParser(app/parser/fund_web_parser.py)

参照 `FundParser._parse_js_content`(fund_parser.py:44,吃 content 字符串的纯函数)与 `KcIndexParser`(按参数构造实例)。

```python
@dataclass
class FundWebData:
    fund_code: str
    fund_name: str
    fund_type: str
    establish_date: str
    fund_manager: str
    fund_size: float
    # 持仓明细 / 阶段涨幅 / 费率信息 字段后续阶段补

class FundWebParser:
    FUND_F10_URL = "https://fundf10.eastmoney.com/jbgk_{code}.html"
    def fetch(self, fund_code: str) -> Optional[FundWebData]:
        html = self._fetch_html(fund_code)       # 走 PlaywrightClient.new_page()
        return self._parse(html, fund_code) if html else None
    def _fetch_html(self, fund_code) -> Optional[str]: ...
    def _parse(self, html: str, fund_code: str) -> Optional[FundWebData]:
        # 纯函数:BeautifulSoup 解析,无外部依赖,可独立测试
```

- **两层分离**:`_fetch_html`(薄,依赖 PlaywrightClient)+ `_parse`(纯函数,可单测)。与现有两个 parser 的范式一致,便于 TDD 在边界 mock。

### 5.3 fetch_fund_detail_task(app/task/fetch_fund_detail_task.py)

参照 `fetch_kc50_index_task.py` 编排模式:实例化 parser/storage -> 调 parser -> 字段映射 -> 调 storage 写库 -> try/except/finally 关闭。

```python
def fetch_fund_detail_task(force_run=False):
    parser = FundWebParser()
    storage = FundInfoStorage()
    try:
        fund_codes = storage.get_all_fund_codes()
        for code in fund_codes:
            data = parser.fetch(code)
            if data:
                storage.<update_method>(<mapped_dict>)  # 复用或扩展
    except Exception as e:
        logger.error(...)
    finally:
        storage.close()
```

- **手动触发路径**:在 `register_task.py` 加 `scheduler.register_task('fetch_fund_detail_task', fetch_fund_detail_task)`(进入 task_registry,**不**往 `task_schedule` 表插行 -> 不被 cron 调度)。`/api/task/run/fetch_fund_detail_task` 经 web 转发 scheduler 的 `run_job_now` 触发。

### 5.4 docker-compose 新增 browser 服务

```yaml
  browser:
    image: mcr.microsoft.com/playwright:v1.49.0-noble   # 固定 tag
    command: ["npx", "playwright", "run-server", "--port", "9222"]
    expose:
      - "9222"
    networks:
      - fund-network
    healthcheck:
      test: ["CMD", "node", "-e", "require('http').get('http://localhost:9222/json/version',r=>process.exit(r.statusCode===200?0:1)).on('error',()=>process.exit(1))"]
      interval: 30s
      timeout: 5s
      retries: 3
    restart: unless-stopped
  scheduler:
    environment:
      - PLAYWRIGHT_CDP_URL=http://browser:9222
    depends_on:
      - browser
```

> **技术验证点(实现阶段首要)**:`mcr.microsoft.com/playwright` 镜像的 CDP server 启动命令(`npx playwright run-server` vs 自写 Node 脚本 vs `--browser-type`)需按实际镜像版本验证。骨架第一步先跑通"容器起来 + CDP `/json/version` 能连"。

## 6. 数据流(骨架:基本概况)

```
POST /api/task/run/fetch_fund_detail_task
  -> web scheduler_proxy.run_task -> scheduler /internal/task/run
  -> cron_scheduler.run_job_now('fetch_fund_detail_task')
  -> fetch_fund_detail_task()
     -> FundWebParser.fetch(code)
        -> PlaywrightClient.new_page() -> goto fundf10 -> content() 取 HTML -> 关 page
        -> _parse(html) -> FundWebData
     -> FundInfoStorage 更新 fund_info(复用/扩展 update 方法)
```

## 7. 后续字段落库规划(架构预留,本次不实现)

| 字段类 | 落库目标 | 改动 |
|--------|---------|------|
| 基本概况(本次) | fund_info | 复用 `update_fund_net_value` 或扩展;可能 `sql/alter/` 加列(基金规模等) |
| 持仓明细 | 新表 fund_holdings | 新 struct + 新 Storage |
| 阶段涨幅 | 新表 fund_performance | 新 struct + 新 Storage |
| 费率信息 | fund_info 加列 或 新表 | 视字段量定 |

## 8. 测试策略(TDD)

- **`_parse` 纯函数**:喂 `tests/fixtures/fundf10_basic.html` 录制 fixture,断言解析出正确字段。无需浏览器。
- **`fetch`**:mock `PlaywrightClient`(MagicMock,参照现有 mock Storage 范式 conftest.py:48),验证调用链与异常处理。
- **`PlaywrightClient`**:测单例惰性 init、page 用完关闭、连接断开重连的 mock 行为,不连真实浏览器。
- 框架:pytest(项目既有),`pythonpath = .`(pytest.ini)。

## 9. 关键决策记录

- 选方案 A:应用镜像保持轻量,浏览器隔离故障,符合双进程隔离理念。
- browser 常驻 + page 临时:平衡资源与隔离,官方推荐。
- 注册 registry 不插 task_schedule:零新增接口复用 `/api/task/run/`,且天然不被 cron 调度。
- `_parse` 纯函数分离:契合现有 parser 范式与项目"边界 mock"测试范式。
- 官方镜像 CDP server 启动方式列为首要技术验证点。

## 10. 端到端验证状态(已通过)

代码、单元测试、端到端验证全部通过:

**browser 服务(自定义镜像方案)**:
- 微软官方 `mcr.microsoft.com/playwright:v1.49.1-noble` 镜像**不适合直接做 CDP server**:chrome headless 的 `--remote-debugging-address=0.0.0.0` 不生效(CDP 只绑容器内 127.0.0.1),且镜像无 playwright Node 包、无 socat。
- 改用**自定义镜像** `fund-browser:latest`(`Dockerfile.browser` + `browser-entrypoint.sh`):基于微软镜像加装 socat,chrome 监听 127.0.0.1:9223,socat 把 0.0.0.0:9222 转发到 127.0.0.1:9223,使容器外可访问 CDP。
- compose 的 browser 服务用 `ports: "9222:9222"`(本地开发,scheduler 在宿主机跑时用 `http://127.0.0.1:9222`)+ 接入 fund-network(生产,scheduler 在另一容器时用 `http://browser:9222`)。两种形态都支持。

**端到端验证结果**:
1. ✅ `docker compose up browser` 起容器,`curl http://127.0.0.1:9222/json/version` 返回 Chrome/131。
2. ✅ Python `playwright.connect_over_cdp('http://127.0.0.1:9222')` 连接成功,抓取真实 fundf10 页面(标题/HTML 正确)。
3. ✅ `FundWebParser.fetch('011613')` 端到端:抓取+解析出基金简称/类型/成立日期/经理/净资产规模(53.82亿元)。
4. ✅ HTTP 触发 `/internal/task/run/fetch_fund_detail_task`:从真实库读 23 只基金,**全部抓取成功(23/23,0 失败)**,总耗时约 25 秒。
5. ✅ `fetch_fund_detail_task` 在 task_registry 注册但 task_schedule 无行,确认"可手动触发、不被 cron 调度"。

**本地/生产 CDP 地址切换**(`.env` / `.env.example` 注释已说明):
- 本地开发:scheduler 在宿主机跑,browser 容器 `ports: 9222:9222` 映射,`PLAYWRIGHT_CDP_URL=http://127.0.0.1:9222`。
- 生产:web/scheduler/browser 三容器同 compose,scheduler 经 fund-network,`PLAYWRIGHT_CDP_URL=http://browser:9222`。

**reviewer 已修复的高危问题**:
- `run-server`(WS 协议)与 `connect_over_cdp`(CDP 协议)不匹配 -> 改用 chromium 二进制 `--remote-debugging-port` + socat。
- `fetch_fund_detail_task` 的 `storage.close()` 调用不存在的方法致任务必崩 -> 已删除(FundInfoStorage 无 close,内部方法自管 session)。
- 连接失效不重连 -> `_ensure_connected` 已加 `is_connected()` 检查 + `new_page` 失败重连一次。
