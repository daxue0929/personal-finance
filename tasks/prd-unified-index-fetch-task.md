# PRD — 统一指数抓取任务（unified-index-fetch-task）

**Feature slug**: `unified-index-fetch-task`

## 1. 背景

`data-crawler/app/task/` 下有 4 个高度雷同的指数抓取任务（科创50、科创100、沪深300、创业板50），每个文件结构完全一致：调 `fetch_and_store_index(<硬编码代码>, force_run)`，唯一差异是指数代码和市场前缀（由 `KcIndexParser.INDEX_CONFIG` 决定）。每次新增指数都需要：
- 复制一个 fetch_*_index_task.py 文件
- 在 `register_task.py` 加一行注册
- 在 `KcIndexParser.INDEX_CONFIG` 加新条目
- 在生产 `task_schedule` 表插一行

`fetch_kc100_index_task` 还有唯一副作用：拉取后额外把当日涨跌幅写入 `fund_info` 表 `020292` 的 `remark` 字段。重构时必须保留此副作用。

调度器当前只透传 `force_run` 一个 bool，无法传递业务参数（指数代码、市场、副作用目标基金）。`task_schedule` 表也无参数列，`TaskManage.vue` 表单没有参数配置项。

## 2. 功能目标

1. **任务函数统一**：4 个 fetch_*_index_task.py 合并为 `fetch_index_task(force_run, index_code, market, **kwargs)` 一个文件，删除 4 个旧任务文件。
2. **参数配置化**：在 `task_schedule` 表增加 `func_args JSON` 列，存 `{"index_code": "000688", "market": "sh"}` 形式。调度器在执行任务时从 `func_args` 解析并 **kwargs 透传给任务函数。`force_run` 保留为位置参数。
3. **kc100 副作用兼容**：在统一函数里 `if index_code == '000698'` 走额外分支调用 `FundInfoStorage.update_fund_remark('020292', change_pct_str)`，**不**增加新参数。
4. **KcIndexParser 松绑**：删除 `INDEX_CONFIG`，构造函数改为 `KcIndexParser(index_code, market)` 必传 `market`（`'sh'` 或 `'sz'`）；`INDEX_CONFIG` 在生产数据库迁移后无残留引用。
5. **任务配置管理列表**：前端 `TaskManage.vue` 表单新增"函数参数"动态 KV 编辑区（key/value 行，保存时序列化为 JSON 提交到后端 `func_args`）。
6. **数据库零手动迁移**：scheduler 启动时自动检测 `func_args` 列是否存在，不存在则执行 `ALTER TABLE task_schedule ADD COLUMN func_args JSON NULL`，并把现有 4 行旧任务记录替换为新 `fetch_index_task` 任务（ON DUPLICATE KEY UPDATE 幂等）。

## 3. 用户故事

- **US1 运维**：管理员登录后访问"任务管理"页，可以编辑任意指数抓取任务的参数（key/value 形式），保存后立即生效（下次调度周期或手动"立即执行"时生效）。
- **US2 开发**：新增一支指数（如"中证1000"，代码 000852）只需在 `task_schedule` 表插一行 `func_args={"index_code":"000852","market":"sh"}`，**不需修改任何 Python 代码**。
- **US3 测试**：单元测试用 `fetch_index_task(force_run=True, index_code='000688', market='sh')` 直接调用，无数据库依赖。
- **US4 kc100 业务行为不变**：kc100 抓取后仍然把当日涨跌幅写入 `fund_info.020292.remark`，与重构前完全一致。

## 4. 验收标准

### AC-1 后端代码
- [ ] `data-crawler/app/task/fetch_kc50_index_task.py` / `fetch_kc100_index_task.py` / `fetch_hs300_index_task.py` / `fetch_cyb50_index_task.py` **删除**。
- [ ] 新增 `data-crawler/app/task/fetch_index_task.py`，定义 `fetch_index_task(force_run: bool = False, index_code: str = '', market: str = 'sh', **kwargs) -> None`：
  - 入参校验：`index_code` 非空、长度 6、`market` ∈ {'sh', 'sz'}，否则 raise ValueError 并被 `execute_task_with_record` 捕获记录日志。
  - 调用 `fetch_and_store_index_with_market(index_code, market, force_run)`（helper 内部用 `KcIndexParser(index_code, market)`）。
  - `index_code == '000698'` 且返回 `KcIndexData` 非 None 时，调 `FundInfoStorage().update_fund_remark('020292', f"{change_percent:.2f}")`，异常 try/except 不中断主流程。
- [ ] `data-crawler/app/parser/kc_index_parser.py` 删除 `INDEX_CONFIG`；`__init__(self, index_code, market)` 两个必传；market 非法 raise ValueError；`get_supported_indices()` 同步删除。
- [ ] `data-crawler/app/task/index_fetch_helper.py` 把 `fetch_and_store_index` 改名为 `fetch_and_store_index_with_market(index_code, market, force_run)`，并把 `KcIndexParser(index_code)` 改为 `KcIndexParser(index_code, market)`。
- [ ] `register_task.py` 删除 4 行 fetch_*_index_task 注册，新增 1 行 `scheduler.register_task('fetch_index_task', fetch_index_task)`。

### AC-2 调度与数据库
- [ ] `data-crawler/app/scheduler.py`（或等价调度器）启动时自动检测 `task_schedule.func_args` 列是否存在，不存在则 `ALTER TABLE` 加列（idempotent）。检测逻辑用一次 `DESCRIBE task_schedule` 或 `information_schema.columns` 查询，错误吞掉日志。
- [ ] 启动时自动迁移 4 行旧任务到 `fetch_index_task`：删除 task_func IN (`fetch_kc50_index_task`, `fetch_kc100_index_task`, `fetch_hs300_index_task`, `fetch_cyb50_index_task`)，并插入 4 行 `task_func='fetch_index_task'`，`func_args` 分别为 `{"index_code":"000688","market":"sh"}` / `{"index_code":"000698","market":"sh"}` / `{"index_code":"000300","market":"sh"}` / `{"index_code":"399673","market":"sz"}`。
- [ ] 调度执行任务时，解析 `func_args` JSON 为 `dict`，**kwargs 透传给任务函数。`force_run` 仍为位置参数。
- [ ] 任务热加载 hash 字段保持：`task_func|cron_expression|enabled`（与现状一致），不把 `func_args` 纳入 hash（参数修改不要求重启调度器），下次执行时再读新参数。

### AC-3 API
- [ ] `POST /api/tasks` 和 `PUT /api/tasks/<id>` 接受 `func_args` 字段（任意 JSON 对象），存入数据库；其他字段白名单不变。
- [ ] `GET /api/tasks` 列表返回每条记录含 `func_args` 字段。
- [ ] `POST /api/task/run/<task_func>` 接受 `func_args`（可选）覆盖库内配置，**kwargs 传给任务函数。

### AC-4 前端
- [ ] `frontend/src/views/TaskManage.vue` 表单新增"函数参数"区域：
  - 动态行编辑（key/value 两个 `<el-input>` + 删除按钮 + "新增"按钮）
  - 提交时序列化为 JSON 提交到后端
  - 编辑/详情时反序列化填充
  - 不传参时提交空对象 `{}`
- [ ] `frontend/src/api/index.js` 的 `taskApi.createTask/updateTask` 接口传 `func_args` 字段；`runTask` 支持可选 `funcArgs` 参数。

### AC-5 测试
- [ ] `data-crawler/tests/test_unified_index_fetch_task.py`：
  - `test_fetch_index_task_value_error_no_code`：缺 index_code → ValueError
  - `test_fetch_index_task_value_error_invalid_market`：market='xx' → ValueError
  - `test_fetch_index_task_calls_helper`（mock）：传 (False, '000688', 'sh') 时正确调用 `fetch_and_store_index_with_market('000688', 'sh', False)`
  - `test_fetch_index_task_kc100_side_effect`（mock）：传 (False, '000698', 'sh') 时调 helper + `FundInfoStorage.update_fund_remark('020292', '<change_pct_str>')`
  - `test_fetch_index_task_kc100_no_data_no_side_effect`：helper 返回 None 时不调副作用
  - `test_fetch_index_task_kc100_side_effect_error_swallowed`：update_fund_remark 抛异常时任务不报错返回
- [ ] `data-crawler/tests/test_kc_index_parser_market.py`：
  - `test_init_requires_market`：不传 market → TypeError 或 ValueError
  - `test_init_invalid_market_value`：market='xx' → ValueError
- [ ] 现有测试（`test_index_crawler_expand.py` 等）保持通过。

### AC-6 全量回归
- [ ] `cd data-crawler && python3 -m pytest tests/ -q` 全量通过。
- [ ] `cd frontend && npm run build` 成功。
- [ ] 不破坏现有 4 个指数抓取任务在 `task_schedule` 表的 cron 调度（启动后自动迁移，新行沿用旧 cron 表达式）。

## 5. 非目标

- **不**改造 `KcIndexParser` 的字段解析逻辑（parts 数组下标、PE/PB 位置不变）。
- **不**为 fetch_index_task 增加除 kc100 副作用之外的任何额外副作用。
- **不**为非指数任务（如 `update_fund_net_values_task`、`calculate_buyer_shares_task` 等）引入参数化。
- **不**改 `task_schedule` 的 `task_func` 唯一索引语义（只增 `func_args` 列，不调整现有列）。
- **不**改前端"立即执行"按钮的 force_run 开关交互（仅在弹窗里增加"运行时参数覆盖"可选折叠区）。
- **不**回溯历史回测脚本 `tasks/backtest_*.py`。
- **不**为 kc100 副作用的目标基金代码（'020292'）新增参数化——保持硬编码。

## 6. 依赖

- `task_schedule` 表存在，可写（生产 117.72.53.38 / 本地均可）。
- `app/storage/fund_info_storage.py` 已存在 `update_fund_remark` 方法。
- 前端 Element Plus 支持 el-input + 动态行（已有 el-table 模板可参考）。
- APScheduler 现有 `run_with_trace_context` 支持 **kwargs 透传（已确认）。

## 7. 风险

| 风险 | 影响 | 缓解 |
|------|------|------|
| 启动时自动 `ALTER TABLE` 在生产失败 | 启动失败 / 部分迁移 | 加 try/except + 详细 ERROR 日志，提示 DBA 手动跑 `sql/alter/add_task_schedule_func_args.sql` |
| 4 行旧任务记录删除后 cron 暂时空白 | 抓取短暂中断（数秒到数分钟） | 同一事务内 DELETE + INSERT；启动事务前加锁；先确认 cron 表达式可从旧行复制 |
| `func_args` JSON 解析失败（用户输入非法 JSON） | 任务执行报错 | 调度器解析 try/except 失败时打 ERROR 并跳过本次执行，不崩溃 |
| KcIndexParser 去除 INDEX_CONFIG 后，调用方漏传 market | 启动报错或生产 500 | 单元测试 + lint 静态检查 + 文档化"market 必传" |
| 调度 hash 比对不把 func_args 纳入 → 用户改参数后无提示 | 用户不知道改完是否生效 | UI 给出"已修改但需等待下次执行"提示，不重启 |
| kc100 副作用的 update_fund_remark 抛异常 | 任务失败 | 现有代码已有 try/except 包裹，重构保持 |
| 前端"函数参数"区域对老任务（无 func_args）显示空表 | UI 误以为丢了配置 | 初次进入表单反序列化空对象→空编辑区 + 提示"暂未配置参数" |

## 8. Open Questions

（已与用户澄清完，无遗留）

## 9. 实施顺序（粗）

1. SQL：`sql/alter/add_task_schedule_func_args.sql`（DBA 备查）+ `sql/alter/migrate_index_tasks_to_unified.sql`（DBA 备查）
2. 后端 Storage：`task_schedule_storage.py` ORM + `update_task` 白名单加 `func_args`
3. 后端 API：`api_server.py` /api/tasks 接受 `func_args`；`/api/task/run/<task_func>` 接受覆盖
4. 调度器：`scheduler.py` 启动自检 ALTER + 数据迁移；任务执行时解析 func_args **kwargs 透传
5. Parser：`kc_index_parser.py` 删 INDEX_CONFIG，构造函数 market 必传
6. Helper：`index_fetch_helper.py` 改 `fetch_and_store_index_with_market(index_code, market, force_run)`
7. 任务：`fetch_index_task.py` 新文件，含 kc100 副作用分支
8. 注册：`register_task.py` 改 1 行
9. 删除 4 个 fetch_*_index_task.py
10. 测试：`test_unified_index_fetch_task.py` / `test_kc_index_parser_market.py`（TDD 先写）
11. 前端：`TaskManage.vue` KV 编辑区 + `api/index.js` 透传
12. 全量 pytest + npm run build
