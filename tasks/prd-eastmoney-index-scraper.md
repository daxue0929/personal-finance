# PRD: 东方财富指数网页抓取解析器(eastmoney-index-scraper)

**Feature slug**: `eastmoney-index-scraper`

> **状态:已搁置(2026-07-19)**。东方财富 push2 等接口对密集请求 IP 限流,页面 JS 请求失败导致数据填不进 HTML,本地无法端到端验证;服务器 IP 虽未限但方案不确定性高。用户决定本功能搁置,未来改从**同花顺**抓取。本文档保留供未来重启参考,设计/任务文档同步搁置。已改的 browser 容器(xvfb 有头 + 反检测)保留,不影响其他功能。

**Feature slug**: `eastmoney-index-scraper`

## 1. 背景与功能目标

### 背景
现有指数抓取只有 KcIndexParser(腾讯财经,抓科创50/100 两个指数)。用户需要抓取更多指数(沪深300/深证成指/上证指数/恒生科技/纳斯达克100 等 9 个),主要从东方财富抓。其中沪深300(000300)历史数据停在 2025-07-29,需填补。

实测发现:东方财富指数页 `quote.eastmoney.com/zsXXX.html` 是 JS 动态渲染,静态 HTML 全是占位符 `-`。页面 JS 调多个接口(push2、31.push2 trends2/sse 等)后填入 `.brief_info li`。push2 等接口对密集请求的 IP 会限流(本地 Mac IP 连续测试被限),但页面 HTML 本身可访问,真实浏览器(未限 IP)能渲染数据。服务器 IP 未被限,部署后可正常抓。故采用 Playwright 抓渲染后 HTML + BeautifulSoup 解析(不用 networkidle,SSE 持续;用 wait_for_function 等 `.brief_info li` 填值)。

### 功能目标
- 新建**可扩展的指数抓取解析器**:抽象基类定义契约,东方财富为实现(未来可加其他数据源子类)。参照 fund_web_parser 的 fetch/_parse 两层 + dataclass + client 注入设计。
- 东方财富实现:Playwright 抓渲染后 HTML(`wait_for_function` 等 `.brief_info li` 填值),BeautifulSoup 解析。配置 9 个指数(URL/name/index_type/market),容忍港股/美股缺失字段("-"->0.0)。
- 单 task 每 30 分钟,task 内按各市场交易时间门控(CN 9:00-15:05 / HK 9:30-16:00 / US 21:30-04:00 次日)。
- 美股 trade_date 按美东时区算(避免跨日劈两半)。
- 存 index_info 表(source='东方财富'),Storage 零改动。
- 000300 沪深300 改由东方财富抓(填补 2025-07-29 后空缺),KC 任务(000688/000698)不动。

## 2. 用户故事

- **作为用户**,我希望抓取沪深300/深证成指/上证指数/恒生科技/纳斯达克100 等 9 个指数的实时行情,存 index_info 表。
- **作为用户**,我希望指数数据带"数据来源"标识(东方财富),与现有腾讯财经数据区分。
- **作为运维**,我希望解析器架构可扩展,未来加新数据源(其他网站)时只需写子类,不改 task/storage。
- **作为运维**,我希望抓取频率合理(每 30 分钟),闭市不抓(各市场门控),不打扰数据源。
- **作为用户**,我希望美股指数的交易日按美东时区记录,避免同一交易日存成两条。

## 3. 验收标准

### 解析器(可扩展抽象)
- [ ] AC1: 新建 `app/parser/index_parser_base.py`:`IndexData` dataclass(字段对齐 index_info) + `BaseIndexParser` 抽象基类(fetch 编排 + 抽象 `_fetch_raw`/`_parse` + client 注入)。
- [ ] AC2: 新建 `app/parser/eastmoney_index_parser.py`:`EastmoneyIndexParser(BaseIndexParser)`,`_fetch_html` 用 Playwright 抓渲染后 HTML(wait_for_function 等 `.brief_info li` 填值),`_parse` 用 BeautifulSoup 解析 `.brief_info li`(label:value)+ `.zxj`(最新价),"-"/None 容忍为 0.0。`INDEX_CONFIG` 类属性配置 9 个指数(URL 模板/name/index_type/market)。
- [ ] AC3: `app/parser/__init__.py` 导出 BaseIndexParser/IndexData/EastmoneyIndexParser。
- [ ] AC4: 单位处理正确:成交量去"万手"、成交额去"亿"转数值(已是万手/亿元单位,符合 index_info 列注释);港股无换手率、美股无成交额+换手率时置 0.0;指数无 PE/PB 置 0.0。

### task 与调度
- [ ] AC5: 新建 `app/task/fetch_eastmoney_index_task.py`:循环抓 9 个指数,per-market 交易时间门控(force_run 跳过),组 index_info_data dict(source='东方财富'),调 IndexInfoStorage.create_or_update_index_info,单只失败不中断。
- [ ] AC6: 美股 trade_date 按美东时区算(CN/HK 用北京时间)。
- [ ] AC7: `register_task.py` 注册 fetch_eastmoney_index_task。
- [ ] AC8: `sql/alter/seed_eastmoney_index_task.sql` 插 task_schedule(cron `*/30 * * * *`,enabled=1),热加载生效。

### 质量
- [ ] AC9: TDD,`tests/test_eastmoney_index_parser.py` 先行:_parse 纯函数(喂 push2 JSON fixture,覆盖 A/HK/US 字段缺失)+ fetch(mock requests.Session)+ task(monkeypatch parser/storage)。pytest 全量回归通过。
- [ ] AC10: 端到端验证:手动触发抓取 9 个指数,index_info 表新增/更新记录(source='东方财富'),字段正确。

## 4. 非目标

- **不动 KC 任务**:fetch_kc50/100(抓 000688/000698)保持原样。
- **不用 requests 直连 API**:走 Playwright 抓渲染后 HTML(规避 IP 限流 + 拿渲染数据)。基类设计允许未来 requests 子类。
- **不抓 PE/PB/PE分位**:指数无这些字段,置 0.0(与现状一致)。
- **不改 index_info 表结构**:source 字段已存在,Storage 已支持。
- **不做前端**:纯后端抓取,数据经现有指数信息页展示(已有数据来源列)。
- **不处理 000300 历史数据回填**:只从启用日起往后抓,历史空缺不补。
- **不做反爬对抗**:push2 API 当前无限制,不实现代理/验证码。

## 5. 依赖

- **现有**:PlaywrightClient(browser 长连)、beautifulsoup4(已装)、IndexInfoStorage(create_or_update_index_info 已支持 source)、index_info 表(含 source 字段)、register_task 注册链路、task_schedule 热加载、browser 容器(xvfb 有头 + 反检测,已就绪)。
- **新增**:无新依赖。
- **数据源**:东方财富 quote.eastmoney.com 指数页(页面 HTML 可访问,数据由 JS 渲染填入)。

## 6. 风险

| 风险 | 影响 | 缓解 |
|------|------|------|
| push2 等接口 IP 限流 | 页面 JS 请求失败,数据填不进 HTML | 服务器 IP 未限;30 分钟一次低频;task 异常捕获不中断 |
| 页面等待超时(数据未填) | _parse 拿到全 `-` | wait_for_function 超时返回当前 HTML,_parse 容忍 `-`->0.0,记日志 |
| 页面结构变更(.brief_info li) | 解析失败 | _parse 返回 None 跳过;fixture 测试快速定位 |
| 美股夏令时 | trade_date 偏移 | zoneinfo America/New_York 自动处理 |
| 港股/美股指数字段缺失 | 部分 0.0 | 设计预期内,前端容忍 |
| 000300 source 由腾讯变东方财富 | 前端数据来源列显示变化 | 预期内,2025-07-29 后新数据 source=东方财富 |
| secid 前缀配置错误 | 抓不到数据 | INDEX_CONFIG 集中配置,实测验证 9 个 secid |

## 7. Open Questions

(Phase 3 澄清后,已无遗留。以下为已澄清决策记录)

- **Q: 传输方式?** A: Playwright 抓渲染后 HTML + BeautifulSoup 解析(push2 等接口对密集请求 IP 限流,页面 HTML 本身可访问;服务器 IP 未限)。
- **Q: 000300 冲突?** A: 新任务抓全 9 个(含 000300,改东方财富),KC 任务不动(本就不抓 000300)。
- **Q: 抓取频率?** A: 单 task 每 30 分钟 + 各市场交易时间门控。
- **Q: 美股 trade_date?** A: 按美东时区算(zoneinfo America/New_York)。
