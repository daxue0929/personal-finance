# Design — 统一指数抓取任务

**PRD**: `tasks/prd-unified-index-fetch-task.md`

## 1. 目标

把 4 个高度雷同的 `fetch_*_index_task` 合并为一个 `fetch_index_task`；把指数代码、市场、副作用目标基金等业务参数从代码里抽到 `task_schedule.func_args`（JSON 列）。`KcIndexParser` 去掉 `INDEX_CONFIG` 硬编码列表，market 由外部传入。新增指数无需改 Python 代码。

## 2. 关键设计决策

### 2.1 任务函数签名

```python
def fetch_index_task(force_run: bool = False, **kwargs) -> None:
    index_code = kwargs.get('index_code', '')
    market     = kwargs.get('market', 'sh')
    if not index_code or len(index_code) != 6:
        raise ValueError(f"index_code 必传且长度 6, got {index_code!r}")
    if market not in ('sh', 'sz'):
        raise ValueError(f"market 必须为 'sh' 或 'sz', got {market!r}")
    ...
```

- `force_run` 保留为位置参数（避免 inspect.signature 反射解析 kwargs）。
- `index_code` / `market` 走 `**kwargs`，由调度器从 `func_args` 注入。
- kc100 副作用在函数体里 `if index_code == '000698':` 硬编码分支，不增新参数（PRD 已定）。

### 2.2 调度器注入路径

`app/scheduler/cron_scheduler.py` 改 3 处：

1. **新增辅助方法** `_resolve_func_args(task_func_name, override=None)`：
   - `override` 来自手动触发（`run_job_now` 接收 `func_args` 覆盖）。
   - 否则查 `task_schedule.func_args`（字符串则 `json.loads`；dict/None 兼容）。
   - 解析失败 try/except 打 ERROR 返回 `{}`（不阻塞任务执行）。

2. **`execute_task_with_record` (line 116)** 注入：
   ```python
   kwargs = self._resolve_func_args(task_func_name)
   run_with_trace_context(
       self.task_registry[task_func_name], task_name,
       force_run=force_run, trace_id=trace_id, **kwargs
   )
   ```
   现状 line 147-149 不传 kwargs。

3. **`_run_task_in_thread` (line 234) + `run_job_now` (line 199)** 同步注入：
   - `run_job_now` 新增形参 `func_args: Optional[Dict] = None`，透传到 `_run_task_in_thread`。
   - `_run_task_in_thread` 用 `override` 路径解析 `func_args`。

**`func_args` 不进 hash**：维持现状 hash 字段为 `task_func|cron_expression|enabled`，参数修改不触发 job 重建（热加载），下次 cron 触发 / 手动触发时再读新值。

### 2.3 数据库自检 + 迁移

启动时（`CronTaskScheduler.start()` 入口或更早的 `__init__` 末）执行：

1. **`_ensure_func_args_column()`**：用 `information_schema.columns` 查列存在性，0 行则 `ALTER TABLE` 加列。
2. **`_migrate_index_tasks_to_unified()`**：DELETE 4 行旧 + INSERT 4 行新（事务 + ON DUPLICATE KEY UPDATE 幂等）。

完整 SQL 落盘到 `sql/alter/migrate_index_tasks_to_unified.sql`（DBA 备查）。

### 2.4 KcIndexParser 改造

- 删除 `INDEX_CONFIG` 字典 + `get_supported_indices()` 类方法。
- `__init__(index_code, market='sh')` market 必传，非法 raise ValueError。
- `index_name = ''`（不再硬编码）。

### 2.5 Helper 改动

`app/task/index_fetch_helper.py`：
- `fetch_and_store_index(index_code, force_run)` 改名为 `fetch_and_store_index_with_market(index_code, market, force_run)`。
- 内部 `KcIndexParser(index_code, market)` market 由调用方传。

### 2.6 API 与 Storage

- ORM `TaskSchedule` 加 `func_args = Column(JSON, nullable=True)`。
- `app/web/api_server.py`：GET/POST/PUT /api/tasks 接受并返回 `func_args`；`POST /api/task/run/<task_func>` 接受 override。
- `app/web/scheduler_proxy.py` `run_task` 透传 `func_args`。

### 2.7 前端 KV 编辑区

`frontend/src/views/TaskManage.vue` 新增"函数参数"区域：动态 KV 行（key + value + 删除按钮 + "新增"按钮）；回显 `Object.entries()` 转数组；提交 `Object.fromEntries()` 序列化为 JSON。空对象 `{}` 也提交。

`frontend/src/api/index.js` `taskApi.runTask(taskFunc, forceRun=false, funcArgs=null)`。

## 3. 文件改动清单

### 新增
- `data-crawler/app/task/fetch_index_task.py`
- `data-crawler/tests/test_unified_index_fetch_task.py`
- `data-crawler/tests/test_kc_index_parser_market.py`
- `sql/alter/add_task_schedule_func_args.sql`（DBA 备查）
- `sql/alter/migrate_index_tasks_to_unified.sql`（DBA 备查）

### 修改
- `data-crawler/app/scheduler/cron_scheduler.py`
- `data-crawler/app/storage/task_schedule_storage.py`
- `data-crawler/app/parser/kc_index_parser.py`
- `data-crawler/app/parser/__init__.py`
- `data-crawler/app/task/index_fetch_helper.py`
- `data-crawler/app/task/register_task.py`
- `data-crawler/app/web/api_server.py`
- `data-crawler/app/web/scheduler_proxy.py`
- `frontend/src/views/TaskManage.vue`
- `frontend/src/api/index.js`

### 删除
- `data-crawler/app/task/fetch_kc50_index_task.py`
- `data-crawler/app/task/fetch_kc100_index_task.py`
- `data-crawler/app/task/fetch_hs300_index_task.py`
- `data-crawler/app/task/fetch_cyb50_index_task.py`

## 4. 实施顺序（TDD 节奏）

1. 写测试 `test_kc_index_parser_market.py` → 改 parser → 跑通
2. 写测试 `test_unified_index_fetch_task.py` → 改 helper → 新增 fetch_index_task → 跑通
3. 改 storage ORM
4. 改 api / scheduler_proxy
5. 改 scheduler 自检 + 迁移 + 透传
6. 改 register_task.py
7. 删除 4 个旧 fetch_*_index_task.py
8. 改前端
9. 后端全量 pytest
10. 前端 npm run build

## 5. 不做的事

- 不改 cron 表达式、enabled 语义、不改 task_func 唯一索引。
- 不为非指数任务引入参数化。
- 不把 market 写入数据库。
- 不回溯 `tasks/backtest_*.py`。
- 不为 kc100 副作用的目标基金代码（'020292'）新增参数化。
- 不做 kc100 副作用的失败重试。
