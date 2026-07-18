# PRD: Playwright 网页抓取解析器(fund-web-scraper)

**Feature slug**: `fund-web-scraper`

## 1. 背景与功能目标

### 背景
`data-crawler/app/parser/` 现有两个解析器:
- `FundParser`(fund_parser.py):requests 抓东方财富 `pingzhongdata/{code}.js` 接口,字符串切割解析基金名/最新净值/经理等。
- `KcIndexParser`(kc_index_parser.py):requests 抓腾讯财经接口,`split('~')` 解析科创指数。

两者均依赖"静态接口 + 字符串切割",只能拿到接口返回的结构化字段,**拿不到东方财富网页(fundf10)动态渲染的内容**(如基金持仓明细、阶段涨幅、费率明细等),且未来若接口反爬将整体失效。

### 功能目标
为 parser 模块**新增**一种并行能力:用 Playwright(无头浏览器)抓取东方财富 fundf10 网页 HTML,识别、清洗出需要的信息。本 PRD 聚焦**架构落地与可运行骨架**,具体字段抓取分阶段交付。

- 引入独立 Docker 浏览器服务(微软官方 `mcr.microsoft.com/playwright` 镜像,CDP server 模式),应用进程通过 CDP 长连复用。
- 设计 browser 单例 + page 临时的生命周期管理,参照现有 `DatabaseManager` 单例模式。
- 落地 1 个样例解析器(`FundWebParser`),抓 fundf10 **基本概况**字段跑通"取 HTML -> 解析 -> 落库"全链路。
- 持仓明细/阶段涨幅/费率信息在架构中规划落库,代码列为后续任务。

## 2. 用户故事

- **作为系统维护者**,我希望 parser 模块具备 Playwright 网页抓取能力,这样未来能获取东方财富网页动态渲染的数据(接口拿不到的)。
- **作为系统维护者**,我希望浏览器以独立 Docker 服务运行,这样浏览器崩溃不影响爬虫主进程,且应用镜像保持轻量。
- **作为系统维护者**,我希望开发与部署统一连远程浏览器服务(本地不装浏览器),这样环境一致、配置只差地址。
- **作为开发者**,我希望抓取器有手动触发接口,这样骨架阶段能反复调试而无需等待 cron。

## 3. 验收标准

### 架构与骨架
- [ ] AC1: 新建 `app/utils/playwright_client.py`,实现 browser 单例管理(参照 `DatabaseManager`),通过 `PLAYWRIGHT_CDP_URL` 连接远程 CDP server,提供 `get_browser()` 便捷访问器,惰性初始化。
- [ ] AC2: 新建 `app/parser/fund_web_parser.py`,定义 `FundWebParser` 类,设计为 `fetch(fund_code)`(取 HTML)+ `_parse(html)`(纯函数)两层,与现有两个 parser 并列,不动现有两文件。
- [ ] AC3: `app/parser/__init__.py` 导出 `FundWebParser`,保持包级契约一致。
- [ ] AC4: `docker-compose.yml` 新增 `browser` 服务(微软官方 playwright 镜像,CDP server 模式,expose 9222,接入 fund-network),`scheduler` 服务加 `PLAYWRIGHT_CDP_URL` 环境变量与 `depends_on`。
- [ ] AC5: `requirements.txt` 加 `playwright`(版本遵 CLAUDE.md"倒数第二稳定版"规范);`.env` / `.env.example` 加 `PLAYWRIGHT_CDP_URL`。

### 样例抓取(基本概况)
- [ ] AC6: `FundWebParser` 能抓取 fundf10 基本概况字段(基金名称/类型/成立日期/基金经理/基金规模等),`_parse` 纯函数对录制 HTML fixture 解析正确。
- [ ] AC7: 提供手动触发接口(参照现有 `/api/task/run/<func>` 或新增内部接口),能触发 `FundWebParser` 抓取并返回解析结果,不接入 cron(不动 register_task / task_schedule)。
- [ ] AC8: 抓取结果能落库到 `fund_info` 表(复用或扩展 `FundInfoStorage` 方法),字段映射正确。

### 质量
- [ ] AC9: TDD,`tests/test_fund_web_parser.py` 先行,测 `_parse` 纯函数(喂 HTML fixture)+ mock `PlaywrightClient` 测 `fetch`,pytest 全量回归通过。
- [ ] AC10: browser 单例在进程内复用、page 用完关闭,异常不中断主流程(参照 `run_with_trace_context` 捕获记录)。

## 4. 非目标

- **不改动** `fund_parser.py`、`kc_index_parser.py` 两个现有文件(并行并存)。
- **不接入定时调度**:骨架阶段仅手动触发,不改 `register_task.py`、不插 `task_schedule`。
- **不实现全部 4 类字段抓取**:持仓明细、阶段涨幅、费率信息只做架构落库规划,代码不在本次骨架交付(仅基本概况跑通)。
- **不在 mac 本地安装浏览器**:开发也连远程 Docker 浏览器服务。
- **不替换现有 FundParser**:requests 版本继续工作,Playwright 版为新增能力。
- **不做反爬对抗策略**(验证码、代理池等)的深度实现,架构预留但不交付。

## 5. 依赖

- **新增 Python 依赖**:`playwright`(仅驱动包,不含浏览器二进制;浏览器在独立容器)。
- **新增 Docker 服务**:`mcr.microsoft.com/playwright` 官方镜像,CDP server 模式。
- **现有依赖复用**:`beautifulsoup4`(已在 requirements.txt)用于 HTML 解析;`app/utils/db.py` 单例模式参照;`app/utils/logger` 日志复用。
- **数据库**:基本概况字段大多落 `fund_info`(可能需 `sql/alter/` 加列);持仓/涨幅新表在后续阶段建。

## 6. 风险

| 风险 | 影响 | 缓解 |
|------|------|------|
| 官方 playwright 镜像 CDP server 启动参数/版本变动 | 浏览器服务起不来 | 镜像 tag 固定到具体版本;compose 加健康检查 |
| 东方财富 fundf10 页面结构变更 | 解析失败 | `_parse` 纯函数 + HTML fixture 测试,结构变更时改 fixture 与选择器即可定位 |
| 长连 browser context 资源累积/泄漏 | 内存涨 | page 临时用完即关;参照 db.py pool_recycle 设计 context 定期重建(后续优化) |
| CDP 连接断开未恢复 | 抓取全失败 | 单例惰性 init + 连接失败重连机制;异常捕获记录不中断 |
| 远程浏览器服务对开发网络依赖 | 本地调试受限 | 已知取舍,用户明确接受本地连生产服务器 Docker |
| playwright 版本与官方镜像浏览器版本不匹配 | 连接异常 | pip 包版本与镜像 tag 对齐 |

## 7. Open Questions

(Phase 3 澄清后,已无遗留问题。以下为已澄清决策记录)

- **Q: fundf10 抓哪些字段?** A: 基本概况 + 持仓明细 + 阶段涨幅 + 费率信息(架构规划全部,骨架仅实现基本概况)。
- **Q: 浏览器服务镜像?** A: 微软官方 `mcr.microsoft.com/playwright` + CDP server。
- **Q: 骨架如何触发?** A: 仅手动触发接口,不接 cron。
- **Q: context 生命周期粒度?** A: 按官方推荐,browser 常驻单例 + page 临时用完关。
- **Q: 浏览器部署?** A: 独立 Docker,本地连生产服务器,mac 不装浏览器。
