# Task List: 统一指数抓取任务

**Based on PRD**: `tasks/prd-unified-index-fetch-task.md`
**Design**: `tasks/design-unified-index-fetch-task.md`

## Relevant Files

### Files to Create
- `data-crawler/app/task/fetch_index_task.py` — 统一任务函数（含 kc100 副作用分支）
- `data-crawler/tests/test_unified_index_fetch_task.py` — 任务函数单元测试
- `data-crawler/tests/test_kc_index_parser_market.py` — parser market 校验测试
- `sql/alter/add_task_schedule_func_args.sql` — DBA 备查：新增 func_args 列
- `sql/alter/migrate_index_tasks_to_unified.sql` — DBA 备查：4 行旧任务迁移到 fetch_index_task

### Files to Modify
- `data-crawler/app/scheduler/cron_scheduler.py` — 加 _resolve_func_args / _ensure_func_args_column / _migrate_index_tasks_to_unified；改 execute_task_with_record / run_job_now / _run_task_in_thread
- `data-crawler/app/storage/task_schedule_storage.py` — ORM 加 func_args JSON 列；update_task 白名单加 func_args
- `data-crawler/app/parser/kc_index_parser.py` — 删 INDEX_CONFIG + get_supported_indices；market 必传
- `data-crawler/app/parser/__init__.py` — 同步清理 get_supported_indices 导出
- `data-crawler/app/task/index_fetch_helper.py` — fetch_and_store_index 改名为 fetch_and_store_index_with_market，market 透传
- `data-crawler/app/task/register_task.py` — 删 4 行旧注册，加 1 行 fetch_index_task
- `data-crawler/app/web/api_server.py` — GET/POST/PUT /api/tasks 接受并返回 func_args；/api/task/run 接受 override
- `data-crawler/app/web/scheduler_proxy.py` — run_task 透传 func_args
- `frontend/src/views/TaskManage.vue` — 新增"函数参数"KV 动态行编辑区
- `frontend/src/api/index.js` — taskApi.createTask/updateTask 传 func_args；runTask 加 funcArgs 形参

### Files to Delete
- `data-crawler/app/task/fetch_kc50_index_task.py`
- `data-crawler/app/task/fetch_kc100_index_task.py`
- `data-crawler/app/task/fetch_hs300_index_task.py`
- `data-crawler/app/task/fetch_cyb50_index_task.py`

## Implementation Tasks

### 1. DB Schema & Storage ORM（TDD-N/A，直接建）
**Effort Estimate**: Small

#### Sub-tasks:
- [ ] 1.1 写 `sql/alter/add_task_schedule_func_args.sql`：`ALTER TABLE task_schedule ADD COLUMN func_args JSON NULL COMMENT '任务函数参数(JSON)' AFTER description`
- [ ] 1.2 写 `sql/alter/migrate_index_tasks_to_unified.sql`：事务内 SELECT INTO @var 暂存 4 行旧 cron/description，DELETE 4 行，INSERT 4 行新 fetch_index_task + func_args，`ON DUPLICATE KEY UPDATE` 幂等
- [ ] 1.3 改 `task_schedule_storage.py` ORM：新增 `func_args = Column(JSON, nullable=True)`；`update_task` 白名单加 `func_args`；`to_dict` / `_to_dict` 序列化时透出 `func_args`
- [ ] 1.4 跑 `python3 -c "from app.storage import TaskScheduleStorage; print(TaskScheduleStorage().__table__.columns.keys())"` 确认列存在

### 2. KcIndexParser & Helper 重构（TDD 节奏）
**Effort Estimate**: Medium

#### Sub-tasks:
- [ ] 2.1 写 `test_kc_index_parser_market.py`：`test_init_requires_market`（不传 market → TypeError 或 ValueError）、`test_init_invalid_market_value`（market='xx' → ValueError）、`test_init_valid_markets`（sh/sz 都 OK）
- [ ] 2.2 改 `kc_index_parser.py`：删 INDEX_CONFIG 字典 + get_supported_indices 类方法；`__init__(self, index_code, market)` 两个必传；market 非法 raise ValueError；`self.index_name = ''`（不再硬编码）；`self.market = market`
- [ ] 2.3 跑 `pytest tests/test_kc_index_parser_market.py -q` 全绿
- [ ] 2.4 改 `parser/__init__.py` 删 `get_supported_indices` 导出（如果存在）
- [ ] 2.5 改 `index_fetch_helper.py`：`fetch_and_store_index(index_code, force_run)` → `fetch_and_store_index_with_market(index_code, market, force_run)`；`KcIndexParser(index_code)` → `KcIndexParser(index_code, market)`
- [ ] 2.6 跑全量 `pytest tests/ -q` 确认现有测试不破

### 3. 统一任务函数 + 删除旧任务（TDD 节奏）
**Effort Estimate**: Medium

#### Sub-tasks:
- [ ] 3.1 写 `test_unified_index_fetch_task.py`：
  - `test_fetch_index_task_value_error_no_code`：缺 index_code → ValueError
  - `test_fetch_index_task_value_error_wrong_length_code`：index_code 长度非 6 → ValueError
  - `test_fetch_index_task_value_error_invalid_market`：market='xx' → ValueError
  - `test_fetch_index_task_calls_helper`（mock fetch_and_store_index_with_market）：传 ('000688', 'sh', False) 时正确调用
  - `test_fetch_index_task_kc100_side_effect`（mock FundInfoStorage.update_fund_remark）：('000698', 'sh', False) 时调 update_fund_remark('020292', '<change_pct_str>')
  - `test_fetch_index_task_kc100_no_data_no_side_effect`：helper 返回 None 时不调 update_fund_remark
  - `test_fetch_index_task_kc100_side_effect_error_swallowed`：update_fund_remark 抛异常时任务正常返回
  - `test_fetch_index_task_non_kc100_no_side_effect`（control）：('000688', 'sh') 不调 update_fund_remark
- [ ] 3.2 新增 `app/task/fetch_index_task.py`：
  ```python
  def fetch_index_task(force_run: bool = False, **kwargs) -> None:
      index_code = kwargs.get('index_code', '')
      market     = kwargs.get('market', 'sh')
      # 校验...
      index_data = fetch_and_store_index_with_market(index_code, market, force_run)
      if index_code == '000698' and index_data is not None:
          try:
              FundInfoStorage().update_fund_remark('020292', f"{index_data.change_percent:.2f}")
          except Exception as e:
              logger.error(f"kc100 副作用失败: {e}")
  ```
- [ ] 3.3 跑 `pytest tests/test_unified_index_fetch_task.py -q` 全绿
- [ ] 3.4 删 4 个旧文件：`fetch_kc50_index_task.py` / `fetch_kc100_index_task.py` / `fetch_hs300_index_task.py` / `fetch_cyb50_index_task.py`
- [ ] 3.5 跑全量 `pytest tests/ -q` 确认无回归

### 4. 调度器改造（自检 ALTER + 迁移 + 透传）
**Effort Estimate**: Medium

#### Sub-tasks:
- [ ] 4.1 在 `cron_scheduler.py` 新增 3 个辅助方法：
  - `_ensure_func_args_column()`：information_schema 查询列存在性，0 行则 ALTER TABLE ADD COLUMN func_args JSON NULL，try/except 包整体打 ERROR
  - `_migrate_index_tasks_to_unified()`：单一事务，先 SELECT INTO 4 个 @var 暂存 cron/description，再 DELETE 4 行旧 task_func，再 INSERT 4 行新 fetch_index_task + func_args，`ON DUPLICATE KEY UPDATE` 幂等
  - `_resolve_func_args(task_func_name, override=None)`：override 优先；否则查 self._task_schedule_storage 的 func_args 字段（字符串则 json.loads），解析失败 try/except 返回 `{}`
- [ ] 4.2 改 `start()` 方法入口处依次调用 `_ensure_func_args_column()` → `_migrate_index_tasks_to_unified()`，各包 try/except 不抛
- [ ] 4.3 改 `execute_task_with_record` (line 116)：在 `run_with_trace_context` 调用前 `kwargs = self._resolve_func_args(task_func_name)`，**kwargs 透传
- [ ] 4.4 改 `run_job_now` (line 199) 签名加 `func_args: Optional[Dict] = None`，透传到 `_run_task_in_thread`
- [ ] 4.5 改 `_run_task_in_thread` (line 234) 接受 `func_args_override`，调 `_resolve_func_args(task_func_name, override=func_args_override)`
- [ ] 4.6 改 `register_task.py`：删 4 行 fetch_*_index_task 注册，加 `scheduler.register_task('fetch_index_task', fetch_index_task)`
- [ ] 4.7 跑全量 `pytest tests/ -q` 确认无回归（mock 调度器路径覆盖）
- [ ] 4.8 改 `api_server.py`：
  - `GET /api/tasks` 序列化包含 `func_args`
  - `POST /api/tasks` 白名单加 `func_args`
  - `PUT /api/tasks/<id>` 白名单加 `func_args`
  - `POST /api/task/run/<task_func>` 接受 `func_args`（可选 override）并透传到 scheduler_proxy
- [ ] 4.9 改 `scheduler_proxy.py` `run_task` 形参加 `func_args: dict | None = None`，透传到 scheduler 进程 `/internal/task/run`
- [ ] 4.10 改 `control_server.py` `/internal/task/run`（如果存在）接受 func_args 并调 `run_job_now(..., func_args=...)`

### 5. 前端 KV 编辑区
**Effort Estimate**: Medium

#### Sub-tasks:
- [ ] 5.1 改 `TaskManage.vue`：
  - `import { Delete } from '@element-plus/icons-vue'`
  - `const funcArgs = ref([])` 局部状态
  - 在表单内 `description` 之后新增 `<el-form-item label="函数参数">` 区块：动态 `el-row :gutter="8"` v-for，每行 3 个 `el-col`（key input / value input / delete button），底部"+ 新增参数"按钮，空数组显示"暂未配置参数"提示
  - `showEditDialog(row)` 回显：`funcArgs.value = row.func_args ? Object.entries(row.func_args).map(([k,v]) => ({key:k, value:String(v)})) : []`
  - `showCreateDialog()` 重置：`funcArgs.value = []`
  - `submitForm()` 序列化：`const func_args = Object.fromEntries(funcArgs.value.filter(x => x.key).map(x => [x.key, x.value]))`，与其他字段一起提交
  - `runTask` 弹窗加可选"运行时参数覆盖"折叠区，复用 funcArgs UI，提交时若折叠区有内容则覆盖
- [ ] 5.2 改 `api/index.js`：
  - `taskApi.createTask` / `updateTask` 接受 `func_args` 字段
  - `taskApi.runTask(taskFunc, forceRun=false, funcArgs=null)` 接受可选 funcArgs
- [ ] 5.3 `cd frontend && npm run build` 验证构建成功

### 6. 全量回归 + 文档归档
**Effort Estimate**: Small

#### Sub-tasks:
- [ ] 6.1 `cd data-crawler && python3 -m pytest tests/ -q` 全量绿
- [ ] 6.2 `cd frontend && npm run build` 成功
- [ ] 6.3 启动 scheduler 看自动迁移日志（开发库或生产库）
- [ ] 6.4 手动执行 4 个 fetch_index_task 任务（用 `/api/task/run/fetch_index_task` + 传 func_args 区分），确认 4 个指数都成功抓取
- [ ] 6.5 确认 `dist/` 提交，commit 信息中文简洁
- [ ] 6.6 归档 PRD/design/tasks 三个文件保留在 `tasks/`（不删除，按规约）

## Notes

- **依赖顺序**：T1 → T2 → T3 → T4 → T5 → T6；T1 可与 T2 并行（不同文件）
- **风险点**：
  - `ALTER TABLE` 在大表上会锁表，PRD 风险表已点；用 information_schema 查询避免锁
  - 4 行旧任务 DELETE + INSERT 同事务，cron 表达式用 @var 暂存保留
  - kc100 副作用 try/except 包裹不中断主流程
- **TDD 硬性顺序**：
  - T2：先写 `test_kc_index_parser_market.py` → 改 parser → 跑绿
  - T3：先写 `test_unified_index_fetch_task.py` → 新建 fetch_index_task.py → 跑绿 → 删 4 个旧文件 → 再跑全量
- **前端构建门禁**：T5 改完 `frontend/src/` 必须 `npm run build`，dist 提交到版本库
- **不破现有测试**：`test_index_crawler_expand.py` 等保持通过；如破，需要更新 import 而非删除测试
