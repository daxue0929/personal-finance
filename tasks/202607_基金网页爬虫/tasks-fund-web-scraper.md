# Task List: Playwright 网页抓取解析器(fund-web-scraper)

**Based on PRD**: `tasks/prd-fund-web-scraper.md`
**Based on Design**: `tasks/design-fund-web-scraper.md`

## Relevant Files

### Files to Create
- `data-crawler/app/utils/playwright_client.py` - PlaywrightClient 单例,browser 长连 + page 临时管理(参照 db.py DatabaseManager)
- `data-crawler/app/parser/fund_web_parser.py` - FundWebParser + FundWebData,fetch + _parse 两层
- `data-crawler/app/task/fetch_fund_detail_task.py` - task 编排 parser -> 打印(不落库)
- `data-crawler/Dockerfile.browser` - 自定义 browser 镜像(微软官方镜像 + socat)
- `data-crawler/browser-entrypoint.sh` - browser 服务启动脚本(chrome + socat 转发)
- `data-crawler/tests/test_fund_web_parser.py` - TDD 测试:_parse 纯函数 + mock client 测 fetch
- `data-crawler/tests/fixtures/fundf10_basic.html` - 录制的 fundf10 基本概况 HTML fixture

### Files to Modify
- `data-crawler/app/parser/__init__.py` - 导出 FundWebParser / FundWebData
- `data-crawler/app/task/register_task.py` - 注册 fetch_fund_detail_task(进 registry,不插 task_schedule)
- `data-crawler/requirements.txt` - 加 playwright==1.49.x
- `data-crawler/.env` 和 `data-crawler/.env.example` - 加 PLAYWRIGHT_CDP_URL
- `data-crawler/docker-compose.yml` - 新增 browser 服务 + scheduler 环境变量/depends_on

### Test Files
- `data-crawler/tests/test_fund_web_parser.py`(新建,见上)

## Implementation Tasks

### 1. 浏览器服务容器化与依赖配置
**Effort Estimate**: Medium

#### Sub-tasks:
- [x] 1.1 `requirements.txt` 加 `playwright==1.49.1`(倒数第二稳定版思路,与镜像 tag 对齐)
- [x] 1.2 `.env.example` 与 `.env` 加 `PLAYWRIGHT_CDP_URL=http://browser:9222`(参照 SCHEDULER_INTERNAL_URL 行)
- [x] 1.3 `docker-compose.yml` 新增 `browser` 服务:`image: mcr.microsoft.com/playwright:v1.49.1-noble`,`command: npx playwright run-server --port 9222`,`expose: 9222`,接入 `fund-network`,加 healthcheck(`/json/version`),`restart: unless-stopped`
- [x] 1.4 `scheduler` 服务加 `PLAYWRIGHT_CDP_URL` 环境变量与 `depends_on: [browser]`(web 服务不加,parser 仅在 scheduler 进程用)
- [x] 1.5 **技术验证点(已通过)**:`docker-compose up browser` 起容器,`curl http://127.0.0.1:9222/json/version` 返回 Chrome/131。微软镜像不适合直接做 CDP server(chrome 只绑 127.0.0.1、无 socat),改用自定义镜像 `fund-browser:latest`(`Dockerfile.browser` + `browser-entrypoint.sh`,socat 转发 0.0.0.0:9222->127.0.0.1:9223)。详见 design 第 10 节

### 2. PlaywrightClient 单例(browser 长连管理)
**Effort Estimate**: Medium

#### Sub-tasks:
- [x] 2.1 [TDD] 先写 `tests/test_fund_web_parser.py` 中 PlaywrightClient 测试:单例(`__new__` 返回同一实例)、惰性 init(首次 new_page 才连)、page 用完关闭(mock playwright,不连真实浏览器)
- [x] 2.2 [TDD] 测连接断开重连:`_ensure_connected` 检测连接失效后重新 `connect_over_cdp`
- [x] 2.3 [TDD] 测 `PLAYWRIGHT_CDP_URL` 未配置(空)时报错或返回明确提示
- [x] 2.4 实现 `app/utils/playwright_client.py`:`PlaywrightClient` 类(`__new__` 单例 + 惰性 init + `os.getenv('PLAYWRIGHT_CDP_URL')`),`new_page()` 上下文管理(page 临时关),`close()`,模块级实例 `playwright_client` + `get_browser()` 便捷函数
- [x] 2.5 复用 `app.utils.logger.logger` 记录连接/重连/异常,异常不中断主流程(参照 run_with_trace_context 思想)
- [x] 2.6 跑 `python3 -m pytest tests/test_fund_web_parser.py -q` 通过

### 3. FundWebParser 解析器(fetch + _parse 两层)
**Effort Estimate**: Medium

#### Sub-tasks:
- [x] 3.1 [TDD] 准备 `tests/fixtures/fundf10_basic.html`:录制/构造一份 fundf10 基本概况页 HTML(含基金名称/类型/成立日期/基金经理/基金规模)
- [x] 3.2 [TDD] 测 `_parse(html, fund_code)` 纯函数:喂 fixture,断言解析出 FundWebData 各字段正确
- [x] 3.3 [TDD] 测 `_parse` 边界:HTML 缺字段、空 HTML、错误结构返回 None 或默认值
- [x] 3.4 [TDD] 测 `fetch(fund_code)`:mock PlaywrightClient.new_page 返回 fixture HTML,断言返回 FundWebData;mock 异常时返回 None
- [x] 3.5 实现 `app/parser/fund_web_parser.py`:`FundWebData` dataclass(fund_code/fund_name/fund_type/establish_date/fund_manager/fund_size),`FundWebParser` 类(FUND_F10_URL 模板、`fetch`、`_fetch_html` 走 PlaywrightClient、`_parse` 纯函数用 BeautifulSoup)
- [x] 3.6 `app/parser/__init__.py` 加 `from .fund_web_parser import FundWebParser, FundWebData` 并入 `__all__`(不动两个旧 import)
- [x] 3.7 跑 `python3 -m pytest tests/test_fund_web_parser.py -q` 通过

### 4. task 编排 + 手动触发接入(抓取+打印,不落库)
**Effort Estimate**: Small

> 骨架阶段不写数据库,task 抓取后打印结构化数据(用户决策)。落库留后续。

#### Sub-tasks:
- [x] 4.1 实现 `app/task/fetch_fund_detail_task.py`:`fetch_fund_detail_task(force_run=False)`,参照 fetch_kc50_index_task 的实例化/try/except/finally 结构,但**不接 storage**:遍历 fund_codes -> FundWebParser.fetch -> 把 FundWebData 结构化打印(logger.info),异常捕获记录不中断
- [x] 4.2 `app/task/register_task.py` 加 import + `scheduler.register_task('fetch_fund_detail_task', fetch_fund_detail_task)`(**不**往 task_schedule 表插行,确保不被 cron 调度)
- [x] 4.3 [TDD] 测手动触发链路:mock FundWebParser.fetch,验证 `fetch_fund_detail_task` 遍历并打印结构化结果;mock 异常时单只基金失败不中断整体(参照现有 task 测试范式)
- [x] 4.4 跑 `python3 -m pytest tests/test_fund_web_parser.py -q` 通过

### 5. 集成验证与全量回归
**Effort Estimate**: Small

#### Sub-tasks:
- [x] 5.1 端到端验证(已通过):HTTP 触发 `/internal/task/run/fetch_fund_detail_task`,从真实库读 23 只基金全部抓取成功(23/23,0 失败),打印结构化数据。详见 design 第 10 节
- [x] 5.2 `data-crawler/` 下跑 `python3 -m pytest tests/ -q` 全量回归(168 passed),确认无回归
- [x] 5.3 对照 `tasks/prd-fund-web-scraper.md` 验收标准 AC1-AC10 逐条核对(全部达标)
- [x] 5.4 Phase 6 reviewer:同步起 1 个 code-reviewer agent(中改),已修复 3 个高危(run-server/CDP 协议、storage.close 致命崩、连接失效不重连)+ 4 个中低危

## Notes

### 依赖顺序
- 任务 1(browser 服务 + 依赖)与任务 2(PlaywrightClient)可并行准备,但 2.6 测试通过依赖 1.5 的 CDP 验证结论(本地测 mock 不依赖,端到端依赖)。
- 任务 3 依赖任务 2(PlaywrightClient)。
- 任务 4 依赖任务 3(FundWebParser)。
- 任务 5 依赖全部。

### TDD 节奏(强制)
每个任务按:先写测试用例(明确预期与边界)-> 再写实现 -> `python3 -m pytest tests/test_fund_web_parser.py -q` 通过 -> 勾选。禁止先实现后补测试。

### 关键约束
- **不动** `fund_parser.py`、`kc_index_parser.py`(并行并存)。
- **不插** `task_schedule` 表(仅手动触发,不被 cron 调度)。
- **Dockerfile 基本不动**(独立浏览器服务方案下,仅需 requirements.txt 的 pip 包)。
- **mac 本地不装浏览器**,开发连远程 Docker;本地 pytest 用 mock,不连真实浏览器。

### 首要风险
- `mcr.microsoft.com/playwright` 镜像 CDP server 启动命令(1.5)是首要技术验证点,若官方命令不可用需自写 Node 启动脚本,可能微调 compose command。

### 后续(非本次范围)
- 持仓明细 / 阶段涨幅 / 费率信息的抓取与落库(需新表 fund_holdings / fund_performance)。
- 接入 cron 定时调度(届时往 task_schedule 插行)。
- context 定期重建等资源优化。
