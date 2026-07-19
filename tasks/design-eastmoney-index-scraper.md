# Design: 东方财富指数网页抓取解析器(eastmoney-index-scraper)

**Feature slug**: `eastmoney-index-scraper`

> **状态:已搁置(2026-07-19)**。详见 PRD 搁置说明。未来改从同花顺抓取时,本文档的"可扩展抽象基类"设计仍可复用(基类 + 同花顺实现子类),东方财富实现作废。文档保留供参考。

> 架构设计。配套 PRD 见 `tasks/prd-eastmoney-index-scraper.md`。纯后端,无前端设计。

## 1. 设计约束(已与用户锁定)

- requests + push2 API(实测东方财富指数页 JS 渲染,静态 HTML 抓不到)。
- 抓 9 个指数(沪深300/深证成指/上证指数/恒生科技/纳斯达克100/000819/000813/399998/399997)。
- 可扩展抽象:基类定义契约,东方财富为实现,未来加数据源写子类。
- 单 task 每 30 分钟 + 各市场交易时间门控(CN/HK/US)。
- 美股 trade_date 按美东时区(zoneinfo America/New_York)。
- 存 index_info 表(source='东方财富'),Storage 零改动。
- 000300 改由东方财富抓(填补空缺),KC 任务不动。
- 解析器容忍港股/美股缺失字段("-"->0.0)。

## 2. 技术基础(实测验证)

东方财富指数页 `quote.eastmoney.com/zsXXX.html` 是 JS 动态渲染,静态 HTML 全是占位符 `-`。真实数据由页面 JS 调多个接口(`push2.eastmoney.com/api/qt/stock/get`、`31.push2.eastmoney.com/api/qt/stock/trends2/sse` 等)后填入 `.brief_info li` 等元素。

**实测结论**:
- `push2` 等接口对密集请求的 IP 会限流(本地 Mac IP 连续测试被限),但页面 HTML 本身可访问(HTTP 200)。
- 真实浏览器(未限 IP)能看到数据;Playwright 抓不到是因 IP 被限导致页面 JS 请求接口失败、数据填不进 HTML,非 headless 检测(xvfb 有头 + 反检测后仍抓不到,印证是 IP 限流)。
- 服务器 IP(117.72.53.38)未被限,部署后可正常抓取。
- 页面有 SSE 持续连接,`networkidle` 永远不触发,不能用;需用 `wait_for_function` 等 `.brief_info li` 填值。

**渲染完成态 HTML 结构**(用户提供,解析依据):
```html
<div class="zsquote3l zs_brief">
  <div class="quote_quotenums"><div class="zxj"><span><span class="price_down">3416.88</span></span></div></div>
  <ul class="brief_info">
    <li>今开: <span><span class="price_down">3452.78</span></span></li>
    <li>最高: <span><span class="price_up">3503.00</span></span></li>
    <li>涨跌幅: <span><span class="price_down">-1.20%</span></span></li>
    <li>换手: <span><span class="price_draw">1.87%</span></span></li>
    <li>成交量: <span><span class="price_draw">2302万手</span></span></li>
    <li>昨收: <span><span class="price_draw">3458.33</span></span></li>
    <li>最低: <span><span class="price_down">3392.37</span></span></li>
    <li>涨跌额: <span><span class="price_down">-41.45</span></span></li>
    <li>振幅: <span><span class="price_draw">3.20%</span></span></li>
    <li>成交额: <span><span class="price_draw">521.1亿</span></span></li>
  </ul>
</div>
```

字段映射:`.zxj` 最新价;`.brief_info li` 按 `label: value` 解析(今开/最高/最低/昨收/涨跌幅/换手/成交量/成交额/振幅)。成交量带"万手"单位、成交额带"亿"单位,解析时去单位转数值。

**secid/URL**:页面 URL `zs{code}.html`(A 股)、`gb/zs{code}.html`(海外)。解析器按 URL 抓页面,不直接调 API(secid 由页面 JS 自己处理)。

## 2.1 browser 容器配置(已就绪)

为降低被检测风险,browser 容器已改:
- **xvfb 有头模式**:`Dockerfile.browser` 装 xvfb,`browser-entrypoint.sh` 用 `xvfb-run` 启 chrome(非 headless),规避 headless 检测。
- **`--disable-blink-features=AutomationControlled`**:隐藏 navigator.webdriver 标记。
- 注:实测这些反检测未能绕过 IP 限流(根因是 IP),但有头模式更接近真实浏览器,保留。

## 3. 整体架构

```
app/parser/
  index_parser_base.py      [新] 抽象基类 BaseIndexParser + IndexData dataclass
  eastmoney_index_parser.py [新] 东方财富实现(继承基类)
  fund_parser.py / kc_index_parser.py / fund_web_parser.py  [不动]
  __init__.py               [改] 导出新解析器

app/task/
  fetch_eastmoney_index_task.py  [新] 抓取 task(循环 9 指数 + 市场门控)
  register_task.py               [改] 注册

sql/alter/
  seed_eastmoney_index_task.sql  [新] cron 种子(*/2 * * * *)

tests/
  test_eastmoney_index_parser.py [新] TDD
  fixtures/eastmoney_*.json      [新] push2 响应 fixture
```

## 4. 核心组件设计

### 4.1 抽象基类(app/parser/index_parser_base.py)

参照 fund_web_parser 的 fetch/_parse 两层 + dataclass + client 注入,做成抽象基类:

```python
@dataclass
class IndexData:
    index_code: str
    index_name: str
    index_type: str
    trade_date: str  # YYYY-MM-DD(由 task 按市场时区算,解析器不参与)
    open_price: float
    close_price: float
    high_price: float
    low_price: float
    change_percent: float
    volume: float       # 万手
    amount: float       # 亿元
    turnover_rate: float
    update_time: str

class BaseIndexParser(ABC):
    """指数抓取解析器抽象基类。定义 fetch/_fetch_raw/_parse 契约。
    子类实现 _fetch_raw(传输) + _parse(解析),fetch 编排。"""
    @abstractmethod
    def _fetch_raw(self, index_code: str) -> Optional[str]: ...
    @abstractmethod
    def _parse(self, raw: str, index_code: str) -> Optional[IndexData]: ...
    def fetch(self, index_code: str) -> Optional[IndexData]:
        try:
            raw = self._fetch_raw(index_code)
            return self._parse(raw, index_code) if raw else None
        except Exception as e:
            logger.error(...); return None
```

### 4.2 东方财富实现(app/parser/eastmoney_index_parser.py)

```python
class EastmoneyIndexParser(BaseIndexParser):
    """东方财富指数页解析器（Playwright 抓渲染后 HTML + BeautifulSoup 解析）。
    参照 fund_web_parser 的 fetch/_fetch_html/_parse 两层，复用 PlaywrightClient 单例。"""
    # URL 模板：A股 zs{code}.html；海外 gb/zs{code}.html
    URL_CN = "https://quote.eastmoney.com/zs{code}.html"
    URL_OVERSEAS = "https://quote.eastmoney.com/gb/zs{code}.html"
    INDEX_CONFIG = {
        '000300': {'name': '沪深300', 'index_type': '宽基指数', 'market': 'CN'},
        '000001': {'name': '上证指数', 'index_type': '宽基指数', 'market': 'CN'},
        '399001': {'name': '深证成指', 'index_type': '宽基指数', 'market': 'CN'},
        '000819': {'name': '...', 'index_type': '行业指数', 'market': 'CN'},
        '000813': {'name': '...', 'index_type': '行业指数', 'market': 'CN'},
        '399998': {'name': '中证煤炭', 'index_type': '行业指数', 'market': 'CN'},
        '399997': {'name': '中证白酒', 'index_type': '行业指数', 'market': 'CN'},
        'HSTECH': {'name': '恒生科技', 'index_type': '宽基指数', 'market': 'HK', 'overseas': True},
        'NDX':    {'name': '纳斯达克100', 'index_type': '宽基指数', 'market': 'US', 'overseas': True},
    }
    def _fetch_html(self, index_code):  # Playwright goto + wait_for_function 等 .brief_info li 填值
    def _parse(self, html, index_code):  # BeautifulSoup 解析 .brief_info li + .zxj
```

- `_fetch_html`(原 `_fetch_raw`):走 PlaywrightClient.new_page() -> goto(`domcontentloaded`)-> `wait_for_function`(等 `.brief_info li` 至少 3 个非 `-`,超时 20s)-> `page.content()` 返回渲染后 HTML。不用 `networkidle`(SSE 持续不 idle)。
- `_parse`:BeautifulSoup 解析 `.brief_info li`(label: value,如"今开: 3452.78")+ `.zxj`(最新价)。成交量去"万手"、成交额去"亿"转数值;"-"->0.0。指数名用 INDEX_CONFIG 的 name(页面标题可能含冗余)。
- client 注入:默认 `get_playwright_client()`,测试可注入 mock。

### 4.3 task(app/task/fetch_eastmoney_index_task.py)

照 fetch_kc50_index_task 模式:
```python
def fetch_eastmoney_index_task(force_run=False):
    parser = EastmoneyIndexParser()
    storage = IndexInfoStorage()
    for code, cfg in EastmoneyIndexParser.INDEX_CONFIG.items():
        if not force_run and not _is_trading_time(cfg['market']):
            continue  # 该市场闭市跳过
        data = parser.fetch(code)
        if data:
            trade_date = _get_trade_date(cfg['market'])  # CN/HK 北京时间,US 美东
            index_info_data = {..., 'source': '东方财富', 'trade_date': trade_date,
                               'pe_ratio': 0.0, 'pe_percentile': 0.0, 'pb_ratio': 0.0}
            storage.create_or_update_index_info(index_info_data)
```

- `_is_trading_time(market)`:CN 9:00-15:05 周一到五;HK 9:30-16:00;US 21:30-04:00(次日,夏令时自动)。
- `_get_trade_date(market)`:CN/HK 用 get_beijing_now().date();US 用 zoneinfo('America/New_York') 当地 date。

## 5. 字段映射(index_info)

| index_info 列 | HTML 来源 | 说明 |
|--------------|-----------|------|
| index_code | config 代码 | |
| index_name | config name | 页面标题含冗余,用 config |
| index_type | config | 宽基/行业指数 |
| trade_date | task 按市场算 | |
| open_price | `.brief_info li` "今开" | |
| close_price | `.zxj` 最新价 | |
| high_price | `.brief_info li` "最高" | |
| low_price | `.brief_info li` "最低" | |
| change_percent | `.brief_info li` "涨跌幅" | 去 % |
| volume | `.brief_info li` "成交量" | 去"万手"->数值(已是万手单位) |
| amount | `.brief_info li` "成交额" | 去"亿"->数值(已是亿单位) |
| turnover_rate | `.brief_info li` "换手" | 去 %,"-":0.0 |
| pe_ratio | - | 0.0(指数无) |
| pe_percentile | - | 0.0 |
| pb_ratio | - | 0.0 |
| source | '东方财富' | |

> 单位:HTML 里成交量直接是"万手"、成交额"亿"(如"2302万手""521.1亿"),去单位即符合 index_info 列注释(万手/亿元),无需换算。

## 6. 关键决策

- **抽象基类**:满足"可扩展"要求,未来加数据源(其他网站)写子类实现 _fetch_raw/_parse,task/storage 不变。
- **requests 而非 Playwright**:push2 API 直接返回 JSON,高效轻量,不依赖 browser 容器。基类设计允许未来 Playwright 子类。
- **单 task + 市场门控**:一个 cron `*/30` 覆盖三市场,闭市 early-return,简洁。30 分钟一次频率低,避免 push2 限流。
- **美东时区**:zoneinfo America/New_York 自动处理夏令时,避免美股交易日劈两半。
- **000300 填补空缺**:2025-07-29 后由东方财富抓,source=东方财富,与腾讯历史共存(upsert 按 code+date)。
- **容忍缺失字段**:港股/美股部分字段无,"-"->0.0,设计预期内。

## 7. 待验证风险(实现阶段首要)

- **IP 限流(已确认根因)**:本地 Mac IP 连续测试触发东方财富对 push2 等接口的限流,导致页面 JS 请求失败、数据填不进 HTML。服务器 IP(117.72.53.38)未被限,部署后可正常抓取。30 分钟一次 9 个页面频率极低,正常不会触发限流。
- **等待策略**:`_fetch_html` 用 `wait_for_function` 等 `.brief_info li` 至少 3 个非 `-`(超时 20s)。本地 IP 被限时等不到(数据填不进),服务器 IP 未限时数据会填入、等待成功。超时则返回当前 HTML(_parse 容忍 `-`->0.0,记录部分字段)。
- **本地无法端到端验证**:本地 IP 被限,Playwright 抓不到数据。用用户提供的渲染完成态 HTML 做 fixture 测 _parse 逻辑;部署服务器后实测抓取。
- **页面结构变更**:`.brief_info li` 选择器若失效,_parse 返回 None,记日志跳过。fixture 测试可快速定位结构变更。
