# Task List: 东方财富指数网页抓取解析器(eastmoney-index-scraper)

**Based on PRD**: `tasks/prd-eastmoney-index-scraper.md`
**Based on Design**: `tasks/design-eastmoney-index-scraper.md`

> **状态:已搁置(2026-07-19)**。详见 PRD 搁置说明。未来改从同花顺抓取时重启。已勾选的子任务(1.1/1.2 fixture 准备、browser 容器 xvfb 改造)保留;未实现的子任务待同花顺方案定后重新规划。

**Based on PRD**: `tasks/prd-eastmoney-index-scraper.md`

## Relevant Files

### Files to Create
- `data-crawler/app/parser/index_parser_base.py` - 抽象基类 BaseIndexParser + IndexData dataclass
- `data-crawler/app/parser/eastmoney_index_parser.py` - 东方财富实现(Playwright 抓渲染后 HTML + BeautifulSoup 解析)
- `data-crawler/app/task/fetch_eastmoney_index_task.py` - 抓取 task(循环 9 指数 + 市场门控)
- `sql/alter/seed_eastmoney_index_task.sql` - cron 种子(*/30 * * * *)
- `data-crawler/tests/test_eastmoney_index_parser.py` - TDD 测试
- `data-crawler/tests/fixtures/eastmoney_*.html` - 渲染后 HTML fixture(A/HK/US 代表,用户提供结构)

### Files to Modify
- `data-crawler/app/parser/__init__.py` - 导出 BaseIndexParser/IndexData/EastmoneyIndexParser
- `data-crawler/app/task/register_task.py` - 注册 fetch_eastmoney_index_task

## Implementation Tasks

### 1. HTML fixture 准备与技术基础
**Effort Estimate**: Small

#### Sub-tasks:
- [x] 1.1 确认东方财富指数页渲染完成态 HTML 结构(用户提供 `.brief_info li` + `.zxj` 结构,含 3416.88/3452.78 等数字)
- [ ] 1.2 构造 3 个渲染后 HTML fixture 落盘 tests/fixtures/(eastmoney_000300.html A股全字段、eastmoney_HSTECH.html HK 缺换手率、eastmoney_NDX.html US 缺成交额+换手率),基于用户提供的 HTML 结构,供 _parse 测试
- [ ] 1.3 确认 browser 容器 xvfb 有头 + 反检测已就绪(实测 `--disable-blink-features=AutomationControlled` 已加,navigator.webdriver 隐藏)

### 2. 抽象基类 + IndexData(index_parser_base.py)
**Effort Estimate**: Small

#### Sub-tasks:
- [ ] 2.1 [TDD] 先写 tests/test_eastmoney_index_parser.py 中基类测试:BaseIndexParser 不可实例化(ABC)、子类必须实现 _fetch_html/_parse、fetch 编排调 _fetch_html 失败返回 None
- [ ] 2.2 [TDD] 测 IndexData dataclass 字段完整(index_code/index_name/index_type/trade_date/open_price/close_price/high_price/low_price/change_percent/volume/amount/turnover_rate/update_time)
- [ ] 2.3 实现 app/parser/index_parser_base.py:IndexData dataclass + BaseIndexParser(ABC,fetch 编排 + 抽象 _fetch_html/_parse + 异常捕获返回 None),参照 fund_web_parser 的 client 注入与 fetch/_parse 两层设计
- [ ] 2.4 跑 python3 -m pytest tests/test_eastmoney_index_parser.py -q 通过

### 3. 东方财富实现(eastmoney_index_parser.py)
**Effort Estimate**: Medium

#### Sub-tasks:
- [ ] 3.1 [TDD] 测 _parse 纯函数:喂 eastmoney_000300.html fixture,断言 IndexData 字段映射正确(close=.zxj 3416.88/open=今开 3452.78/high=最高 3503.00/low=最低 3392.37/volume=成交量 2302/amount=成交额 521.1/change=涨跌幅 -1.2/turnover=换手 1.87)
- [ ] 3.2 [TDD] 测 _parse 容忍缺失字段:喂 HSTECH fixture(换手"-"->turnover 0.0)、NDX fixture(成交额"-"->amount 0.0, 换手"-"->turnover 0.0)
- [ ] 3.3 [TDD] 测 _parse 边界:HTML 无 .brief_info 返回 None、空 HTML 返回 None
- [ ] 3.4 [TDD] 测 fetch:mock PlaywrightClient.new_page(wait_for_function + content 返回 fixture HTML),断言返回 IndexData;mock 异常返回 None
- [ ] 3.5 实现 eastmoney_index_parser.py:EastmoneyIndexParser(BaseIndexParser),URL_CN/URL_OVERSEAS 模板,INDEX_CONFIG(9 指数 name/index_type/market/overseas),_fetch_html(Playwright goto + wait_for_function 等 .brief_info li 填值 + content),_parse(BeautifulSoup 解析 .brief_info li label:value + .zxj + "-"->0.0 + 去单位)
- [ ] 3.6 app/parser/__init__.py 导出 BaseIndexParser/IndexData/EastmoneyIndexParser,加入 __all__(不动现有三个 parser 导出)
- [ ] 3.7 跑 python3 -m pytest tests/test_eastmoney_index_parser.py -q 通过

### 4. task + 注册 + cron 种子
**Effort Estimate**: Medium

#### Sub-tasks:
- [ ] 4.1 [TDD] 测 _is_trading_time(market):CN 周末/非 9:00-15:05 返回 False;HK 9:30-16:00;US 21:30-04:00(次日)。mock get_beijing_now
- [ ] 4.2 [TDD] 测 _get_trade_date(market):CN/HK 返回北京时间 date;US 返回美东时区 date(zoneinfo America/New_York)
- [ ] 4.3 [TDD] 测 fetch_eastmoney_index_task:mock parser.fetch 返回 IndexData,遍历 9 指数;闭市市场跳过;断言 index_info_data 含 source='东方财富'、pe_ratio/pe_percentile/pb_ratio=0.0、调 create_or_update_index_info;单只失败不中断
- [ ] 4.4 实现 fetch_eastmoney_index_task.py:_is_trading_time(market) + _get_trade_date(market) + fetch_eastmoney_index_task(force_run=False),参照 fetch_kc50_index_task 模式(parser/storage task 内 new,try/except/finally close)
- [ ] 4.5 register_task.py 加 import + scheduler.register_task('fetch_eastmoney_index_task', fetch_eastmoney_index_task)
- [ ] 4.6 sql/alter/seed_eastmoney_index_task.sql:INSERT IGNORE task_schedule('东方财富指数抓取任务','fetch_eastmoney_index_task','*/30 * * * *',1,...)
- [ ] 4.7 生产库执行 seed 脚本(插 task_schedule 行,热加载生效)
- [ ] 4.8 跑 python3 -m pytest tests/test_eastmoney_index_parser.py -q 通过

### 5. 集成验证与全量回归
**Effort Estimate**: Small

#### Sub-tasks:
- [ ] 5.1 端到端验证:手动触发 fetch_eastmoney_index_task(force_run),确认 9 指数抓取并落库 index_info(source='东方财富'),字段正确(尤其港股/美股缺失字段 0.0)
- [ ] 5.2 验证美东时区:美股 trade_date 为美东当地日期(非北京时间),不跨日劈两半
- [ ] 5.3 data-crawler/ 下跑 python3 -m pytest tests/ -q 全量回归,确认无回归
- [ ] 5.4 Phase 6 reviewer:同步起 1 个 code-reviewer agent(中改),核实抽象设计/字段映射/时区/项目规范
- [ ] 5.5 对照 tasks/prd-eastmoney-index-scraper.md 验收标准 AC1-AC10 逐条核对,未达标项记录

## Notes

### 依赖顺序
- 任务 1(secid 验证 + fixture)是基础,任务 3 依赖它(fixture)。
- 任务 2(基类)是任务 3 的父类,先于任务 3。
- 任务 3(解析器)依赖任务 2(基类)+ 任务 1(fixture)。
- 任务 4(task)依赖任务 3(解析器)。
- 任务 5(集成验证)依赖全部。

### TDD 节奏(强制)
每个任务按:先写测试用例(明确预期与边界)-> 再写实现 -> python3 -m pytest tests/test_eastmoney_index_parser.py -q 通过 -> 勾选。禁止先实现后补测试。

### 关键约束
- **用 Playwright**:抓渲染后 HTML + BeautifulSoup 解析(不用 requests 直连 API,push2 等接口对密集 IP 限流;服务器 IP 未限)。基类允许未来 requests 子类。
- **不动 KC 任务**:fetch_kc50/100 保持原样。
- **不抓 PE/PB**:指数无,置 0.0。
- **不改 index_info 表结构**:Storage 零改动。
- **000300 填补空缺**:2025-07-29 后由东方财富抓,source=东方财富。

### 首要风险(任务 1/5 验证)
- **IP 限流(已确认根因)**:本地 Mac IP 连续测试触发东方财富对 push2 等接口限流,页面 JS 请求失败、数据填不进 HTML。本地 Playwright 抓不到数字(全 `-`)。服务器 IP 未限,部署后可正常抓。本地用构造的 fixture 测 _parse 逻辑。
- **等待策略**:`_fetch_html` 用 `wait_for_function` 等 `.brief_info li` 至少 3 个非 `-`(超时 20s)。本地 IP 被限等不到,服务器会等到。
- **本地无法端到端验证**:本地 IP 被限,部署服务器后实测抓取(任务 5)。

### 数据库部署
- task_schedule 首次:sql/alter/seed_eastmoney_index_task.sql 在生产库执行(热加载生效,无需重启 scheduler)。
- index_info 表无变更(source 字段已存在)。
